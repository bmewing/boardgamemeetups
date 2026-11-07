"""The bot's slash commands, and a script that tells Discord about them.

Run it once, and again whenever the commands below change:

    uv run python -m app.discord.commands

It needs DISCORD_APPLICATION_ID and DISCORD_BOT_TOKEN (in .env or the environment), and
prints the link that adds the bot to a server.
"""

import sys
from typing import Any

import httpx

from app.config import get_settings
from app.discord.client import API_URL, USER_AGENT
from app.discord.interactions import COMMAND_NAME, EMBED_LINKS, SEND_MESSAGES, VIEW_CHANNEL

SUBCOMMAND = 1
GUILD = 0  # usable in servers (not DMs)
GUILD_INSTALL = 0  # installed to a server, not to someone's account

COMMANDS: list[dict[str, Any]] = [
    {
        "name": COMMAND_NAME,
        "description": "Board Game Group",
        "contexts": [GUILD],
        "integration_types": [GUILD_INSTALL],
        "options": [
            {
                "type": SUBCOMMAND,
                "name": "next",
                "description": "Post a card for the next date, to say whether you're coming",
            },
            {
                "type": SUBCOMMAND,
                "name": "link",
                "description": "Link your Discord account to your Board Game Group account",
            },
            {
                "type": SUBCOMMAND,
                "name": "connect",
                "description": "Post a group's dates in this channel (needs Manage Server)",
            },
            {
                "type": SUBCOMMAND,
                "name": "disconnect",
                "description": "Stop posting dates in this channel (needs Manage Server)",
            },
        ],
    }
]

# What the bot asks for when it's added to a server: enough to post and edit its cards.
INSTALL_PERMISSIONS = VIEW_CHANNEL | SEND_MESSAGES | EMBED_LINKS


def install_url(application_id: str) -> str:
    return (
        "https://discord.com/oauth2/authorize"
        f"?client_id={application_id}&scope=bot+applications.commands"
        f"&permissions={INSTALL_PERMISSIONS}"
    )


def main() -> int:
    settings = get_settings()
    if not settings.discord_application_id or not settings.discord_bot_token:
        print("Set DISCORD_APPLICATION_ID and DISCORD_BOT_TOKEN first.", file=sys.stderr)
        return 1
    response = httpx.put(
        f"{API_URL}/applications/{settings.discord_application_id}/commands",
        json=COMMANDS,
        headers={"Authorization": f"Bot {settings.discord_bot_token}", "User-Agent": USER_AGENT},
        timeout=15,
    )
    if response.is_error:
        print(f"Discord said {response.status_code}: {response.text}", file=sys.stderr)
        return 1
    names = ", ".join(command["name"] for command in response.json())
    print(f"Registered: {names}")
    print(f"Add the bot to a server: {install_url(settings.discord_application_id)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
