"""Load popular RPG systems from RPGGeek into the local catalog, so searching for them stays
local instead of costing three throttled RPGGeek requests each.

Run once per database (and again any time to refresh their details):
    uv run python -m app.import_rpg_systems

The ids are RPGGeek's "RPG" families (https://rpggeek.com/rpg/<id>).
"""

import asyncio

from app.bgg import BggClient, PostgresThrottle, create_http_client
from app.config import get_settings
from app.db import SessionLocal, engine
from app.rpg_catalog import upsert_system_details

POPULAR_SYSTEMS = {
    17181: "Dungeons & Dragons (5th Edition)",
    1627: "Pathfinder Roleplaying Game (1st Edition)",
    56388: "Pathfinder Roleplaying Game (2nd Edition)",
    41351: "Starfinder Roleplaying Game",
    23113: "Call of Cthulhu (7th Edition)",
    26952: "Blades in the Dark",
    57038: "Cyberpunk RED",
    21069: "Shadowrun (5th Edition)",
    56248: "Shadowrun: Sixth World (6th Edition)",
    48533: "Vampire: The Masquerade (5th Edition)",
    370: "Werewolf: The Apocalypse",
    48770: "Mothership",
    27917: "Delta Green: The Role-Playing Game",
    5891: "Apocalypse World",
    11105: "Dungeon World",
    28640: "Masks: A New Generation",
    17708: "Monster of the Week",
    203: "Fate Core",
    78185: "Savage Worlds Adventure Edition (SWADE)",
    332: "GURPS (4th Edition)",
    45637: "Warhammer Fantasy Roleplay (4th & 5th Editions)",
    79109: "Dragonbane",
    56344: "MÖRK BORG",
    75269: "Pirate Borg",
    73714: "Shadowdark RPG",
    58009: "Old-School Essentials Retro Adventure Game",
    10737: "Dungeon Crawl Classics Role Playing Game",
    56423: "ALIEN: The Roleplaying Game",
    114476: "ALIEN: The Roleplaying Game: Evolved Edition",
    40891: "Tales from the Loop",
    59583: "Vaesen",
    43641: "Forbidden Lands",
    43640: "Coriolis: The Third Horizon",
    19360: "Star Wars: Edge of the Empire",
    23396: "Star Wars: Age of Rebellion",
    25705: "Star Wars: Force and Destiny",
    39931: "Traveller (Mongoose 2nd Edition)",
    4395: "The One Ring (1st Edition)",
    27818: "The Cypher System",
    19481: "Numenera",
    17925: "13th Age",
    103027: "Daggerheart",
    109099: "Draw Steel",
    57798: "Lancer",
    66116: "Thirsty Sword Lesbians",
    44855: "Kids on Bikes",
    57447: "Root: The Roleplaying Game",
    71365: "Avatar Legends: The Roleplaying Game",
    61196: "Mausritter",
    65735: "Cairn",
    46662: "Ironsworn",
    57395: "Heart: The City Beneath",
    43044: "Spire",
    68792: "Wanderhome",
    42059: "Index Card RPG",
    28634: "KULT: Divinity Lost (4th Edition)",
    4996: "Legend of the Five Rings (4th Edition)",
    2138: "Dragon Age",
    72495: "Marvel Multiverse Role-Playing Game",
    105324: "Cosmere Roleplaying Game",
    72028: "Fabula Ultima",
    103496: "Triangle Agency",
    113127: "Nimble",
}


async def import_systems() -> int:
    settings = get_settings()
    async with create_http_client(settings.bgg_api_token) as http:
        bgg = BggClient(
            http,
            min_interval=settings.bgg_min_interval_seconds,
            throttle=PostgresThrottle(engine),
        )
        details = await bgg.rpg_families(POPULAR_SYSTEMS)
    async with SessionLocal() as session:
        await upsert_system_details(session, details)
        await session.commit()
    return len(details)


if __name__ == "__main__":
    total = asyncio.run(import_systems())
    print(f"Imported {total} of {len(POPULAR_SYSTEMS)} RPG systems")
