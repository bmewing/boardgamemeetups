"""let people add games that are not on bgg

Revision ID: 224381d42b8a
Revises: 3fc2d5121c5c
Create Date: 2026-11-07 06:27:14.497290

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "224381d42b8a"
down_revision: str | Sequence[str] | None = "3fc2d5121c5c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Games not on BGG take ids counting down from -1, clear of BGG's.
    op.execute(
        "CREATE SEQUENCE custom_game_ids INCREMENT BY -1 MINVALUE -2147483648 MAXVALUE -1 START -1"
    )
    op.add_column("games", sa.Column("created_by_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_games_created_by_id_users"),
        "games",
        "users",
        ["created_by_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Leaves any games people added; delete them (ids below 0) first to get rid of them.
    op.drop_constraint(op.f("fk_games_created_by_id_users"), "games", type_="foreignkey")
    op.drop_column("games", "created_by_id")
    op.execute("DROP SEQUENCE custom_game_ids")
