"""Load Board Game Arena's game list into `bga_games`, linked to the catalog's games.

BGA has no API, and its terms don't allow automated fetching, so this is done by hand now
and then:

1. Open https://boardgamearena.com/gamelist in a browser (no need to sign in) and save the
   page ("Save as", HTML only).
2. Turn it into the trimmed list kept in the repo, and load it:
       uv run python -m app.import_bga path/to/gamelist.html --write-snapshot data/bga_games.json
3. Commit data/bga_games.json. Other databases (production) load the committed file:
       uv run --env-file .env.production python -m app.import_bga data/bga_games.json

BGA names the BGG game for almost every entry; those games link directly (as a stub, filled
in later, if the catalog doesn't have it yet). The rest are matched by name when the name is
unambiguous, and listed at the end otherwise. To fix a link, set the entry's `bgg_id` in the
snapshot and load it again. Loading is idempotent; games BGA no longer lists are removed.
"""

import argparse
import asyncio
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app import catalog
from app.bgg import SearchHit
from app.db import SessionLocal
from app.matching import match_name
from app.models import BgaGame, Game

GAME_LIST = '"game_list":'


class BgaFileError(ValueError):
    pass


@dataclass
class BgaEntry:
    """One game, with only the fields kept from BGA's list."""

    id: int
    slug: str
    name: str
    premium: bool
    player_counts: list[int]
    bgg_id: int  # 0 when BGA doesn't say
    status: str

    @classmethod
    def from_bga(cls, raw: dict[str, Any]) -> "BgaEntry":
        """An entry of the `game_list` in BGA's page."""
        return cls(
            id=int(raw["id"]),
            slug=str(raw["name"]),
            name=str(raw.get("display_name_en") or raw["name"]).strip(),
            premium=bool(raw.get("premium")),
            player_counts=sorted({int(n) for n in raw.get("player_numbers") or []}),
            bgg_id=int(raw.get("bgg_id") or 0),
            status=str(raw.get("status") or "public"),
        )

    @classmethod
    def from_snapshot(cls, raw: dict[str, Any]) -> "BgaEntry":
        return cls(**{name: raw[name] for name in cls.__dataclass_fields__})


def parse(text: str) -> list[BgaEntry]:
    """The games in a saved BGA page, or in a snapshot written by this command."""
    stripped = text.lstrip()
    if stripped.startswith("["):
        entries = [BgaEntry.from_snapshot(raw) for raw in json.loads(stripped)]
    else:
        at = text.find(GAME_LIST)
        if at < 0:
            raise BgaFileError("No game list in this file; save BGA's /gamelist page.")
        start = at + len(GAME_LIST)
        while text[start].isspace():
            start += 1
        raw_list, _end = json.JSONDecoder().raw_decode(text, start)
        entries = [BgaEntry.from_bga(raw) for raw in raw_list]
    # Games with no player counts can't be fitted to anyone, so they're of no use here.
    entries = [e for e in entries if e.player_counts]
    if not entries:
        raise BgaFileError("The game list is empty.")
    return sorted(entries, key=lambda e: e.id)


def snapshot(entries: Sequence[BgaEntry]) -> str:
    """The trimmed list kept in the repo: one game per line, so changes diff well."""
    lines = [json.dumps(asdict(e), ensure_ascii=False) for e in entries]
    return "[\n" + ",\n".join(lines) + "\n]\n"


@dataclass
class ImportReport:
    total: int = 0
    linked: int = 0
    stubs_added: int = 0  # BGG games the catalog didn't have yet
    # Each with the catalog game it matched, as "id name (year)".
    matched_by_name: list[tuple[BgaEntry, str]] = field(default_factory=list)
    unlinked: list[BgaEntry] = field(default_factory=list)
    removed: int = 0


async def import_games(session: AsyncSession, entries: Sequence[BgaEntry]) -> ImportReport:
    report = ImportReport(total=len(entries))
    bgg_ids = {e.bgg_id for e in entries if e.bgg_id > 0}
    known = set(await session.scalars(select(Game.id).where(Game.id.in_(bgg_ids))))
    missing = {e.bgg_id: e for e in entries if e.bgg_id > 0 and e.bgg_id not in known}
    await catalog.insert_search_hits(
        session, [SearchHit(bgg_id, e.name, None) for bgg_id, e in missing.items()]
    )
    report.stubs_added = len(missing)

    rows = []
    for entry in entries:
        game_id: int | None = entry.bgg_id if entry.bgg_id > 0 else None
        if game_id is None:
            game = await match_name(session, entry.name)
            if game is not None:
                game_id = game.id
                year = f" ({game.year_published})" if game.year_published else ""
                report.matched_by_name.append((entry, f"{game.id} {game.name}{year}"))
            else:
                report.unlinked.append(entry)
        if game_id is not None:
            report.linked += 1
        rows.append(
            {
                "id": entry.id,
                "slug": entry.slug,
                "name": entry.name,
                "game_id": game_id,
                "premium": entry.premium,
                "player_counts": entry.player_counts,
                "status": entry.status,
            }
        )
    stmt = insert(BgaGame).values(rows)
    await session.execute(
        stmt.on_conflict_do_update(
            index_elements=[BgaGame.id],
            set_={column: stmt.excluded[column] for column in rows[0] if column != "id"},
        )
    )
    gone = await session.execute(
        delete(BgaGame).where(BgaGame.id.not_in([e.id for e in entries])).returning(BgaGame.id)
    )
    report.removed = len(gone.all())
    return report


def _print_report(report: ImportReport) -> None:
    print(f"Loaded {report.total} BGA games; {report.linked} linked to catalog games.")
    if report.stubs_added:
        print(f"Added {report.stubs_added} BGG games the catalog didn't have (details later).")
    if report.removed:
        print(f"Removed {report.removed} games BGA no longer lists.")
    if report.matched_by_name:
        print("\nMatched by name (BGA gave no BGG id); check these:")
        for entry, game in report.matched_by_name:
            print(f"  {entry.slug}: {entry.name} -> {game}")
    if report.unlinked:
        print("\nNot linked (set bgg_id in the snapshot to link them):")
        for entry in report.unlinked:
            print(f"  {entry.slug}: {entry.name}")


async def load(entries: Sequence[BgaEntry]) -> ImportReport:
    async with SessionLocal() as session:
        report = await import_games(session, entries)
        await session.commit()
    return report


def main(path: Path, write_snapshot: Path | None) -> None:
    entries = parse(path.read_text(encoding="utf-8"))
    if write_snapshot is not None:
        write_snapshot.write_text(snapshot(entries), encoding="utf-8", newline="\n")
        print(f"Wrote {len(entries)} games to {write_snapshot}")
    _print_report(asyncio.run(load(entries)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("path", type=Path, help="a saved BGA /gamelist page, or a snapshot")
    parser.add_argument("--write-snapshot", type=Path, help="also save the trimmed list here")
    args = parser.parse_args()
    try:
        main(args.path, args.write_snapshot)
    except BgaFileError as exc:
        sys.exit(str(exc))
