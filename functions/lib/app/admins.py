"""Make or unmake admins from the command line, for the first admin and any lockout.

Once someone is an admin they can promote others in the admin portal. From backend/:

    uv run python -m app.admins grant you@example.com
    uv run python -m app.admins revoke someone@example.com
    uv run python -m app.admins list

Add `--env-file .env.production` after `uv run` to act on production. The person must have
signed in to the app at least once, so their account exists.
"""

import asyncio
import sys

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SessionLocal
from app.models import User

USAGE = "usage: python -m app.admins grant|revoke EMAIL  |  python -m app.admins list"


async def set_admin(session: AsyncSession, email: str, is_admin: bool) -> User | None:
    """Grant or revoke admin for the account with this email. None if there's no such account."""
    user = await session.scalar(
        select(User).where(func.lower(User.email) == email.strip().lower()).limit(1)
    )
    if user is None:
        return None
    user.is_admin = is_admin
    await session.commit()
    return user


async def list_admins(session: AsyncSession) -> list[User]:
    return list(
        await session.scalars(
            select(User).where(User.is_admin).order_by(func.lower(User.display_name))
        )
    )


async def main(args: list[str]) -> int:
    async with SessionLocal() as session:
        if args == ["list"]:
            admins = await list_admins(session)
            for admin in admins:
                print(f"{admin.display_name} <{admin.email}>")
            if not admins:
                print("No admins yet.")
            return 0
        if len(args) == 2 and args[0] in ("grant", "revoke"):
            user = await set_admin(session, args[1], args[0] == "grant")
            if user is None:
                print(f"No account uses {args[1]}. Sign in to the app with it first.")
                return 1
            now = "now" if user.is_admin else "no longer"
            print(f"{user.display_name} <{user.email}> is {now} an admin.")
            return 0
    print(USAGE)
    return 2


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
