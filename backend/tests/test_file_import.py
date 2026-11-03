import io
from datetime import datetime

import pytest
from openpyxl import Workbook

from app.file_import import (
    FileError,
    FileKind,
    ImportColumn,
    WholeFile,
    bgg_export_entries,
    inspect_table,
    parse_rows,
    read_table,
)
from app.models import Ownership, PlaytimeFeel

C = ImportColumn


def xlsx(rows: list[list[object]]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    for row in rows:
        sheet.append(row)
    out = io.BytesIO()
    workbook.save(out)
    return out.getvalue()


def test_reads_excel_cells_as_text() -> None:
    data = xlsx([["Name", "Year", "Last Played"], ["Wingspan", 2019.0, datetime(2026, 6, 13)]])

    table = read_table(data, "games.xlsx")

    assert table == [["Name", "Year", "Last Played"], ["Wingspan", "2019", "2026-06-13"]]


def test_reads_csv_with_semicolons_and_drops_empty_trailing_columns() -> None:
    data = b"Name;Rating;;\nAzul;8;;\n;;;\nBrass;9;;\n"

    assert read_table(data, "games.csv") == [["Name", "Rating"], ["Azul", "8"], ["Brass", "9"]]


def test_rejects_an_empty_file() -> None:
    with pytest.raises(FileError):
        read_table(b"\n\n", "games.csv")


def test_suggests_columns_from_headers() -> None:
    table = [["Game", "Min Player", "My Rating", "Comments", "Notes"], ["Azul", "2", "8", "", ""]]

    layout = inspect_table(table)

    assert layout.kind is FileKind.TABLE
    assert layout.has_header
    assert layout.suggested == [C.NAME, None, C.RATING, C.NOTES, C.NOTES]
    assert layout.row_count == 1


def test_a_plain_list_has_no_header_and_names_in_the_first_column() -> None:
    layout = inspect_table([["Wingspan (2019)"], ["Azul"]])

    assert not layout.has_header
    assert layout.headers == ["Column A"]
    assert layout.suggested == [C.NAME]
    assert layout.row_count == 2


def test_recognizes_a_bgg_export() -> None:
    table = [["objectname", "objectid", "own"], ["Wingspan", "266192", "1"]]

    assert inspect_table(table).kind is FileKind.BGG_EXPORT


def test_parses_answers_and_explains_what_doesnt_fit() -> None:
    table = [
        ["Name", "Owned", "Rating", "Length", "Teach", "Teach time", "Plays", "Wishlist"],
        ["Azul", "yes", "8.5", "longer", "y", "20 min", "2026-06-13", "love to have"],
        ["Brass", "sold", "eleven", "", "yes", "", "4", ""],
    ]
    columns: list[ImportColumn | None] = [
        C.NAME,
        C.OWNERSHIP,
        C.RATING,
        C.PLAYTIME_FEEL,
        C.CAN_TEACH,
        C.TEACH_MINUTES,
        C.PLAYS,
        C.WISHLIST_PRIORITY,
    ]

    azul, brass = parse_rows(table, inspect_table(table), columns)

    assert azul.values == {
        "ownership": Ownership.OWNED,
        "rating": 8.5,
        "playtime_feel": PlaytimeFeel.LONGER,
        "can_teach": True,
        "teach_minutes": 20,
        "wishlist_priority": 2,
    }
    assert azul.problems == ["plays “2026-06-13” doesn't make sense"]  # a date isn't a count
    assert brass.values == {"ownership": Ownership.PREVIOUSLY_OWNED, "plays": 4}
    assert brass.problems == [
        "rating “eleven” doesn't make sense",
        "can teach needs a teach time, so it was left out",
    ]


def test_several_columns_can_go_into_notes() -> None:
    table = [["Name", "Boxes", "Status"], ["Arcadia Quest", "Inferno, Riders", "Stack"]]

    [row] = parse_rows(table, inspect_table(table), [C.NAME, C.NOTES, C.NOTES], WholeFile.OWNED)

    assert row.values["notes"] == "Boxes: Inferno, Riders; Status: Stack"


def test_every_game_can_be_put_on_one_shelf() -> None:
    table = [["Name"], ["Azul"]]
    layout = inspect_table(table)

    [owned] = parse_rows(table, layout, [C.NAME], WholeFile.OWNED)
    [wanted] = parse_rows(table, layout, [C.NAME], WholeFile.WISHLIST)
    [neither] = parse_rows(table, layout, [C.NAME], WholeFile.NEITHER)

    assert owned.values == {"ownership": Ownership.OWNED}
    assert wanted.values == {"wishlist_priority": 3}
    assert neither.values == {}


def test_a_shelf_is_required_without_an_ownership_or_wishlist_column() -> None:
    table = [["Name"], ["Azul"]]

    with pytest.raises(FileError, match="owned or on your wishlist"):
        parse_rows(table, inspect_table(table), [C.NAME])


def test_the_name_column_is_required_and_fields_cant_repeat() -> None:
    table = [["A", "B"], ["Azul", "8"]]
    layout = inspect_table(table)

    with pytest.raises(FileError, match="name"):
        parse_rows(table, layout, [None, C.RATING], WholeFile.OWNED)
    with pytest.raises(FileError, match="one column only"):
        parse_rows(table, layout, [C.NAME, C.NAME], WholeFile.OWNED)


def test_years_in_names_are_read() -> None:
    table = [["Wingspan (2019)"]]

    [row] = parse_rows(table, inspect_table(table), [C.NAME], WholeFile.NEITHER)

    assert (row.name, row.year) == ("Wingspan", 2019)


def test_reads_a_bgg_export_and_merges_copies() -> None:
    table = [
        ["objectname", "objectid", "rating", "numplays", "own", "wishlist", "itemtype"],
        ["Wingspan", "266192", "8.5", "12", "1", "0", "standalone"],
        ["Wingspan", "266192", "0", "12", "0", "0", "standalone"],
        ["Wingspan: Oceania", "290837", "", "0", "0", "0", "expansion"],
    ]

    wingspan, oceania = bgg_export_entries(table)

    assert (wingspan.own, wingspan.rating, wingspan.plays) == (True, 8.5, 12)
    assert oceania.is_expansion and oceania.rating is None
