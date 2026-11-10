from pathlib import Path

from app.bgg.parse import parse_rpg_families, parse_rpg_item_systems, parse_search

FIXTURES = Path(__file__).parent / "fixtures" / "bgg"
BLADES = 26952


def test_rpg_book_search_reads_books() -> None:
    hits = parse_search((FIXTURES / "search_rpgitem_blades.xml").read_bytes())

    assert len(hits) == 8
    assert (hits[0].id, hits[0].name, hits[0].year_published) == (291997, "Alone in the Dark", 2019)


def test_books_lead_to_their_system_once() -> None:
    systems = parse_rpg_item_systems((FIXTURES / "thing_rpgitem_blades.xml").read_bytes())

    # Five books, all Blades in the Dark: listed once, by the name the link gives.
    assert [(s.id, s.name) for s in systems] == [(BLADES, "Blades in the Dark")]


def test_a_system_has_its_description_and_pictures() -> None:
    (blades,) = parse_rpg_families((FIXTURES / "family_rpg_blades.xml").read_bytes())

    assert (blades.id, blades.name) == (BLADES, "Blades in the Dark")
    assert blades.thumbnail_url and blades.thumbnail_url.startswith("https://cf.geekdo-images")
    assert blades.image_url and blades.image_url.startswith("https://cf.geekdo-images")
    assert blades.description is not None
    # BGG escapes entities twice; they come out as the characters.
    assert "scoundrels like you — the Blades" in blades.description
    assert "&" not in blades.description


def test_inbound_links_are_not_the_systems_books_belong_to() -> None:
    # A family lists its books as inbound "rpg" links; those aren't systems.
    assert parse_rpg_item_systems((FIXTURES / "family_rpg_blades.xml").read_bytes()) == []


def test_books_linked_to_many_systems_are_left_out() -> None:
    links = "".join(f'<link type="rpg" id="{n}" value="System {n}" />' for n in range(1, 6))
    xml = (
        '<items><item type="rpgitem" id="1">'
        f'<name type="primary" value="Big Book of RPGs"/>{links}</item>'
        '<item type="rpgitem" id="2"><name type="primary" value="Core"/>'
        '<link type="rpg" id="9" value="Nine" /></item></items>'
    ).encode()

    assert [s.id for s in parse_rpg_item_systems(xml)] == [9]
