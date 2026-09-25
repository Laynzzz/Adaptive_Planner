"""Stage provider pages durably; expose a complete generation under the owner lock."""

from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from planner.calendar.provider import ProviderError, parse_event
from planner.calendar.reconcile import canonical, conflict, digest, owned
from planner.db.calendar_models import (
    BlockEventMapping,
    CalendarConnection,
    EventMirror,
    StagedEvent,
    SyncGeneration,
)
from planner.db.job_models import ProposalRecord
from planner.db.models import AuditEvent, PlanningState
from planner.jobs.coalescing import enqueue_in_transaction
from planner.observability.runtime import traced_owner_work


@dataclass(frozen=True)
class SyncResult:
    state: str
    changed: bool = False


def calendar_inputs(db, owner_id):
    connection = db.get(CalendarConnection, owner_id)
    if not connection or connection.state in ("DISCONNECTED", "DISCONNECTING"):
        return [], [], set()
    state = db.get(PlanningState, owner_id)
    active = db.get(ProposalRecord, state.active_proposal_id) if state.active_proposal_id else None
    active_ids = {b["id"] for b in active.candidate["blocks"]} if active else set()
    mappings = {
        m.event_id: m
        for m in db.scalars(select(BlockEventMapping).where(BlockEventMapping.owner_id == owner_id))
    }
    busy, protected, suppressed = [], [], set()
    off_grid_ids = set()
    for mapping in mappings.values():
        if mapping.state == "IGNORED":
            suppressed.add(mapping.block_id)
        elif mapping.commitment:
            instants = [
                datetime.fromisoformat(mapping.commitment[field]) for field in ("start", "end")
            ]
            off_grid = any(value.timestamp() % 900 for value in instants)
            if off_grid:
                off_grid_ids.add(mapping.block_id)
            protected.append(
                dict(
                    mapping.commitment,
                    id=mapping.block_id,
                    owner_id=owner_id,
                    task_id=mapping.task_id,
                    locked=True,
                    source="CALENDAR_OFF_GRID" if off_grid else "CALENDAR",
                )
            )
    for mirror in db.scalars(select(EventMirror).where(EventMirror.owner_id == owner_id)):
        event = parse_event(mirror.payload)
        interval = event.interval()
        if not interval:
            continue
        mapping = mappings.get(event.id)
        if (
            mapping
            and mapping.block_id not in off_grid_ids
            and owned(event.payload, owner_id, mapping.block_id)
        ):
            if mapping.commitment or (
                str(mapping.block_id) in active_ids and mapping.state != "IGNORED"
            ):
                continue
        busy.append({"start": interval[0].isoformat(), "end": interval[1].isoformat()})
    return busy, protected, suppressed


def _effective(db, owner):
    busy, protected, suppressed = calendar_inputs(db, owner)
    merged = []
    for start, end in sorted((x["start"], x["end"]) for x in busy):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(end, merged[-1][1])
        else:
            merged.append([start, end])
    return digest(
        [
            merged,
            sorted((str(x["id"]), x["start"], x["end"]) for x in protected),
            sorted(map(str, suppressed)),
        ]
    )


