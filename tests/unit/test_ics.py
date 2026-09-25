from datetime import UTC, datetime

from tests.unit.test_validator import block, candidate, snapshot, task


def test_ics_has_utc_instants_stable_uid_and_escaped_text():
    from planner.calendar.ics import export_ics

    a = task().model_copy(update={"title": "Read, write; reflect\nNext step"})
    s = snapshot([a])
    c = candidate(s, [block(a, 36, 40)])
    content = export_ics(c, {a.id: a.title}, generated_at=datetime(2026, 9, 25, tzinfo=UTC))
    assert "DTSTART:20260925T090000Z\r\n" in content
    assert "SUMMARY:Read\\, write\\; reflect\\nNext step\r\n" in content
    assert f"UID:{c.blocks[0].id}@adaptive-planner.local\r\n" in content
    later = export_ics(c, {a.id: a.title}, generated_at=datetime(2026, 9, 26, tzinfo=UTC))
    assert next(x for x in content.splitlines() if x.startswith("UID:")) in later
    assert content.endswith("END:VCALENDAR\r\n")


def test_ics_folds_utf8_at_75_octets_without_splitting_characters():
    from planner.calendar.ics import export_ics

    s = snapshot()
    c = candidate(s, [block(s.tasks[0], 0, 2)])
    content = export_ics(c, {s.tasks[0].id: "学习" * 100}, generated_at=s.reference_now)
    assert all(len(line.encode("utf-8")) <= 75 for line in content.split("\r\n"))
    assert "SUMMARY:" + "学习" * 100 in content.replace("\r\n ", "")
