"""Durable calendar I/O queue consumed separately from CPU solver work."""

import logging
import os
import signal
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, time, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import and_, exists, or_, select
from sqlalchemy.orm import Session

from planner.calendar.fake import DurableMockProvider
from planner.calendar.oauth import CalendarConfig, google_provider
from planner.calendar.provider import ProviderError
from planner.calendar.publish import publish_active
from planner.calendar.reconcile import canonical, conflict, owned
from planner.calendar.sync import synchronize
from planner.db.calendar_models import BlockEventMapping, CalendarConnection
from planner.db.job_models import ProposalRecord
from planner.db.models import Identity, PlanningState

CALENDAR_POOL_SIZE = 2


def config_from_environment():
    return CalendarConfig(
        live_enabled=os.environ.get("PLANNER_CALENDAR_LIVE_ENABLED", "").lower() == "true",
        client_id=os.environ.get("PLANNER_CALENDAR_CLIENT_ID", ""),
        client_secret=os.environ.get("PLANNER_CALENDAR_CLIENT_SECRET", ""),
        encryption_key=os.environ.get("PLANNER_CALENDAR_ENCRYPTION_KEY", ""),
        redirect_uri=os.environ.get(
            "PLANNER_CALENDAR_REDIRECT_URI", "http://127.0.0.1:8000/api/v1/calendar/callback"
        ),
    )


def default_provider_factory(engine, config, clock):
    def factory(owner):
        with Session(engine) as db:
            connection = db.get(CalendarConnection, owner)
            provider_name = connection.provider
        if provider_name == "MOCK":
            return DurableMockProvider(engine, owner)
        return google_provider(engine, owner, config, clock)

    return factory


def _disconnect(engine, owner, provider, token, clock):
    with Session(engine) as db:
        connection = db.get(CalendarConnection, owner)
        calendar_id, keep = connection.calendar_id, connection.keep_remote_events
        rows = [
            (m.block_id, m.event_id, m.published_payload)
            for m in db.scalars(
                select(BlockEventMapping).where(BlockEventMapping.owner_id == owner)
            )
        ]
    if not keep:
        for block_id, remote_id, published in rows:
            with Session(engine) as db:
                current = db.get(CalendarConnection, owner)
                if current.state != "DISCONNECTING" or current.io_lease_token != token:
                    return "SUPERSEDED"
            try:
                remote = provider.get_event(calendar_id, remote_id)
            except ProviderError as error:
                if error.kind == "NOT_FOUND":
                    continue
                raise
            if not owned(remote.payload, owner, block_id) or canonical(remote.payload) != canonical(
                published
            ):
                with Session(engine) as db, db.begin():
                    conflict(
                        db,
                        db.get(BlockEventMapping, (owner, block_id)),
                        "DISCONNECT_MANUAL_EDIT",
                        remote.payload,
                        clock(),
                    )
                continue
            # Conditional delete prevents deleting an edit made after this read.
            provider.delete_event(calendar_id, remote_id, etag=remote.etag)
    revoke_error = None
    if hasattr(provider, "revoke_credentials"):
        try:
            provider.revoke_credentials()
        except ProviderError:
            revoke_error = "REVOCATION_UNCONFIRMED"
    with Session(engine) as db, db.begin():
        connection = db.scalar(
            select(CalendarConnection).where(CalendarConnection.owner_id == owner).with_for_update()
        )
        if connection.io_lease_token != token or connection.state != "DISCONNECTING":
            return "SUPERSEDED"
        connection.state = "DISCONNECTED"
        connection.encrypted_refresh_token = None
        connection.sync_request = connection.publish_request = None
        connection.oauth_state_hash = None
        connection.last_error = revoke_error
    return "DISCONNECTED"