@traced_owner_work("sync")
def synchronize(
    engine, owner_id, provider, *, now: datetime, window_start: datetime, window_end: datetime
) -> SyncResult:
    for rebuild in range(2):
        with Session(engine) as db, db.begin():
            connection = db.get(CalendarConnection, owner_id)
            if not connection or connection.state != "CONNECTED":
                return SyncResult(connection.state if connection else "DISCONNECTED")
            calendar_id, base = connection.calendar_id, connection.generation
            full = bool(
                rebuild
                or not connection.sync_token
                or connection.window_start != window_start
                or connection.window_end != window_end
            )
            cursor = None if full else connection.sync_token
            generation_id = uuid4()
            db.add(
                SyncGeneration(
                    id=generation_id,
                    owner_id=owner_id,
                    base_generation=base,
                    full=full,
                    created_at=now,
                )
            )
        try:
            page_token, seen = None, set()
            while True:
                page = provider.list_events(
                    calendar_id,
                    sync_token=cursor,
                    page_token=page_token,
                    time_min=window_start,
                    time_max=window_end,
                )
                with Session(engine) as db, db.begin():
                    for event in page.events:
                        # Reject malformed intervals before exposing the generation.
                        event.interval()
                        db.execute(
                            insert(StagedEvent)
                            .values(
                                owner_id=owner_id,
                                generation_id=generation_id,
                                event_id=event.id,
                                payload=event.payload,
                            )
                            .on_conflict_do_update(
                                index_elements=["owner_id", "generation_id", "event_id"],
                                set_={"payload": event.payload},
                            )
                        )
                page_token = page.next_page_token
                if not page_token:
                    if not page.next_sync_token:
                        raise ProviderError("PERMANENT_VALIDATION")
                    break
                if page_token in seen or len(seen) >= 1000:
                    raise ProviderError("PERMANENT_VALIDATION")
                seen.add(page_token)
            with Session(engine) as db, db.begin():
                state = db.scalar(
                    select(PlanningState)
                    .where(PlanningState.owner_id == owner_id)
                    .with_for_update()
                )
                connection = db.scalar(
                    select(CalendarConnection)
                    .where(CalendarConnection.owner_id == owner_id)
                    .with_for_update()
                )
                generation = db.get(SyncGeneration, generation_id)
                if (
                    connection.state != "CONNECTED"
                    or connection.calendar_id != calendar_id
                    or connection.generation != base
                ):
                    generation.state = "SUPERSEDED"
                    return SyncResult("SUPERSEDED")
                before = _effective(db, owner_id)
                if full:
                    db.execute(delete(EventMirror).where(EventMirror.owner_id == owner_id))
                for staged in db.scalars(
                    select(StagedEvent).where(StagedEvent.generation_id == generation_id)
                ):
                    db.execute(
                        insert(EventMirror)
                        .values(owner_id=owner_id, event_id=staged.event_id, payload=staged.payload)
                        .on_conflict_do_update(
                            index_elements=["owner_id", "event_id"],
                            set_={"payload": staged.payload},
                        )
                    )
                mirrors = {
                    e.event_id: e.payload
                    for e in db.scalars(select(EventMirror).where(EventMirror.owner_id == owner_id))
                }
                for mapping in db.scalars(
                    select(BlockEventMapping).where(BlockEventMapping.owner_id == owner_id)
                ):
                    if (
                        mapping.state in ("IGNORED", "DELETED", "PENDING")
                        or mapping.published_payload is None
                    ):
                        continue
                    remote = mirrors.get(mapping.event_id)
                    if remote is None and not full:
                        continue
                    old_interval = parse_event(mapping.published_payload).interval()
                    if (
                        remote is None
                        and old_interval
                        and not (old_interval[0] < window_end and old_interval[1] > window_start)
                    ):
                        continue
                    if remote is None or remote.get("status") == "cancelled":
                        conflict(db, mapping, "MANUAL_DELETION", remote, now)
                    elif not owned(remote, owner_id, mapping.block_id):
                        conflict(db, mapping, "OWNERSHIP_MISMATCH", remote, now)
                    elif (
                        canonical(remote) != canonical(mapping.published_payload)
                        or remote.get("etag", "") != mapping.etag
                    ):
                        conflict(db, mapping, "MANUAL_EDIT", remote, now)
                    else:
                        mapping.etag = remote.get("etag", mapping.etag)
                db.flush()
                after = _effective(db, owner_id)
                changed = before != after
                if changed:
                    state.revision += 1
                    state.calendar_revision += 1
                    db.add(
                        AuditEvent(
                            owner_id=owner_id, operation="calendar.sync", revision=state.revision
                        )
                    )
                    enqueue_in_transaction(db, owner_id, now=now)
                connection.sync_token, connection.generation = page.next_sync_token, base + 1
                connection.window_start, connection.window_end = window_start, window_end
                connection.busy_hash, connection.last_sync_at, connection.last_error = (
                    after,
                    now,
                    None,
                )
                generation.state = "APPLIED"
                db.execute(delete(StagedEvent).where(StagedEvent.generation_id == generation_id))
                return SyncResult("SYNCED", changed)
        except ProviderError as error:
            with Session(engine) as db, db.begin():
                db.get(SyncGeneration, generation_id).state = "FAILED"
                connection = db.scalar(
                    select(CalendarConnection)
                    .where(CalendarConnection.owner_id == owner_id)
                    .with_for_update()
                )
                if (
                    connection.state != "CONNECTED"
                    or connection.calendar_id != calendar_id
                    or connection.generation != base
                ):
                    return SyncResult("SUPERSEDED")
                connection.last_error = error.kind
                if error.kind == "AUTHENTICATION_REQUIRED":
                    connection.state = "NEEDS_REAUTH"
            if error.kind == "INVALID_SYNC_TOKEN" and not rebuild:
                continue
            return SyncResult(error.kind)
    return SyncResult("INVALID_SYNC_TOKEN")
