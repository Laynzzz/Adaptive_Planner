"""One owner-state lock serializes all planning-input mutations."""

import hashlib
import json
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from planner.api.errors import APIError
from planner.db.models import AuditEvent, CommandReceipt, PendingReplan, PlanningState


def execute_command(engine, owner_id, operation, key, payload, clock, mutate, status=200):
    if not key or len(key) > 128:
        raise APIError(
            "IDEMPOTENCY_REQUIRED", 400, "Supply an Idempotency-Key of 1 to 128 characters."
        )
    body_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    try:
        with Session(engine) as db, db.begin():
            state = db.scalar(
                select(PlanningState)
                .where(PlanningState.owner_id == owner_id)
                .with_for_update(nowait=True)
            )
            now = clock()
            receipt = db.get(CommandReceipt, (owner_id, operation, key))
            if receipt is not None and receipt.expires_at > now:
                if receipt.body_hash != body_hash:
                    raise APIError(
                        "IDEMPOTENCY_CONFLICT", 409, "This key was used for different input."
                    )
                return receipt.response, receipt.status_code
            if receipt is not None:
                db.delete(receipt)
                db.flush()
            if state.revision != payload["expected_revision"]:
                raise APIError("STALE_REVISION", 409, "Inputs changed. Refresh before retrying.")
            response = mutate(db)
            state.revision += 1
            response["revision"] = state.revision
            db.add(AuditEvent(owner_id=owner_id, operation=operation, revision=state.revision))
            db.add(
                CommandReceipt(
                    owner_id=owner_id,
                    operation=operation,
                    key=key,
                    body_hash=body_hash,
                    response=response,
                    status_code=status,
                    expires_at=now + timedelta(days=7),
                )
            )
            db.execute(
                insert(PendingReplan)
                .values(
                    owner_id=owner_id,
                    desired_revision=state.revision,
                    enqueued_at=now,
                    updated_at=now,
                    explicit=False,
                )
                .on_conflict_do_update(
                    index_elements=["owner_id"],
                    set_={"desired_revision": state.revision, "updated_at": now},
                )
            )
            return response, status
    except OperationalError as error:
        if getattr(error.orig, "sqlstate", None) == "55P03":
            raise APIError(
                "COMMAND_IN_PROGRESS", 409, "Another command is in progress.", retryable=True
            ) from None
        raise