def run_calendar_once(engine, provider_factory=None, *, clock):
    """Claim at most one owner; safe to invoke from a bounded I/O executor."""
    provider_factory = provider_factory or default_provider_factory(
        engine, config_from_environment(), clock
    )
    token = uuid4()
    with Session(engine) as db, db.begin():
        pending_plan = exists().where(
            PlanningState.owner_id == CalendarConnection.owner_id,
            PlanningState.active_proposal_id == ProposalRecord.id,
            ProposalRecord.publication_state == "PENDING_CONNECTION",
        )
        connection = db.scalar(
            select(CalendarConnection)
            .where(
                CalendarConnection.state.in_(["CONNECTED", "DISCONNECTING"]),
                or_(
                    CalendarConnection.io_lease_until.is_(None),
                    CalendarConnection.io_lease_until <= clock(),
                ),
                or_(CalendarConnection.retry_at.is_(None), CalendarConnection.retry_at <= clock()),
                or_(
                    CalendarConnection.state == "DISCONNECTING",
                    CalendarConnection.sync_request.is_not(None),
                    CalendarConnection.publish_request.is_not(None),
                    and_(CalendarConnection.state == "CONNECTED", pending_plan),
                ),
            )
            .order_by(
                CalendarConnection.last_sync_at.asc().nulls_first(), CalendarConnection.owner_id
            )
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if not connection:
            return False
        owner, state = connection.owner_id, connection.state
        connection.io_lease_token, connection.io_lease_until = (
            token,
            clock() + timedelta(seconds=120),
        )
        if (
            connection.publish_request is None
            and state == "CONNECTED"
            and db.scalar(
                select(ProposalRecord.id)
                .join(PlanningState, PlanningState.active_proposal_id == ProposalRecord.id)
                .where(
                    PlanningState.owner_id == owner,
                    ProposalRecord.publication_state == "PENDING_CONNECTION",
                )
            )
        ):
            connection.publish_request = uuid4()
        sync_request, publish_request = connection.sync_request, connection.publish_request
        timezone = db.get(Identity, owner).timezone
    sync_state = publish_state = None
    try:
        provider = provider_factory(owner)
        if state == "DISCONNECTING":
            publish_state = _disconnect(engine, owner, provider, token, clock)
        else:
            if sync_request:
                local_date = clock().astimezone(ZoneInfo(timezone)).date()
                start = datetime.combine(local_date, time.min, ZoneInfo(timezone)).astimezone(UTC)
                end = datetime.combine(
                    local_date + timedelta(days=14), time.min, ZoneInfo(timezone)
                ).astimezone(UTC)
                sync_state = synchronize(
                    engine, owner, provider, now=clock(), window_start=start, window_end=end
                ).state
            if publish_request:
                publish_state = publish_active(engine, owner, provider, clock=clock).state
    except ProviderError as error:
        sync_state = publish_state = error.kind
    finally:
        with Session(engine) as db, db.begin():
            connection = db.scalar(
                select(CalendarConnection)
                .where(CalendarConnection.owner_id == owner)
                .with_for_update()
            )
            if connection.io_lease_token == token:
                connection.io_lease_until = connection.io_lease_token = None
                terminal = {
                    "SYNCED",
                    "PUBLISHED",
                    "NO_ACTIVE_PLAN",
                    "CONFLICT",
                    "DISCONNECTED",
                    "NEEDS_REAUTH",
                    "AUTHENTICATION_REQUIRED",
                    "PERMANENT_VALIDATION",
                }
                if connection.sync_request == sync_request and sync_state in terminal:
                    connection.sync_request = None
                if connection.publish_request == publish_request and publish_state in terminal:
                    connection.publish_request = None
                results = {sync_state, publish_state} - {None}
                if results - terminal:
                    connection.retry_at = clock() + timedelta(seconds=5)
                    connection.last_error = next(iter(sorted(results - terminal)))
                if (
                    "AUTHENTICATION_REQUIRED" in results
                    and connection.state == "CONNECTED"
                    and connection.sync_request in (None, sync_request)
                    and connection.publish_request in (None, publish_request)
                ):
                    connection.state = "NEEDS_REAUTH"
                    connection.last_error = "AUTHENTICATION_REQUIRED"
    return True


def serve(engine, stop, *, clock, provider_factory=None):
    with ThreadPoolExecutor(max_workers=CALENDAR_POOL_SIZE) as pool:
        futures = set()
        while not stop.is_set():
            for future in tuple(futures):
                if future.done():
                    try:
                        future.result()
                    except Exception as error:
                        logging.error(
                            "Calendar worker interrupted; durable requests remain (%s)",
                            type(error).__name__,
                        )
                    futures.remove(future)
            while len(futures) < CALENDAR_POOL_SIZE and not stop.is_set():
                futures.add(pool.submit(run_calendar_once, engine, provider_factory, clock=clock))
            stop.wait(0.25)


def main():
    from planner.db.session import create_db_engine
    from planner.settings import Settings

    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    engine = create_db_engine(Settings())
    try:
        serve(engine, stop, clock=lambda: datetime.now(UTC))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
