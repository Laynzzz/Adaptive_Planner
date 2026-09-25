"""RFC 5545 UTC export with stable identities and octet-aware folding."""

from datetime import UTC, datetime
from uuid import UUID

from planner.domain.contracts import Candidate


def _escape(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\n", "\\n")
        .replace(";", "\\;")
        .replace(",", "\\,")
    )


def _fold(line: str) -> str:
    lines, current = [], ""
    for character in line:
        if len((current + character).encode("utf-8")) > 75:
            lines.append(current)
            current = " "
        current += character
    return "\r\n".join([*lines, current])


def _instant(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("Calendar instants must have an explicit timezone.")
    return value.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def export_ics(candidate: Candidate, titles: dict[UUID, str], *, generated_at: datetime) -> str:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Adaptive Planner//EN",
        "CALSCALE:GREGORIAN",
    ]
    for block in sorted(candidate.blocks, key=lambda b: (b.start, str(b.id))):
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{block.id}@adaptive-planner.local",
                f"DTSTAMP:{_instant(generated_at)}",
                f"DTSTART:{_instant(block.start)}",
                f"DTEND:{_instant(block.end)}",
                f"SUMMARY:{_escape(titles.get(block.task_id, 'Planned work'))}",
                "END:VEVENT",
            ]
        )
    return "\r\n".join(_fold(line) for line in [*lines, "END:VCALENDAR"]) + "\r\n"
