"""Posting, editing and deleting the bot's messages through Discord's REST API."""

import logging
from enum import StrEnum
from typing import Annotated, Any, Protocol

import httpx
from fastapi import Depends

from app.config import get_settings

logger = logging.getLogger(__name__)

API_URL = "https://discord.com/api/v10"
# Discord asks bots to name themselves this way.
USER_AGENT = "DiscordBot (https://bggroup.app, 1.0)"

Message = dict[str, Any]


class Edit(StrEnum):
    DONE = "done"
    GONE = "gone"  # the message (or channel) was deleted in Discord
    FAILED = "failed"


class Discord(Protocol):
    @property
    def enabled(self) -> bool: ...

    async def post(self, channel_id: str, message: Message) -> str | None:
        """Post a message; its ID, or None if it couldn't be posted (already logged)."""
        ...

    async def edit(self, channel_id: str, message_id: str, message: Message) -> Edit: ...

    async def delete(self, channel_id: str, message_id: str) -> None:
        """Delete a message if it's still there. Failures are logged, not raised."""
        ...


class RestDiscord:
    enabled = True

    def __init__(self, bot_token: str) -> None:
        self.headers = {"Authorization": f"Bot {bot_token}", "User-Agent": USER_AGENT}

    async def _send(
        self, method: str, path: str, message: Message | None = None
    ) -> httpx.Response | None:
        try:
            async with httpx.AsyncClient(base_url=API_URL, headers=self.headers, timeout=5) as http:
                return await http.request(method, path, json=message)
        except httpx.HTTPError:
            logger.exception("Discord %s %s failed", method, path)
            return None

    def _failed(self, response: httpx.Response, what: str) -> None:
        logger.error("Discord %s failed: %s %s", what, response.status_code, response.text)

    async def post(self, channel_id: str, message: Message) -> str | None:
        response = await self._send("POST", f"/channels/{channel_id}/messages", message)
        if response is None:
            return None
        if response.is_error:
            self._failed(response, f"post to {channel_id}")
            return None
        message_id: str = response.json()["id"]
        return message_id

    async def edit(self, channel_id: str, message_id: str, message: Message) -> Edit:
        response = await self._send(
            "PATCH", f"/channels/{channel_id}/messages/{message_id}", message
        )
        if response is None:
            return Edit.FAILED
        if response.status_code == httpx.codes.NOT_FOUND:
            return Edit.GONE
        if response.is_error:
            self._failed(response, f"edit of {message_id}")
            return Edit.FAILED
        return Edit.DONE

    async def delete(self, channel_id: str, message_id: str) -> None:
        response = await self._send("DELETE", f"/channels/{channel_id}/messages/{message_id}")
        if response is not None and response.is_error and response.status_code != 404:
            self._failed(response, f"delete of {message_id}")


class NoDiscord:
    """Stands in when there's no bot token (local development): nothing is posted."""

    enabled = False

    async def post(self, channel_id: str, message: Message) -> str | None:
        return None

    async def edit(self, channel_id: str, message_id: str, message: Message) -> Edit:
        return Edit.FAILED

    async def delete(self, channel_id: str, message_id: str) -> None:
        return None


def get_discord() -> Discord:
    token = get_settings().discord_bot_token
    return RestDiscord(token) if token else NoDiscord()


DiscordDep = Annotated[Discord, Depends(get_discord)]
