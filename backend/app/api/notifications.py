"""Scheduled emails, and turning emails off from a link in one."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, status
from pydantic import BaseModel
from sqlalchemy import select

from app.db import SessionDep
from app.discord.cards import announce_due
from app.discord.client import DiscordDep
from app.email import EmailKind, MailerDep
from app.models import Group, User
from app.notify import send_due_reminders
from app.plays import fill_unlogged
from app.schedule import sync_meetups

router = APIRouter(tags=["notifications"])

EmailToken = Annotated[str, Path(min_length=1, max_length=64)]
LINK_GONE = HTTPException(status.HTTP_404_NOT_FOUND, "This link doesn't work any more.")


class RunResult(BaseModel):
    reminded_dates: int
    announced_dates: int  # meetup cards posted in Discord


class EmailSettingsRead(BaseModel):
    email_opt_outs: list[EmailKind]


@router.post("/notifications/run")
async def run_scheduled(session: SessionDep, mailer: MailerDep, discord: DiscordDep) -> RunResult:
    """Called every hour by a GitHub Actions workflow. Open to anyone: it only does what's
    due (tops up each group's dates, fills in unlogged plays, sends reminders, posts Discord
    cards a week ahead), and never sends a reminder or posts a card twice."""
    for group in list(await session.scalars(select(Group))):
        if group.schedule:
            await sync_meetups(session, group)
        await fill_unlogged(session, group)
    reminded = await send_due_reminders(session, mailer)
    return RunResult(reminded_dates=reminded, announced_dates=await announce_due(session, discord))


async def _by_token(session: SessionDep, token: str) -> User:
    user = await session.scalar(select(User).where(User.email_token == token))
    if user is None:
        raise LINK_GONE
    return user


@router.get("/email/unsubscribe/{token}")
async def read_email_settings(token: EmailToken, session: SessionDep) -> EmailSettingsRead:
    """Which emails the link's owner has turned off. Needs no sign-in, only the link."""
    user = await _by_token(session, token)
    return EmailSettingsRead(email_opt_outs=[EmailKind(kind) for kind in user.email_opt_outs])


@router.post("/email/unsubscribe/{token}")
async def unsubscribe(
    token: EmailToken, session: SessionDep, kind: EmailKind | None = None
) -> EmailSettingsRead:
    """Turn off one kind of email, or all of them when no kind is given. Also the target of
    mail apps' one-click unsubscribe (RFC 8058), whose form body is ignored."""
    user = await _by_token(session, token)
    turned_off = set(user.email_opt_outs) | ({kind.value} if kind else {k.value for k in EmailKind})
    user.email_opt_outs = sorted(turned_off)
    await session.commit()
    return EmailSettingsRead(email_opt_outs=[EmailKind(k) for k in user.email_opt_outs])
