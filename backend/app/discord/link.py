"""Links that tie a Discord account to an account here.

The bot shows the link only to the person who asked for it. It carries their Discord ID
and name, signed so it can't be altered, and works for a short while. Opening it while
signed in links the two accounts.
"""

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.config import get_settings

LIFETIME = timedelta(minutes=15)


@dataclass(frozen=True)
class DiscordAccount:
    id: str
    username: str


def _encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _key() -> bytes:
    """Derived from the bot token, the one secret the bot already has."""
    token = get_settings().discord_bot_token
    if not token:
        raise RuntimeError("DISCORD_BOT_TOKEN is not set")
    return hashlib.sha256(b"bggroup discord link:" + token.encode()).digest()


def _sign(body: str) -> str:
    return _encode(hmac.new(_key(), body.encode(), hashlib.sha256).digest())


def make_token(account: DiscordAccount, now: datetime | None = None) -> str:
    expires = (now or datetime.now(UTC)) + LIFETIME
    payload = {"id": account.id, "name": account.username, "exp": int(expires.timestamp())}
    body = _encode(json.dumps(payload, separators=(",", ":")).encode())
    return f"{body}.{_sign(body)}"


def link_url(account: DiscordAccount) -> str:
    return f"{get_settings().app_url}/discord/link/{make_token(account)}"


def read_token(token: str, now: datetime | None = None) -> DiscordAccount | None:
    """The account a link is for, or None if it's been altered or has expired."""
    body, _, signature = token.partition(".")
    if not body or not signature or not get_settings().discord_bot_token:
        return None
    if not hmac.compare_digest(signature, _sign(body)):
        return None
    try:
        payload = json.loads(_decode(body))
        account = DiscordAccount(id=str(payload["id"]), username=str(payload["name"]))
        expires = int(payload["exp"])
    except (ValueError, KeyError, TypeError):
        return None
    if (now or datetime.now(UTC)).timestamp() > expires:
        return None
    return account
