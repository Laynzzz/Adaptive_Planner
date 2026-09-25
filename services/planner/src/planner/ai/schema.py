"""Typed model proposals are data, never executable commands."""

from typing import Generic, Literal, TypeVar

from pydantic import Field, model_validator

from planner.domain.contracts import Contract, Deadline

Value = TypeVar("Value")


class EvidenceSpan(Contract):
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    text: str

    @model_validator(mode="after")
    def ordered(self):
        if self.end <= self.start:
            raise ValueError("Evidence spans must be nonempty")
        return self


class Extracted(Contract, Generic[Value]):  # noqa: UP046 - Pydantic generic schema naming is frozen
    value: Value | None
    label: Literal["explicit", "inferred", "unknown"]
    evidence: tuple[EvidenceSpan, ...]
    requires_confirmation: bool

    @model_validator(mode="after")
    def review_required(self):
        if self.label in ("inferred", "unknown") and not self.requires_confirmation:
            raise ValueError("Uncertain fields must require confirmation")
        if self.label == "explicit" and not self.evidence:
            raise ValueError("Explicit fields require evidence")
        if self.label == "unknown" and self.value is not None:
            raise ValueError("Unknown fields cannot invent a value")
        return self


class DraftTask(Contract):
    key: str = Field(pattern=r"^task_[1-9][0-9]*$")
    title: Extracted[str]
    remaining_minutes: Extracted[int]
    deadline: Extracted[Deadline]
    priority: Extracted[int]
    predecessor_keys: tuple[str, ...] = ()


class DraftConstraint(Contract):
    key: str
    kind: Literal["SOFT_AVOID", "HARD_UNAVAILABLE", "HARD_NO_DEADLINE"]
    weekday: int = Field(ge=0, le=6)
    label: Literal["explicit", "inferred", "unknown"]
    evidence: tuple[EvidenceSpan, ...]
    requires_confirmation: bool = True


class ExtractionDraft(Contract):
    schema_version: Literal["extraction-v1"] = "extraction-v1"
    tasks: tuple[DraftTask, ...] = Field(default=(), max_length=20)
    constraints: tuple[DraftConstraint, ...] = Field(default=(), max_length=20)
    unresolved_fields: tuple[str, ...] = ()
    abstained: bool = False
