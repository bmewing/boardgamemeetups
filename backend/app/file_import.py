"""Read an uploaded game list: a BGG collection export, or any table of games.

Reading takes two steps. `inspect_table` reports the file's columns with sample values and
a guessed meaning for each; the user confirms or changes those, and `parse_rows` then reads
every row with the chosen columns. A BGG export needs no choices: its columns are known.

Every row ends up as a `FileRow`: what it says about the game (a BGG id, or a name and maybe
a year) and the user_games values it carries. Values that don't fit their field are dropped
and explained in `problems`, so one bad cell doesn't sink the whole file.
"""

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from typing import Any

from openpyxl import load_workbook
from pydantic import ValidationError

from app.bgg.parse import CollectionEntry, merge_copies
from app.collection import bgg_values, validate_field
from app.models import Ownership, PlaytimeFeel

MAX_ROWS = 5000
SAMPLE_ROWS = 5


class FileError(ValueError):
    """The file can't be read, or the chosen columns don't make sense."""


class FileKind(StrEnum):
    BGG_EXPORT = "bgg_export"  # BGG's collection CSV: has objectid, so no matching needed
    TABLE = "table"  # anything else: the user says what each column holds


class ImportColumn(StrEnum):
    """What a file column can hold: how to find the game, or one of the user's answers."""

    NAME = "name"
    YEAR = "year"
    BGG_ID = "bgg_id"
    OWNERSHIP = "ownership"
    WISHLIST_PRIORITY = "wishlist_priority"
    WANT_TO_PLAY = "want_to_play"
    RATING = "rating"
    WEIGHT_VOTE = "weight_vote"
    PLAYTIME_FEEL = "playtime_feel"
    CAN_TEACH = "can_teach"
    TEACH_MINUTES = "teach_minutes"
    PLAYS = "plays"
    WILL_BRING = "will_bring"
    NOTES = "notes"  # several columns may go here; each is labelled with its header


class WholeFile(StrEnum):
    """Where a file's games go when no column says: a list of games is usually one shelf."""

    OWNED = "owned"
    WISHLIST = "wishlist"
    NEITHER = "neither"


# BGG's middle priority, "Like to have", for games put on the wishlist without one.
DEFAULT_WISHLIST_PRIORITY = 3


@dataclass
class FileRow:
    line: int  # where the row is in the file, for messages
    name: str | None = None
    year: int | None = None
    bgg_id: int | None = None
    values: dict[str, Any] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)


@dataclass
class TableLayout:
    kind: FileKind
    has_header: bool
    headers: list[str]  # "Column A", "Column B"… when the file has no header row
    samples: list[list[str]]
    suggested: list[ImportColumn | None]
    row_count: int


def _cell(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))  # Excel stores 2019 as 2019.0
    if isinstance(value, datetime):
        return value.date().isoformat() if value.time() == datetime.min.time() else str(value)
    if isinstance(value, date):
        return value.isoformat()
    return str(value).strip()


