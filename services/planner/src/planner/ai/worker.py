"""Separate bounded I/O worker; no model invocation occurs on an HTTP request."""

import asyncio
import signal
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from time import perf_counter
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from planner.ai.interpret import parse_proposal
from planner.ai.prompt import PROMPT_HASH, SCHEMA_HASH
from planner.ai.provider import (
    AIConfig,
    Context,
    MockProvider,
    OpenAIResponsesProvider,
    ProviderError,
)
from planner.ai.spend import reserve, settle
from planner.db.ai_models import InterpretationRecord
from planner.db.session import create_db_engine
from planner.settings import Settings

POOL_SIZE = 2


def utc_now():
    return datetime.now(UTC)


@dataclass(frozen=True)
class Claim:
    id: UUID
    owner_id: UUID
    token: int
    context: Context
    mode: str


def claim_next(engine, now):
    with Session(engine) as db, db.begin():
        db.execute(text("SELECT pg_advisory_xact_lock(712909)"))
        if (
            db.scalar(
                select(func.count())
                .select_from(InterpretationRecord)
                .where(InterpretationRecord.state == "RUNNING")
            )
            >= POOL_SIZE
        ):
            return None
        row = db.scalar(
            select(InterpretationRecord)
            .where(InterpretationRecord.state == "QUEUED")
            .order_by(InterpretationRecord.created_at, InterpretationRecord.id)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if row is None:
            return None
        row.state = "RUNNING"
        row.fencing_token += 1
        row.lease_until = now + timedelta(seconds=35)
        return Claim(
            row.id,
            row.owner_id,
            row.fencing_token,
            Context(row.source_text, row.reference_now, row.timezone),
            row.mode,
        )


def process_claim(engine, claim, *, provider=None, config=None, clock=utc_now):
    started = perf_counter()
    config = config or AIConfig()
    result = proposal = None
    error = None
    try:
        if claim.mode == "openai":
            amount = reserve(engine, claim, config)
            provider = provider or OpenAIResponsesProvider(config, reserved_microusd=amount)
        else:
            provider = provider or MockProvider()

        async def bounded_call():
            async with asyncio.timeout(config.provider_timeout_seconds):
                return await provider.extract(claim.context)

        result = asyncio.run(bounded_call())
        proposal = parse_proposal(result.payload_json, claim.context.text)
    except TimeoutError:
        error = "PROVIDER_TIMEOUT"
    except ProviderError as failure:
        error = failure.code
    except (ValueError, KeyError, OverflowError):
        error = "MODEL_OUTPUT_INVALID"
    except Exception:
        error = "INTERPRETATION_FAILED"
    with Session(engine) as db, db.begin():
        row = db.get(InterpretationRecord, claim.id, with_for_update=True)
        if row.state != "RUNNING" or row.fencing_token != claim.token or row.lease_until <= clock():
            return False
        cost = settle(db, row.id, result, config)
        row.state = "FAILED" if error else "READY"
        row.error_code = error
        row.proposal = proposal.model_dump(mode="json") if proposal else None
        row.completed_at = clock()
        row.lease_until = None
        row.metadata_json = {
            "provider": result.provider if result else claim.mode,
            "model": result.model if result else config.model,
            "prompt_hash": PROMPT_HASH,
            "schema_hash": SCHEMA_HASH,
            "latency_ms": (perf_counter() - started) * 1000,
            "input_tokens": result.input_tokens if result else None,
            "output_tokens": result.output_tokens if result else None,
            "attempts": result.attempts if result else None,
            "cost_microusd": 0 if claim.mode == "mock" else cost,
            "price_as_of": config.price_as_of if claim.mode == "openai" else None,
            "demonstration_only": claim.mode == "mock",
        }
    return True


def reconcile_expired(engine, now):
    with Session(engine) as db, db.begin():
        rows = db.scalars(
            select(InterpretationRecord)
            .where(InterpretationRecord.state == "RUNNING", InterpretationRecord.lease_until < now)
            .with_for_update(skip_locked=True)
        ).all()
        for row in rows:
            row.state = "FAILED"
            row.error_code = "WORKER_INTERRUPTED"
            row.fencing_token += 1
            row.completed_at = now
            row.lease_until = None
            settle(db, row.id, None, AIConfig())
        return len(rows)


def run_once(engine, *, provider=None, config=None, clock=utc_now):
    reconcile_expired(engine, clock())
    claim = claim_next(engine, clock())
    if claim is None:
        return False
    return process_claim(engine, claim, provider=provider, config=config, clock=clock)


def serve(engine, stop):
    futures = set()
    with ThreadPoolExecutor(max_workers=POOL_SIZE) as pool:
        while not stop.is_set():
            for future in tuple(futures):
                if future.done():
                    future.result()
                    futures.remove(future)
            reconcile_expired(engine, utc_now())
            while len(futures) < POOL_SIZE and not stop.is_set():
                claim = claim_next(engine, utc_now())
                if claim is None:
                    break
                futures.add(pool.submit(process_claim, engine, claim))
            stop.wait(0.1)


def main():
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    engine = create_db_engine(Settings())
    try:
        serve(engine, stop)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
