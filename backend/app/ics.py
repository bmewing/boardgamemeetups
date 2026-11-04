"""Writing iCalendar files (RFC 5545): one date to download, or someone's whole feed."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

PRODID = "-//Board Game Meetups//EN"
MAX_LINE_OCTETS = 75
# Feeds ask calendar apps to check back hourly; most check less often whatever we say.
REFRESH = "PT1H"


@dataclass(frozen=True)
class Event:
    uid: str
    starts_at: datetime
    duration: timedelta
    summary: str
    updated_at: datetime
    sequence: int = 0
    location: str | None = None
    description: str | None = None
    url: str | None = None
    cancelled: bool = False


def escape(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\n")
        .replace("\n", "\\n")
    )


def fold(line: str) -> str:
    """Split a line longer than 75 octets, never inside a UTF-8 character. Each
    continuation starts with a space, which counts toward its 75."""
    data = line.encode()
    if len(data) <= MAX_LINE_OCTETS:
        return line
    parts: list[str] = []
    start, limit = 0, MAX_LINE_OCTETS
    while start < len(data):
        end = min(start + limit, len(data))
        while end < len(data) and data[end] & 0xC0 == 0x80:  # a continuation byte
            end -= 1
        parts.append(data[start:end].decode())
        start, limit = end, MAX_LINE_OCTETS - 1
    return "\r\n ".join(parts)


def _utc(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def _event(event: Event) -> list[str]:
    lines = [
        "BEGIN:VEVENT",
        f"UID:{event.uid}",
        f"DTSTAMP:{_utc(event.updated_at)}",
        f"LAST-MODIFIED:{_utc(event.updated_at)}",
        f"SEQUENCE:{event.sequence}",
        f"DTSTART:{_utc(event.starts_at)}",
        f"DTEND:{_utc(event.starts_at + event.duration)}",
        f"SUMMARY:{escape(event.summary)}",
        f"STATUS:{'CANCELLED' if event.cancelled else 'CONFIRMED'}",
    ]
    if event.location:
        lines.append(f"LOCATION:{escape(event.location)}")
    if event.description:
        lines.append(f"DESCRIPTION:{escape(event.description)}")
    if event.url:
        lines.append(f"URL:{event.url}")
    lines.append("END:VEVENT")
    return lines


def calendar(events: Iterable[Event], *, name: str | None = None, feed: bool = False) -> str:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{PRODID}",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]
    if name:
        lines += [f"NAME:{escape(name)}", f"X-WR-CALNAME:{escape(name)}"]
    if feed:
        lines += [f"REFRESH-INTERVAL;VALUE=DURATION:{REFRESH}", f"X-PUBLISHED-TTL:{REFRESH}"]
    for event in events:
        lines += _event(event)
    lines.append("END:VCALENDAR")
    return "".join(f"{fold(line)}\r\n" for line in lines)
