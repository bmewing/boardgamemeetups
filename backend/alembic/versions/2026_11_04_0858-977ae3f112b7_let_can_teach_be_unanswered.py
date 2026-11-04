"""let can teach be unanswered

Revision ID: 977ae3f112b7
Revises: 9a06778f3072
Create Date: 2026-11-04 08:58:16.505796

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "977ae3f112b7"
down_revision: str | Sequence[str] | None = "9a06778f3072"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "user_games",
        "can_teach",
        existing_type=sa.BOOLEAN(),
        nullable=True,
        server_default=None,
        existing_server_default=sa.text("false"),
    )
    # Until now "no" was also what an unanswered box held, so it can't be told apart from a
    # real "no". Treat every "no" as unanswered: owners then count as able to teach, and can
    # untick it again.
    op.execute("UPDATE user_games SET can_teach = NULL WHERE can_teach = false")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("UPDATE user_games SET can_teach = false WHERE can_teach IS NULL")
    op.alter_column(
        "user_games",
        "can_teach",
        existing_type=sa.BOOLEAN(),
        nullable=False,
        server_default=sa.text("false"),
    )
