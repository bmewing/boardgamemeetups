"""Load BGG's ranks CSV (every game's id, name, year and rank) into the local catalog.

Download the file while logged in to BGG at https://boardgamegeek.com/data_dumps/bg_ranks,
then run:  uv run python -m app.import_bgg_ranks path/to/boardgames_ranks.zip  (or .csv)
"""

import asyncio
import csv
import io
import sys
import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from app.catalog import upsert_rank_rows
from app.db import SessionLocal

# 7 columns per row keeps each statement well under Postgres's 32,767 parameter limit.
CHUNK_SIZE = 4000


def _int(value: str | None) -> int | None:
    try:
        return int(value) if value else None
    except ValueError:
        return None


def _float(value: str | None) -> float | None:
    try:
        return float(value) if value else None
    except ValueError:
        return None


def parse_rows(text: io.TextIOBase) -> Iterator[dict[str, Any]]:
    for record in csv.DictReader(text):
        bgg_id = _int(record.get("id"))
        name = (record.get("name") or "").strip()
        if bgg_id is None or not name:
            continue
        yield {
            "id": bgg_id,
            "name": name[:512],
            "year_published": _int(record.get("yearpublished")) or None,
            "is_expansion": record.get("is_expansion") == "1",
            "bgg_rank": _int(record.get("rank")) or None,  # 0 means unranked
            "bgg_rating": _float(record.get("average")) or None,
            "bgg_users_rated": _int(record.get("usersrated")),
        }


def open_csv(path: Path) -> io.TextIOBase:
    if path.suffix.lower() == ".zip":
        archive = zipfile.ZipFile(path)
        name = next(n for n in archive.namelist() if n.lower().endswith(".csv"))
        return io.TextIOWrapper(archive.open(name), encoding="utf-8", newline="")
    return path.open(encoding="utf-8", newline="")


async def import_ranks(path: Path) -> int:
    count = 0
    chunk: list[dict[str, Any]] = []
    async with SessionLocal() as session:
        with open_csv(path) as text:
            for row in parse_rows(text):
                chunk.append(row)
                if len(chunk) == CHUNK_SIZE:
                    await upsert_rank_rows(session, chunk)
                    count += len(chunk)
                    chunk.clear()
        await upsert_rank_rows(session, chunk)
        count += len(chunk)
        await session.commit()
    return count


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    total = asyncio.run(import_ranks(Path(sys.argv[1])))
    print(f"Imported {total} games")
