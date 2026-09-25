"""Public request and response schemas; ownership and derived values are server assigned."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from planner.domain.contracts import Deadline


class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LocalTime(Schema):
    local: str
    timezone: str = "UTC"
    fold: Literal[0, 1] | None = None


InstantInput = str | LocalTime


class RevisionCommand(Schema):
    expected_revision: int = Field(ge=0, strict=True)


class TaskFields(Schema):
    title: str = Field(min_length=1, max_length=500)
    remaining_minutes: int = Field(ge=0, le=2147483647, strict=True)
    deadline: Deadline | None = None
    release_at: InstantInput | None = None
    priority: int = Field(default=3, ge=1, le=5, strict=True)
    splittable: bool = True
    min_block_slots: int = Field(default=2, ge=1, le=12, strict=True)
    max_block_slots: int = Field(default=12, ge=2, le=12, strict=True)
    short_final_allowed: bool = False

    @model_validator(mode="after")
    def valid_lengths(self):
        if self.min_block_slots > self.max_block_slots or not self.title.strip():
            raise ValueError("Invalid title or block lengths")
        return self


class TaskCreate(TaskFields, RevisionCommand):
    pass


class TaskPatch(RevisionCommand):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    remaining_minutes: int | None = Field(default=None, ge=0, le=2147483647, strict=True)
    deadline: Deadline | None = None
    release_at: InstantInput | None = None
    priority: int | None = Field(default=None, ge=1, le=5, strict=True)
    splittable: bool | None = None
    min_block_slots: int | None = Field(default=None, ge=1, le=12, strict=True)
    max_block_slots: int | None = Field(default=None, ge=2, le=12, strict=True)
    short_final_allowed: bool | None = None


class TaskResponse(TaskFields):
    id: UUID
    owner_id: UUID
    state: Literal["TODO", "IN_PROGRESS", "DONE", "CANCELLED"]
    required_slots: int
    revision: int
    created_at: datetime
    predecessor_ids: list[UUID] = []


class TaskPage(Schema):
    items: list[TaskResponse]
    next_cursor: str | None
    revision: int


class MeResponse(Schema):
    id: UUID
    name: str
    timezone: str
    revision: int
    csrf_token: str
    capabilities: list[str]


class Interval(Schema):
    start: InstantInput
    end: InstantInput


class AvailabilityCommand(RevisionCommand):
    windows: list[Interval] = Field(max_length=400)


class AvailabilityResponse(Schema):
    windows: list[Interval]
    timezone: str
    revision: int


class FixedEventCreate(Interval, RevisionCommand):
    title: str = Field(min_length=1, max_length=500)


class FixedEventPatch(RevisionCommand):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    start: InstantInput | None = None
    end: InstantInput | None = None


class FixedEventResponse(Interval):
    id: UUID
    title: str
    revision: int


class FixedEventPage(Schema):
    items: list[FixedEventResponse]
    revision: int


class DependencyCommand(RevisionCommand):
    predecessor_id: UUID


class RevisionResponse(Schema):
    revision: int
