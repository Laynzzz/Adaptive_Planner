"""Immutable, JSON-serializable public boundaries shared by API and solvers."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_serializer,
    field_validator,
    model_validator,
)


def utc_instant(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("instant must be timezone-aware")
    return value.astimezone(UTC)


Instant = Annotated[datetime, AfterValidator(utc_instant)]
SlotRange = tuple[int, int]
Scalar = str | int | float | bool | None


class Contract(BaseModel):
    model_config = ConfigDict(
        frozen=True, extra="forbid", allow_inf_nan=False, validate_default=True
    )


class TaskState(StrEnum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"
    CANCELLED = "CANCELLED"


class Deadline(Contract):
    kind: Literal["DATE", "TIMESTAMP"]
    value: str
    timezone: str = "UTC"
    fold: Literal[0, 1] | None = None


class TaskSpec(Contract):
    id: UUID
    owner_id: UUID
    title: str = Field(min_length=1, max_length=500)
    state: TaskState = TaskState.TODO
    release_at: Instant | None = None
    release_slot: int = 0
    deadline: Deadline | None = None
    deadline_at: Instant | None = None
    deadline_slot: int | None = None
    remaining_minutes: int = Field(ge=0, strict=True)
    priority: int = Field(default=3, ge=1, le=5, strict=True)
    splittable: bool = True
    min_block_slots: int = Field(default=2, ge=1, strict=True)
    max_block_slots: int = Field(default=12, ge=1, strict=True)
    short_final_allowed: bool = False

    @computed_field
    @property
    def required_slots(self) -> int:
        return (self.remaining_minutes + 14) // 15

    @model_validator(mode="after")
    def block_bounds(self):
        if self.min_block_slots > self.max_block_slots:
            raise ValueError("min_block_slots exceeds max_block_slots")
        return self


class Dependency(Contract):
    predecessor_id: UUID
    successor_id: UUID
    owner_id: UUID


class Block(Contract):
    id: UUID
    owner_id: UUID
    task_id: UUID
    start: Instant
    end: Instant
    start_slot: int
    end_slot: int
    source: str = "GREEDY"
    locked: bool = False
    original_start: Instant | None = None

    @model_validator(mode="after")
    def positive_interval(self):
        if self.end <= self.start or self.end_slot <= self.start_slot:
            raise ValueError("block must have a nonempty half-open interval")
        return self


class Violation(Contract):
    code: str
    related_ids: tuple[UUID, ...] = ()
    facts: Mapping[str, Scalar] = Field(default_factory=dict)

    @field_validator("facts", mode="after")
    @classmethod
    def freeze_facts(cls, value):
        return MappingProxyType(dict(value))

    @field_serializer("facts")
    def serialize_facts(self, value):
        return dict(value)


class Score(Contract):
    future_work_deficit: float = Field(default=0, ge=0, le=1)
    disruption: float = Field(default=0, ge=0, le=1)
    preference_mismatch: float = Field(default=0, ge=0, le=1)
    fragmentation: float = Field(default=0, ge=0, le=1)
    completion_delay: float = Field(default=0, ge=0, le=1)
    objective_version: str = "v1"

    @computed_field
    @property
    def total_penalty(self) -> float:
        return (
            30 * self.future_work_deficit
            + 25 * self.disruption
            + 20 * self.preference_mismatch
            + 15 * self.fragmentation
            + 10 * self.completion_delay
        )

    @computed_field
    @property
    def quality(self) -> float:
        return 1 - self.total_penalty / 100


class SolverMetadata(Contract):
    runtime_ms: float = Field(default=0, ge=0)
    budget_ms: int | None = Field(default=None, ge=0)
    seed: int | None = None
    variable_count: int = Field(default=0, ge=0)
    constraint_count: int = Field(default=0, ge=0)
    reason_code: str | None = None


class Candidate(Contract):
    snapshot_hash: str
    planning_revision: int = Field(ge=0)
    status: Literal["OPTIMAL", "FEASIBLE", "INFEASIBLE", "UNKNOWN", "MODEL_INVALID"]
    source_policy: str
    blocks: tuple[Block, ...] = ()
    constraint_report: tuple[Violation, ...] = ()
    score: Score | None = None
    solver_metadata: SolverMetadata = Field(default_factory=SolverMetadata)


class RoundingLoss(Contract):
    field: str
    original: Instant
    rounded: Instant
    seconds: float = Field(ge=0)


class OriginalTimeInput(Contract):
    field: str
    value: str
    timezone: str
    fold: Literal[0, 1] | None = None


class InputSnapshot(Contract):
    id: UUID
    snapshot_hash: str
    owner_id: UUID
    planning_revision: int = Field(ge=0)
    reference_now: Instant
    timezone: str
    slot_origin: Instant
    horizon_start: Instant
    horizon_end: Instant
    horizon_start_slot: int
    horizon_end_slot: int
    tasks: tuple[TaskSpec, ...] = ()
    dependencies: tuple[Dependency, ...] = ()
    availability: tuple[SlotRange, ...] = ()
    busy_slot_ranges: tuple[SlotRange, ...] = ()
    protected_blocks: tuple[Block, ...] = ()
    preferred_windows: tuple[SlotRange, ...] = ()
    prior_candidate: Candidate | None = None
    prior_active_candidate_id: UUID | None = None
    objective_version: str = "v1"
    rounding_losses: tuple[RoundingLoss, ...] = ()
    original_time_inputs: tuple[OriginalTimeInput, ...] = ()


class BlockMove(Contract):
    old: Block
    new: Block
    reason_codes: tuple[str, ...] = ()


class PlanDiff(Contract):
    retained: tuple[Block, ...] = ()
    moved: tuple[BlockMove, ...] = ()
    added: tuple[Block, ...] = ()
    removed: tuple[Block, ...] = ()
    reason_codes: tuple[str, ...] = ()


class Proposal(Contract):
    id: UUID
    owner_id: UUID
    candidate: Candidate
    state: Literal["CURRENT", "SUPERSEDED"] = "CURRENT"
    activated_at: Instant | None = None
    publication_state: str = "NOT_REQUESTED"


class EvidenceSpan(Contract):
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    text: str


class ExtractedField(Contract):
    name: str
    value: Scalar = None
    label: Literal["explicit", "inferred", "unknown"]
    evidence: tuple[EvidenceSpan, ...] = ()


class ExtractionProposal(Contract):
    id: UUID
    schema_version: str
    reference_now: Instant
    timezone: str
    fields: tuple[ExtractedField, ...] = ()
    unresolved_questions: tuple[str, ...] = ()


class FeatureVector(Contract):
    version: str
    names: tuple[str, ...]
    values: tuple[float, ...]

    @model_validator(mode="after")
    def ordered_finite_features(self):
        if len(self.names) != len(self.values) or len(set(self.names)) != len(self.names):
            raise ValueError("feature names must be unique and match values in order")
        return self


class ModelManifest(Contract):
    model_id: str
    version: str
    feature_version: str
    feature_names: tuple[str, ...]
    feature_hash: str
    data_hash: str
    code_hash: str
    artifact_digest: str
    policy_parameters: Mapping[str, Scalar] = Field(default_factory=dict)

    @field_validator("policy_parameters", mode="after")
    @classmethod
    def freeze_parameters(cls, value):
        return MappingProxyType(dict(value))

    @field_serializer("policy_parameters")
    def serialize_parameters(self, value):
        return dict(value)


class RoutingDecision(Contract):
    action: Literal["ACCEPT_VALID_GREEDY", "RUN_CP_SAT"]
    model_id: str | None = None
    model_version: str | None = None
    policy_version: str
    reason_codes: tuple[str, ...] = ()
