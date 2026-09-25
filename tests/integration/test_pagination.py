from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import event, select
from sqlalchemy.orm import Session

from planner.db.models import DependencyEdge, Task
from planner.db.queries import task_page_data


def seed_tasks(app, api, count=5):
    owner = api.get("/api/v1/me").json()["id"]
    from uuid import UUID

    owner = UUID(owner)
    with Session(app.state.engine) as db, db.begin():
        tasks = [
            Task(
                id=uuid4(),
                owner_id=owner,
                title=f"Page {i}",
                remaining_minutes=30,
                priority=3,
                state="TODO",
                created_at=datetime(2026, 9, 25, tzinfo=UTC),
            )
            for i in range(count)
        ]
        db.add_all(tasks)
        db.flush()
        db.add_all(
            DependencyEdge(owner_id=owner, predecessor_id=tasks[0].id, successor_id=t.id)
            for t in tasks[1:]
        )
    return owner


def test_task_page_batches_dependency_reads_once(api_a, app):
    owner = seed_tasks(app, api_a)
    statements = []

    def capture(connection, cursor, statement, parameters, context, executemany):
        if "dependency_edges" in statement:
            statements.append(statement)

    with Session(app.state.engine) as db:
        tasks = db.scalars(select(Task).where(Task.owner_id == owner)).all()
        event.listen(app.state.engine, "before_cursor_execute", capture)
        try:
            result = task_page_data(db, tasks, revision=7)
        finally:
            event.remove(app.state.engine, "before_cursor_execute", capture)
    assert len(statements) == 1
    assert len(result) == 5
    assert all(item["revision"] == 7 for item in result)
    assert sum(bool(item["predecessor_ids"]) for item in result) == 4


def test_keyset_pages_reject_owner_filter_changes_and_do_not_repeat(api_a, api_b, app):
    seed_tasks(app, api_a)
    first = api_a.get("/api/v1/tasks?limit=2&state=TODO").json()
    cursor = first["next_cursor"]
    assert cursor
    assert api_b.get("/api/v1/tasks", params={"cursor": cursor, "state": "TODO"}).status_code == 400
    assert api_a.get("/api/v1/tasks", params={"cursor": cursor, "state": "DONE"}).status_code == 400
    second = api_a.get(
        "/api/v1/tasks", params={"cursor": cursor, "state": "TODO", "limit": 2}
    ).json()
    assert set(item["id"] for item in first["items"]).isdisjoint(
        item["id"] for item in second["items"]
    )
