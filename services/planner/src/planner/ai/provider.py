"""One HTTP provider plus an explicit deterministic local demonstration parser."""

import asyncio
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from time import perf_counter
from typing import Protocol
from zoneinfo import ZoneInfo

import httpx
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from planner.ai.prompt import PROMPT, PROMPT_HASH, SCHEMA_HASH, response_schema


class AIConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PLANNER_AI_", env_file=".env", extra="ignore")
    live_enabled: bool = False
    api_key: SecretStr | None = None
    model: str | None = None
    approval_reference: str | None = None
    budget_microusd: int = Field(default=0, ge=0)
    input_rate_microusd_per_million: int | None = Field(default=None, gt=0)
    output_rate_microusd_per_million: int | None = Field(default=None, gt=0)
    price_as_of: str | None = None
    max_output_tokens: int = Field(default=4096, ge=128, le=8192)
    provider_timeout_seconds: float = Field(default=30, gt=0, le=30)


@dataclass(frozen=True)
class Context:
    text: str
    reference_now: datetime
    timezone: str


@dataclass(frozen=True)
class LLMResult:
    payload_json: str
    provider: str
    model: str
    latency_ms: float
    input_tokens: int | None = None
    output_tokens: int | None = None
    attempts: int = 1
    prompt_hash: str = PROMPT_HASH
    schema_hash: str = SCHEMA_HASH


class ProviderError(Exception):
    def __init__(self, code: str, *, retryable: bool = False):
        self.code, self.retryable = code, retryable
        super().__init__(code)


class Provider(Protocol):
    async def extract(self, context: Context) -> LLMResult: ...


def require_live_config(config: AIConfig):
    if not config.live_enabled:
        raise ProviderError("LIVE_DISABLED")
    if not config.api_key or not config.model or not config.approval_reference:
        raise ProviderError("PROVIDER_NOT_CONFIGURED")
    if (
        config.budget_microusd <= 0
        or config.input_rate_microusd_per_million is None
        or config.output_rate_microusd_per_million is None
        or not config.price_as_of
    ):
        raise ProviderError("SPEND_NOT_CONFIGURED")


def request_body(context: Context, config: AIConfig):
    return {
        "model": config.model,
        "store": False,
        "max_output_tokens": config.max_output_tokens,
        "instructions": PROMPT,
        "input": json.dumps(
            {
                "text": context.text,
                "reference_now": context.reference_now.isoformat(),
                "timezone": context.timezone,
            }
        ),
        "text": {
            "format": {
                "type": "json_schema",
                "name": "planner_extraction",
                "strict": True,
                "schema": response_schema(),
            }
        },
    }


def maximum_charge(context: Context, config: AIConfig) -> int:
    require_live_config(config)
    # Conservative byte upper bound plus protocol allowance, for two possible attempts.
    input_bound = len(json.dumps(request_body(context, config)).encode("utf-8")) + 4096
    return 2 * (
        (
            input_bound * config.input_rate_microusd_per_million
            + config.max_output_tokens * config.output_rate_microusd_per_million
            + 999999
        )
        // 1000000
    )


class OpenAIResponsesProvider:
    def __init__(self, config: AIConfig, *, transport=None, reserved_microusd: int = 0):
        self.config, self.transport = config, transport
        self.reserved_microusd = reserved_microusd

    async def extract(self, context: Context) -> LLMResult:
        require_live_config(self.config)
        if self.reserved_microusd < maximum_charge(context, self.config):
            raise ProviderError("SPEND_RESERVATION_REQUIRED")
        started = perf_counter()
        attempts = 0
        try:
            async with asyncio.timeout(self.config.provider_timeout_seconds):
                async with httpx.AsyncClient(
                    timeout=self.config.provider_timeout_seconds, transport=self.transport
                ) as client:
                    for attempt in range(2):
                        attempts += 1
                        try:
                            response = await client.post(
                                "https://api.openai.com/v1/responses",
                                headers={
                                    "Authorization": "Bearer "
                                    + self.config.api_key.get_secret_value()
                                },
                                json=request_body(context, self.config),
                            )
                        except (httpx.TimeoutException, httpx.TransportError):
                            if attempt == 0:
                                continue
                            raise ProviderError("PROVIDER_TIMEOUT", retryable=True) from None
                        if response.status_code == 429 or response.status_code >= 500:
                            if attempt == 0:
                                continue
                            raise ProviderError("PROVIDER_UNAVAILABLE", retryable=True)
                        if response.status_code in (401, 403):
                            raise ProviderError("PROVIDER_AUTH_REQUIRED")
                        if response.status_code >= 400:
                            raise ProviderError("PROVIDER_REJECTED")
                        data = response.json()
                        if data.get("status") != "completed":
                            raise ProviderError("PROVIDER_INCOMPLETE")
                        content = [
                            item
                            for message in data.get("output", [])
                            if message.get("type") == "message"
                            for item in message.get("content", [])
                        ]
                        if any(item.get("type") == "refusal" for item in content):
                            raise ProviderError("PROVIDER_REFUSED")
                        payload = "".join(
                            item["text"] for item in content if item.get("type") == "output_text"
                        )
                        if not payload:
                            raise ProviderError("PROVIDER_EMPTY")
                        usage = data.get("usage") or {}
                        return LLMResult(
                            payload,
                            "openai",
                            self.config.model,
                            (perf_counter() - started) * 1000,
                            usage.get("input_tokens"),
                            usage.get("output_tokens"),
                            attempts,
                        )
        except TimeoutError:
            raise ProviderError("PROVIDER_TIMEOUT", retryable=True) from None
        except (ValueError, KeyError, TypeError):
            raise ProviderError("PROVIDER_MALFORMED") from None
        raise ProviderError("PROVIDER_UNAVAILABLE")