def read_table(data: bytes, filename: str) -> list[list[str]]:
    """The file's non-empty rows as text cells, all padded to the same width."""
    if filename.lower().endswith((".xlsx", ".xlsm")):
        try:
            workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        except Exception as exc:  # openpyxl raises many kinds of errors for bad files
            raise FileError("This doesn't look like an Excel file") from exc
        sheet = workbook.worksheets[0]
        table = [[_cell(c) for c in row] for row in sheet.iter_rows(values_only=True)]
    else:
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = data.decode("cp1252", errors="replace")  # Excel's "CSV" on Windows
        lines = text.splitlines()
        try:
            dialect: Any = csv.Sniffer().sniff("\n".join(lines[:20]), delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel  # one column, or nothing to go on
        table = [[c.strip() for c in row] for row in csv.reader(lines, dialect)]
    table = [row for row in table if any(row)]
    if not table:
        raise FileError("The file is empty")
    if len(table) > MAX_ROWS + 1:
        raise FileError(f"The file has more than {MAX_ROWS:,} rows")
    width = max(len(row) for row in table)
    # Trailing columns with no header and no values are just Excel formatting.
    while width > 1 and not any(len(row) >= width and row[width - 1] for row in table):
        width -= 1
    return [(row + [""] * width)[:width] for row in table]


def _key(header: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", header.lower()).strip("_")


# Header spellings that suggest a column's meaning. Only a suggestion: the user decides.
ALIASES: dict[ImportColumn, set[str]] = {
    ImportColumn.NAME: {"name", "game", "title", "game_name", "objectname"},
    ImportColumn.YEAR: {"year", "year_published", "yearpublished", "published"},
    ImportColumn.BGG_ID: {"bgg_id", "bggid", "bgg", "bgg_number"},
    ImportColumn.OWNERSHIP: {"ownership", "owned", "own"},
    ImportColumn.WISHLIST_PRIORITY: {"wishlist", "wishlist_priority"},
    ImportColumn.WANT_TO_PLAY: {"want_to_play", "wanttoplay"},
    ImportColumn.RATING: {"rating", "my_rating", "your_rating"},
    ImportColumn.WEIGHT_VOTE: {"my_weight", "weight_vote", "your_weight"},
    ImportColumn.PLAYTIME_FEEL: {"length", "playtime_feel", "length_feel"},
    ImportColumn.CAN_TEACH: {"can_teach", "teach", "teacher"},
    ImportColumn.TEACH_MINUTES: {"teach_minutes", "teach_time", "teach_mins"},
    ImportColumn.PLAYS: {"plays", "numplays", "play_count", "times_played"},
    ImportColumn.WILL_BRING: {"will_bring", "bring"},
    ImportColumn.NOTES: {"notes", "note", "comment", "comments"},
}
BY_ALIAS = {alias: column for column, aliases in ALIASES.items() for alias in aliases}


def _column_letter(index: int) -> str:
    letters = ""
    index += 1
    while index:
        index, rest = divmod(index - 1, 26)
        letters = chr(ord("A") + rest) + letters
    return letters


def inspect_table(table: list[list[str]]) -> TableLayout:
    """The file's columns, a few sample rows, and a guess at what each column holds."""
    first = table[0]
    keys = [_key(h) for h in first]
    if "objectid" in keys:
        return TableLayout(FileKind.BGG_EXPORT, True, first, table[1 : 1 + SAMPLE_ROWS], [], 0)

    guesses = [BY_ALIAS.get(k) for k in keys]
    has_header = any(guesses)
    suggested: list[ImportColumn | None] = []
    for guess in guesses if has_header else [None] * len(first):
        # Each field comes from one column, except notes, which can gather several.
        taken = guess in suggested and guess is not ImportColumn.NOTES
        suggested.append(None if taken else guess)
    if not has_header:
        suggested[0] = ImportColumn.NAME  # a plain list: the first column is the name
    headers = first if has_header else [f"Column {_column_letter(i)}" for i in range(len(first))]
    data = table[1:] if has_header else table
    return TableLayout(
        FileKind.TABLE, has_header, headers, data[:SAMPLE_ROWS], suggested, len(data)
    )


YES = {"yes", "y", "true", "1", "x"}
NO = {"no", "n", "false", "0"}
OWNERSHIP_WORDS = {
    **dict.fromkeys(YES | {"owned", "own", "have", "✓", "✔"}, Ownership.OWNED),
    **dict.fromkeys({"preordered", "pre_ordered", "preorder", "pre_order"}, Ownership.PREORDERED),
    **dict.fromkeys(
        {"previously_owned", "prevowned", "prev_owned", "previously", "sold", "traded"},
        Ownership.PREVIOUSLY_OWNED,
    ),
}
WISHLIST_WORDS = {
    "must_have": 1,
    "love_to_have": 2,
    "like_to_have": 3,
    "thinking_about_it": 4,
    "don_t_buy_this": 5,
    "dont_buy_this": 5,
}
PLAYTIME_WORDS = {
    **dict.fromkeys({"shorter", "short", "less", "faster", "quicker"}, PlaytimeFeel.SHORTER),
    **dict.fromkeys(
        {"just_right", "right", "as_listed", "same", "about_right", "ok"}, PlaytimeFeel.JUST_RIGHT
    ),
    **dict.fromkeys({"longer", "long", "more", "slower"}, PlaytimeFeel.LONGER),
}
# A number on its own or with a unit ("20", "20 min", "7.5/10"), but not a date ("2026-06-13").
NUMBER = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*(?:/\s*\d+|[a-zA-Z][a-zA-Z .]*)?\s*$")


class _Unreadable(ValueError):
    pass


def _number(text: str) -> float:
    match = NUMBER.match(text)
    if not match:
        raise _Unreadable
    return float(match.group(1))


def _flag(text: str) -> bool:
    word = _key(text) or text.strip()
    if word in YES or word in {"✓", "✔"}:
        return True
    if word in NO or word == "-":
        return False
    raise _Unreadable


def _convert(column: ImportColumn, text: str) -> Any:
    """A cell's value for its field; raises _Unreadable if it makes no sense."""
    word = _key(text) or text.strip()
    match column:
        case ImportColumn.OWNERSHIP:
            if word in NO or word in {"not_owned", "none", "-"}:
                return None
            if word not in OWNERSHIP_WORDS:
                raise _Unreadable
            return OWNERSHIP_WORDS[word]
        case ImportColumn.WISHLIST_PRIORITY:
            if NUMBER.match(text):
                return int(_number(text)) or None  # 1-5; 0 means not wishlisted
            if word in WISHLIST_WORDS:
                return WISHLIST_WORDS[word]
            if word in YES:
                return DEFAULT_WISHLIST_PRIORITY
            if word in NO:
                return None
            raise _Unreadable
        case ImportColumn.PLAYTIME_FEEL:
            if word not in PLAYTIME_WORDS:
                raise _Unreadable
            return PLAYTIME_WORDS[word]
        case ImportColumn.WANT_TO_PLAY | ImportColumn.CAN_TEACH | ImportColumn.WILL_BRING:
            return _flag(text)
        case ImportColumn.RATING:
            return _number(text)
        case ImportColumn.WEIGHT_VOTE:
            return round(_number(text))
        case ImportColumn.TEACH_MINUTES | ImportColumn.PLAYS:
            return int(_number(text))
        case _:
            raise AssertionError(column)


FIELD_WORDS = {
    ImportColumn.OWNERSHIP: "ownership",
    ImportColumn.WISHLIST_PRIORITY: "wishlist",
    ImportColumn.WANT_TO_PLAY: "want to play",
    ImportColumn.RATING: "rating",
    ImportColumn.WEIGHT_VOTE: "weight",
    ImportColumn.PLAYTIME_FEEL: "length",
    ImportColumn.CAN_TEACH: "can teach",
    ImportColumn.TEACH_MINUTES: "teach time",
    ImportColumn.PLAYS: "plays",
    ImportColumn.WILL_BRING: "will bring",
}
NAME_WITH_YEAR = re.compile(r"^(.*?)\s*\((\d{4})\)\s*$")


SHELF_COLUMNS = {ImportColumn.OWNERSHIP, ImportColumn.WISHLIST_PRIORITY}


def check_columns(
    columns: list[ImportColumn | None], width: int, whole_file: WholeFile | None
) -> None:
    if len(columns) != width:
        raise FileError(f"Say what each of the file's {width} columns holds")
    if not ({ImportColumn.NAME, ImportColumn.BGG_ID} & set(columns)):
        raise FileError("Pick the column with the game's name (or its BGG id)")
    chosen = [c for c in columns if c is not None and c is not ImportColumn.NOTES]
    if len(chosen) != len(set(chosen)):
        raise FileError("Each field can come from one column only (except notes)")
    if not (SHELF_COLUMNS & set(columns)) and whole_file is None:
        raise FileError("Say whether the games in this file are owned or on your wishlist")


def parse_rows(
    table: list[list[str]],
    layout: TableLayout,
    columns: list[ImportColumn | None],
    whole_file: WholeFile | None = None,
) -> list[FileRow]:
    """Read every data row using the columns the user chose.

    `whole_file` says where the games go when no column holds ownership or wishlist.
    """
    check_columns(columns, len(layout.headers), whole_file)
    shelf_from_columns = bool(SHELF_COLUMNS & set(columns))
    notes_columns = [i for i, c in enumerate(columns) if c is ImportColumn.NOTES]
    data = table[1:] if layout.has_header else table
    first_line = 2 if layout.has_header else 1
    rows: list[FileRow] = []
    for line, cells in enumerate(data, start=first_line):
        row = FileRow(line=line)
        for column, text in zip(columns, cells, strict=True):
            if column is None or column is ImportColumn.NOTES or not text:
                continue
            if column is ImportColumn.NAME:
                row.name = text
            elif column in (ImportColumn.YEAR, ImportColumn.BGG_ID):
                try:
                    setattr(row, column.value, int(_number(text)))
                except _Unreadable:
                    row.problems.append(f"{column.value.replace('_', ' ')} “{text}” isn't a number")
            else:
                try:
                    row.values[column.value] = validate_field(column.value, _convert(column, text))
                except (_Unreadable, ValueError, ValidationError):
                    row.problems.append(f"{FIELD_WORDS[column]} “{text}” doesn't make sense")
        notes = [(layout.headers[i], cells[i]) for i in notes_columns if cells[i]]
        if len(notes) == 1 and len(notes_columns) == 1:
            row.values["notes"] = notes[0][1][:2000]
        elif notes:
            row.values["notes"] = "; ".join(f"{h}: {v}" for h, v in notes)[:2000]
        if row.name and row.year is None and (match := NAME_WITH_YEAR.match(row.name)):
            row.name, row.year = match.group(1), int(match.group(2))  # "Wingspan (2019)"
        if not shelf_from_columns and whole_file is WholeFile.OWNED:
            row.values["ownership"] = Ownership.OWNED
        elif not shelf_from_columns and whole_file is WholeFile.WISHLIST:
            row.values["wishlist_priority"] = DEFAULT_WISHLIST_PRIORITY
        if row.values.get("can_teach") and "teach_minutes" not in row.values:
            del row.values["can_teach"]
            row.problems.append("can teach needs a teach time, so it was left out")
        if row.name or row.bgg_id:
            rows.append(row)
    return rows


def _int_or_none(text: str | None) -> int | None:
    try:
        return int(float(text)) if text else None
    except ValueError:
        return None


def _float_or_none(text: str | None) -> float | None:
    try:
        return float(text) if text else None
    except ValueError:
        return None


def bgg_export_entries(table: list[list[str]]) -> list[CollectionEntry]:
    """Games and the user's answers from BGG's collection CSV export."""
    keys = [_key(h) for h in table[0]]
    entries: dict[int, CollectionEntry] = {}
    for cells in table[1:]:
        r = dict(zip(keys, cells, strict=False))
        bgg_id = _int_or_none(r.get("objectid"))
        name = r.get("objectname") or r.get("originalname")
        if bgg_id is None or not name:
            continue
        rating = _float_or_none(r.get("rating"))
        wishlisted = r.get("wishlist") == "1"
        entry = CollectionEntry(
            id=bgg_id,
            name=name,
            is_expansion=r.get("itemtype") == "expansion"
            or r.get("objecttype") == "boardgameexpansion",
            year_published=_int_or_none(r.get("yearpublished")) or None,
            min_players=_int_or_none(r.get("minplayers")) or None,
            max_players=_int_or_none(r.get("maxplayers")) or None,
            min_playtime=_int_or_none(r.get("minplaytime")) or None,
            max_playtime=_int_or_none(r.get("maxplaytime")) or None,
            playing_time=_int_or_none(r.get("playingtime")) or None,
            bgg_rank=_int_or_none(r.get("rank")) or None,
            bgg_rating=_float_or_none(r.get("average")) or None,
            own=r.get("own") == "1",
            prevowned=r.get("prevowned") == "1",
            preordered=r.get("preordered") == "1",
            wishlist_priority=_int_or_none(r.get("wishlistpriority")) if wishlisted else None,
            want_to_play=r.get("wanttoplay") == "1",
            rating=rating if rating and 1 <= rating <= 10 else None,
            plays=_int_or_none(r.get("numplays")) or 0,
            comment=r.get("comment") or None,
        )
        if bgg_id in entries:
            merge_copies(entries[bgg_id], entry)  # one row per copy, as in the API
        else:
            entries[bgg_id] = entry
    return list(entries.values())


def bgg_export_rows(entries: list[CollectionEntry]) -> list[FileRow]:
    return [
        FileRow(line=0, name=e.name, year=e.year_published, bgg_id=e.id, values=bgg_values(e))
        for e in entries
    ]
