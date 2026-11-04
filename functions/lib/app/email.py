"""Sending email through Resend, and what every email looks like.

Each recipient gets an email of their own, so nobody sees anyone else's address. Sending
never raises: a failure is logged and reported back as False, so whatever caused the email
(a friend request, a locked pick) still succeeds.
"""

import html
import logging
import secrets
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Annotated, Protocol

import httpx
from fastapi import Depends

from app.config import get_settings
from app.models import User

logger = logging.getLogger(__name__)

RESEND_BATCH_URL = "https://api.resend.com/emails/batch"
RESEND_BATCH_LIMIT = 100


class EmailKind(StrEnum):
    """The kinds of email someone can turn off one by one."""

    FRIEND_REQUEST = "friend_request"
    GROUP_INVITE = "group_invite"
    RSVP_REMINDER = "rsvp_reminder"
    PICK_LOCKED = "pick_locked"
    BRINGING = "bringing"
    DATE_CHANGED = "date_changed"


# What each kind is, as a phrase that follows "emails about".
KIND_NAMES = {
    EmailKind.FRIEND_REQUEST: "friend requests",
    EmailKind.GROUP_INVITE: "group invites",
    EmailKind.RSVP_REMINDER: "dates you haven't answered",
    EmailKind.PICK_LOCKED: "the games picked for a date",
    EmailKind.BRINGING: "games you're bringing",
    EmailKind.DATE_CHANGED: "dates that change or are cancelled",
}


@dataclass(frozen=True)
class Email:
    to: str
    subject: str
    text: str
    html: str
    headers: dict[str, str] = field(default_factory=dict)


class Mailer(Protocol):
    async def send(self, emails: Sequence[Email]) -> bool:
        """Send them all; False if any batch failed (already logged)."""
        ...


class ResendMailer:
    def __init__(self, api_key: str, sender: str, reply_to: str) -> None:
        self.api_key = api_key
        self.sender = sender
        self.reply_to = reply_to

    async def send(self, emails: Sequence[Email]) -> bool:
        if not emails:
            return True
        ok = True
        async with httpx.AsyncClient(
            timeout=10, headers={"Authorization": f"Bearer {self.api_key}"}
        ) as http:
            for start in range(0, len(emails), RESEND_BATCH_LIMIT):
                batch = emails[start : start + RESEND_BATCH_LIMIT]
                payload = [
                    {
                        "from": self.sender,
                        "to": [email.to],
                        **({"reply_to": [self.reply_to]} if self.reply_to else {}),
                        "subject": email.subject,
                        "text": email.text,
                        "html": email.html,
                        **({"headers": email.headers} if email.headers else {}),
                    }
                    for email in batch
                ]
                try:
                    response = await http.post(RESEND_BATCH_URL, json=payload)
                except httpx.HTTPError:
                    logger.exception("Sending %d emails (%s) failed", len(batch), batch[0].subject)
                    ok = False
                    continue
                if response.is_error:
                    logger.error(
                        "Sending %d emails (%s) failed: %s %s",
                        len(batch),
                        batch[0].subject,
                        response.status_code,
                        response.text,
                    )
                    ok = False
        return ok


class LogMailer:
    """Stands in when there's no Resend key (local development): logs instead of sending."""

    async def send(self, emails: Sequence[Email]) -> bool:
        for email in emails:
            logger.info("Email to %s: %s\n%s", email.to, email.subject, email.text)
        return True


def get_mailer() -> Mailer:
    settings = get_settings()
    if settings.resend_api_key:
        return ResendMailer(settings.resend_api_key, settings.email_from, settings.email_reply_to)
    return LogMailer()


MailerDep = Annotated[Mailer, Depends(get_mailer)]


@dataclass
class Message:
    """What an email says. Rendered as plain text and as simple HTML."""

    subject: str
    paragraphs: list[str]
    link: tuple[str, str] | None = None  # (label, url)
    items: list[str] = field(default_factory=list)  # a list after the first paragraph
    after: list[str] = field(default_factory=list)  # paragraphs after the link


def wants(user: User, kind: EmailKind) -> bool:
    return bool(user.email) and kind.value not in (user.email_opt_outs or [])


def ensure_token(user: User) -> str:
    """The user's unsubscribe secret, made on first use. The caller commits it."""
    if user.email_token is None:
        user.email_token = secrets.token_urlsafe(24)
    return user.email_token


def to_user(user: User, kind: EmailKind, message: Message) -> Email:
    """An email to a user, with links to turn this kind of email off. Check `wants` first."""
    assert user.email
    settings = get_settings()
    token = ensure_token(user)
    page = f"{settings.app_url}/unsubscribe/{token}?kind={kind.value}"
    footer = [
        (
            f"You're getting this because you're on Board Game Group as {user.display_name}.",
            None,
        ),
        (f"Stop emails about {KIND_NAMES[kind]}", page),
        ("All email settings", f"{settings.app_url}/profile"),
    ]
    headers = {
        # One-click unsubscribe (RFC 8058): mail apps POST straight to the API.
        "List-Unsubscribe": f"<{settings.api_url}/api/email/unsubscribe/{token}?kind={kind.value}>",
        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
    }
    return _render(user.email, message, footer, headers)


def to_address(address: str, message: Message) -> Email:
    """An email to someone who isn't on the app (yet), so has nothing to unsubscribe from."""
    footer: list[tuple[str, str | None]] = [
        ("Not expecting this? You can ignore it; nothing happens unless you sign up.", None)
    ]
    return _render(address, message, footer, {})


def _render(
    to: str, message: Message, footer: list[tuple[str, str | None]], headers: dict[str, str]
) -> Email:
    text_parts: list[str] = []
    html_parts: list[str] = []
    for index, paragraph in enumerate(message.paragraphs):
        text_parts.append(paragraph)
        html_parts.append(f"<p>{html.escape(paragraph)}</p>")
        if index == 0 and message.items:
            text_parts.append("\n".join(f"- {item}" for item in message.items))
            html_parts.append(
                "<ul>"
                + "".join(f"<li>{html.escape(item)}</li>" for item in message.items)
                + "</ul>"
            )
    if message.link:
        label, url = message.link
        text_parts.append(f"{label}: {url}")
        html_parts.append(
            f'<p><a href="{html.escape(url)}" style="{BUTTON_STYLE}">{html.escape(label)}</a></p>'
        )
    for paragraph in message.after:
        text_parts.append(paragraph)
        html_parts.append(f"<p>{html.escape(paragraph)}</p>")

    text_footer = "\n".join(f"{label}: {url}" if url else label for label, url in footer)
    html_footer = "<br>".join(
        f'<a href="{html.escape(url)}" style="color:#868e96">{html.escape(label)}</a>'
        if url
        else html.escape(label)
        for label, url in footer
    )
    text = "\n\n".join(text_parts) + "\n\n--\n" + text_footer + "\n"
    body = (
        f'<div style="{BODY_STYLE}">'
        + "".join(html_parts)
        + '<hr style="border:none;border-top:1px solid #dee2e6;margin:24px 0 12px">'
        + f'<p style="font-size:12px;color:#868e96">{html_footer}</p></div>'
    )
    return Email(to=to, subject=message.subject, text=text, html=body, headers=headers)


BODY_STYLE = (
    "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;"
    "font-size:15px;line-height:1.5;color:#212529;max-width:560px"
)
BUTTON_STYLE = (
    "display:inline-block;background:#1c7ed6;color:#ffffff;text-decoration:none;"
    "padding:10px 18px;border-radius:6px;font-weight:600"
)
