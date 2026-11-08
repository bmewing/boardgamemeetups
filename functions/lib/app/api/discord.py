"""Discord: the endpoint Discord sends commands and clicks to, and linking a Discord account
to yours."""

import json
from typing import Annotated, Any

from fastapi import APIRouter, Header, HTTPException, Path, Request, status
from pydantic import BaseModel, StringConstraints
from sqlalchemy import update

from app import achievements
from app.api.me import UserRead
from app.auth import CurrentUser
from app.config import get_settings
from app.db import SessionDep
from app.discord.client import DiscordDep
from app.discord.interactions import handle, signature_ok
from app.discord.link import read_token
from app.models import User
from app.pieces import Achievement

router = APIRouter(tags=["discord"])

LinkToken = Annotated[str, StringConstraints(min_length=1, max_length=512)]
LINK_GONE = HTTPException(
    status.HTTP_404_NOT_FOUND,
    "This link has expired. Ask the bot for a new one with /bggroup link.",
)


@router.post("/discord/interactions", include_in_schema=False)
async def interactions(
    request: Request,
    session: SessionDep,
    discord: DiscordDep,
    signature: Annotated[str, Header(alias="X-Signature-Ed25519")] = "",
    timestamp: Annotated[str, Header(alias="X-Signature-Timestamp")] = "",
) -> dict[str, Any]:
    """Every slash command and button click, sent by Discord, which checks the signature
    and allows 3 seconds for the answer."""
    if not get_settings().discord_public_key:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "The Discord bot isn't set up.")
    body = await request.body()
    if not signature_ok(signature, timestamp, body):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Bad request signature")
    try:
        interaction = json.loads(body)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Not JSON") from exc
    if not isinstance(interaction, dict):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Not an interaction")
    return await handle(session, discord, interaction)


class DiscordLinkRead(BaseModel):
    discord_username: str


class DiscordLinkIn(BaseModel):
    token: LinkToken


@router.get("/discord/link/{token}")
async def read_link(token: Annotated[str, Path(max_length=512)]) -> DiscordLinkRead:
    """Which Discord account a link from the bot is for, to show before linking."""
    account = read_token(token)
    if account is None:
        raise LINK_GONE
    return DiscordLinkRead(discord_username=account.username)


@router.put("/me/discord")
async def link_discord(body: DiscordLinkIn, user: CurrentUser, session: SessionDep) -> UserRead:
    """Link the Discord account a link from the bot is for. Opening the link proves it's
    yours, so it moves here if it was linked to another account."""
    account = read_token(body.token)
    if account is None:
        raise LINK_GONE
    await session.execute(
        update(User)
        .where(User.discord_id == account.id, User.id != user.id)
        .values(discord_id=None, discord_username=None)
    )
    user.discord_id = account.id
    user.discord_username = account.username
    await achievements.earn(session, Achievement.STAY_IN_LOOP, user.id)
    await session.commit()
    await session.refresh(user)
    return await UserRead.of(session, user)


@router.delete("/me/discord")
async def unlink_discord(user: CurrentUser, session: SessionDep) -> UserRead:
    user.discord_id = None
    user.discord_username = None
    await session.commit()
    await session.refresh(user)
    return await UserRead.of(session, user)
