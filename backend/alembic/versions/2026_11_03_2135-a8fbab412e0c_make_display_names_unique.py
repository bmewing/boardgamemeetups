"""make display names unique

Display names double as usernames. Existing clashes (ignoring case and extra spaces) are
settled first: the earliest account keeps the name, later ones get " 2", " 3" and so on.

Revision ID: a8fbab412e0c
Revises: 6f5fcd19d051
Create Date: 2026-11-03 21:35:32.591887

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a8fbab412e0c"
down_revision: str | Sequence[str] | None = "6f5fcd19d051"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    connection = op.get_bind()
    users = connection.execute(
        sa.text("SELECT id, display_name FROM users ORDER BY created_at, id")
    ).all()
    taken: set[str] = set()
    renames: list[dict[str, object]] = []
    for user_id, name in users:
        base = " ".join(name.split())[:76] or "Player"
        candidate, n = base, 1
        while candidate.lower() in taken:
            n += 1
            candidate = f"{base} {n}"
        taken.add(candidate.lower())
        if candidate != name:
            renames.append({"id": user_id, "name": candidate})
    if renames:
        connection.execute(sa.text("UPDATE users SET display_name = :name WHERE id = :id"), renames)
    op.create_index(
        "uq_users_display_name_lower", "users", [sa.text("lower(display_name)")], unique=True
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("uq_users_display_name_lower", table_name="users")
