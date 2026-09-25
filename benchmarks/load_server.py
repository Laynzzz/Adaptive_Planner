"""Frozen load-server factory; baseline restores the previous correct N+1 projection."""

import os


def create_app():
    from planner.app import create_app as factory

    if os.environ.get("PLANNER_LOAD_PHASE") == "baseline":
        import planner.api.routes as routes
        from planner.db.repositories import task_data

        routes.task_page_data = lambda db, tasks, revision=0: [
            task_data(db, task, revision) for task in tasks
        ]
    return factory()