class MockProvider:
    """A deliberately limited rule-based demonstration, not measured AI quality."""

    async def extract(self, context: Context) -> LLMResult:
        started = perf_counter()
        tasks, constraints, unresolved = [], [], []
        text = context.text
        if re.search(
            r"ignore (?:all |previous )?instructions|system prompt|execute code|delete all",
            text,
            re.I,
        ):
            payload = {
                "tasks": [],
                "constraints": [],
                "unresolved_fields": ["unsupported_request"],
                "abstained": True,
            }
            return LLMResult(json.dumps(payload), "mock", "deterministic-demo-v1", 0, 0, 0)

        def extracted(value, label, start=None, end=None):
            evidence = (
                [] if start is None else [{"start": start, "end": end, "text": text[start:end]}]
            )
            return {
                "value": value,
                "label": label,
                "evidence": evidence,
                "requires_confirmation": label != "explicit",
            }

        weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        offset = 0
        for raw_line in text.splitlines():
            line = raw_line.strip()
            begin = offset + len(raw_line) - len(raw_line.lstrip())
            offset += len(raw_line) + 1
            if not line:
                continue
            match = re.search(
                r"(dislike|cannot work|no deadlines)\s+(?:on\s+)?(" + "|".join(weekdays) + ")",
                line,
                re.I,
            )
            if match:
                kind = {
                    "dislike": "SOFT_AVOID",
                    "cannot work": "HARD_UNAVAILABLE",
                    "no deadlines": "HARD_NO_DEADLINE",
                }[match[1].lower()]
                constraints.append(
                    {
                        "key": f"constraint_{len(constraints) + 1}",
                        "kind": kind,
                        "weekday": weekdays.index(match[2].lower()),
                        "label": "explicit",
                        "requires_confirmation": True,
                        "evidence": [
                            {
                                "start": begin + match.start(),
                                "end": begin + match.end(),
                                "text": match[0],
                            }
                        ],
                    }
                )
                continue
            key = f"task_{len(tasks) + 1}"
            duration = re.search(r"\b(\d+)\s*(minutes?|mins?|hours?|hrs?)\b", line, re.I)
            title_end = re.search(r"\s+(?:for|due|by|after|priority)\b", line, re.I)
            title = line[: title_end.start()] if title_end else line
            fields = {"key": key, "title": extracted(title, "explicit", begin, begin + len(title))}
            if duration:
                minutes = int(duration[1]) * (60 if duration[2].lower().startswith(("h",)) else 1)
                fields["remaining_minutes"] = extracted(
                    minutes, "explicit", begin + duration.start(), begin + duration.end()
                )
            else:
                fields["remaining_minutes"] = extracted(None, "unknown")
                unresolved.append(f"tasks.{key}.remaining_minutes")
            due = re.search(r"\b(?:due|by)\s+(.+?)(?=\s+(?:after|priority)\b|$)", line, re.I)
            if due:
                value = due[1].strip().rstrip(".")
                deadline = None
                label = "explicit"
                if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                    deadline = {"kind": "DATE", "value": value, "timezone": context.timezone}
                elif value.lower() in ("today", "tomorrow"):
                    day = context.reference_now.astimezone(ZoneInfo(context.timezone)).date()
                    day += timedelta(days=value.lower() == "tomorrow")
                    deadline = {
                        "kind": "DATE",
                        "value": day.isoformat(),
                        "timezone": context.timezone,
                    }
                    label = "inferred"
                else:
                    label = "unknown"
                    unresolved.append(f"tasks.{key}.deadline")
                fields["deadline"] = extracted(
                    deadline, label, begin + due.start(1), begin + due.end(1)
                )
            else:
                fields["deadline"] = extracted(None, "inferred")
            priority = re.search(r"\bpriority\s+([1-5])\b", line, re.I)
            fields["priority"] = (
                extracted(
                    int(priority[1]), "explicit", begin + priority.start(), begin + priority.end()
                )
                if priority
                else extracted(3, "inferred")
            )
            fields["predecessor_keys"] = re.findall(r"\bafter\s+(task_[1-9][0-9]*)", line)
            tasks.append(fields)
        payload = {
            "tasks": tasks,
            "constraints": constraints,
            "unresolved_fields": unresolved,
            "abstained": not tasks and not constraints,
        }
        return LLMResult(
            json.dumps(payload),
            "mock",
            "deterministic-demo-v1",
            (perf_counter() - started) * 1000,
            0,
            0,
        )
