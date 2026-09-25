from datetime import UTC, datetime


def test_timezone_change_requires_preview_and_preserves_absolute_commitments(api_a, api_b, app):
    app.state.clock = lambda: datetime(2026, 9, 25, 9, tzinfo=UTC)
    event = api_a.post(
        "/api/v1/fixed-events",
        json={
            "title": "Class",
            "start": "2026-09-26T09:00",
            "end": "2026-09-26T10:00",
            "expected_revision": 0,
        },
    ).json()
    task = api_a.post(
        "/api/v1/tasks",
        json={
            "title": "Date task",
            "remaining_minutes": 60,
            "deadline": {"kind": "DATE", "value": "2026-09-26"},
            "expected_revision": event["revision"],
        },
    ).json()
    preview = api_a.get(
        "/api/v1/settings/timezone-preview", params={"timezone": "America/New_York"}
    )
    assert preview.status_code == 200, preview.text
    data = preview.json()
    assert api_a.get("/api/v1/me").json()["timezone"] == "UTC"
    assert data["date_deadlines"][0]["old_bound"] == "2026-09-27T00:00:00+00:00"
    assert data["date_deadlines"][0]["new_bound"] == "2026-09-27T04:00:00+00:00"
    command = {
        "timezone": "America/New_York",
        "expected_revision": task["revision"],
        "preview_hash": data["preview_hash"],
        "confirmed": True,
    }
    denied = api_a.put("/api/v1/settings/timezone", json={**command, "confirmed": False})
    assert denied.status_code == 422
    assert (
        api_b.put("/api/v1/settings/timezone", json={**command, "expected_revision": 0}).status_code
        == 409
    )
    saved = api_a.put("/api/v1/settings/timezone", json=command)
    assert saved.status_code == 200, saved.text
    assert api_a.get("/api/v1/me").json()["timezone"] == "America/New_York"
    fixed = api_a.get("/api/v1/fixed-events").json()["items"][0]
    assert datetime.fromisoformat(fixed["start"]) == datetime(2026, 9, 26, 9, tzinfo=UTC)
    task_after = api_a.get("/api/v1/tasks").json()["items"][0]
    assert task_after["deadline"]["value"] == "2026-09-26"
    assert task_after["deadline"]["timezone"] == "America/New_York"


def test_stale_timezone_preview_cannot_overwrite_new_inputs(api_a):
    preview = api_a.get("/api/v1/settings/timezone-preview", params={"timezone": "Asia/Shanghai"})
    assert preview.status_code == 200, preview.text
    task = api_a.post(
        "/api/v1/tasks",
        json={"title": "New input", "remaining_minutes": 60, "expected_revision": 0},
    ).json()
    rejected = api_a.put(
        "/api/v1/settings/timezone",
        json={
            "timezone": "Asia/Shanghai",
            "expected_revision": task["revision"],
            "preview_hash": preview.json()["preview_hash"],
            "confirmed": True,
        },
    )
    assert rejected.status_code == 409
    assert api_a.get("/api/v1/me").json()["timezone"] == "UTC"


def test_timezone_rejects_forbidden_weekday_atomically(api_a, app):
    app.state.clock = lambda: datetime(2026, 9, 25, 9, tzinfo=UTC)
    task = api_a.post(
        "/api/v1/tasks",
        json={
            "title": "Saturday UTC",
            "remaining_minutes": 60,
            "deadline": {"kind": "TIMESTAMP", "value": "2026-09-26T01:00Z"},
            "expected_revision": 0,
        },
    ).json()
    rule = api_a.post(
        "/api/v1/weekday-rules",
        json={"kind": "HARD_NO_DEADLINE", "weekday": 4, "expected_revision": task["revision"]},
    ).json()
    preview = api_a.get(
        "/api/v1/settings/timezone-preview", params={"timezone": "America/New_York"}
    ).json()
    result = api_a.put(
        "/api/v1/settings/timezone",
        json={
            "timezone": preview["timezone"],
            "preview_hash": preview["preview_hash"],
            "expected_revision": rule["revision"],
            "confirmed": True,
        },
    )
    assert result.status_code == 409 and result.json()["code"] == "DEADLINE_WEEKDAY_FORBIDDEN"
    me = api_a.get("/api/v1/me").json()
    assert (me["timezone"], me["revision"]) == ("UTC", rule["revision"])


def test_dst_date_preview_and_explicit_times_are_preserved(api_a, app):
    app.state.clock = lambda: datetime(2026, 10, 30, 9, tzinfo=UTC)
    date_task = api_a.post(
        "/api/v1/tasks",
        json={
            "title": "DST day",
            "remaining_minutes": 60,
            "deadline": {"kind": "DATE", "value": "2026-11-01"},
            "expected_revision": 0,
        },
    ).json()
    timestamp_task = api_a.post(
        "/api/v1/tasks",
        json={
            "title": "Absolute time",
            "remaining_minutes": 60,
            "deadline": {
                "kind": "TIMESTAMP",
                "value": "2026-11-01T23:00",
                "timezone": "Asia/Tokyo",
            },
            "release_at": "2026-11-01T09:00",
            "expected_revision": date_task["revision"],
        },
    ).json()
    availability = api_a.put(
        "/api/v1/availability",
        json={
            "windows": [{"start": "2026-11-01T09:00", "end": "2026-11-01T12:00"}],
            "expected_revision": timestamp_task["revision"],
        },
    ).json()
    preview = api_a.get(
        "/api/v1/settings/timezone-preview", params={"timezone": "America/New_York"}
    ).json()
    assert preview["date_deadlines"][0]["new_bound"] == "2026-11-02T05:00:00+00:00"
    command = {
        "timezone": preview["timezone"],
        "preview_hash": preview["preview_hash"],
        "expected_revision": availability["revision"],
        "confirmed": True,
    }
    headers = {"Idempotency-Key": "timezone-idempotent"}
    saved = api_a.put("/api/v1/settings/timezone", json=command, headers=headers)
    assert saved.status_code == 200
    assert (
        api_a.put("/api/v1/settings/timezone", json=command, headers=headers).json() == saved.json()
    )
    tasks = {t["title"]: t for t in api_a.get("/api/v1/tasks").json()["items"]}
    assert tasks["Absolute time"]["deadline"]["value"] == "2026-11-01T14:00:00+00:00"
    assert tasks["Absolute time"]["release_at"] == "2026-11-01T09:00:00+00:00"
    assert (
        api_a.get("/api/v1/availability").json()["windows"][0]["start"]
        == "2026-11-01T09:00:00+00:00"
    )
    assert (
        api_a.get("/api/v1/settings/timezone-preview", params={"timezone": "Not/AZone"}).status_code
        == 422
    )
