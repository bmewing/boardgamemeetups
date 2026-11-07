"""allow repeat plays and keep their order

Revision ID: fc4590ef4cfd
Revises: dcd10ad7b0ec
Create Date: 2026-11-06 19:28:54.231435

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "fc4590ef4cfd"
down_revision: str | Sequence[str] | None = "dcd10ad7b0ec"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Existing plays all start at 0, so they keep showing A-Z as before.
    op.add_column("plays", sa.Column("position", sa.Integer(), server_default="0", nullable=False))
    op.drop_index(op.f("uq_plays_meetup_game"), table_name="plays")


def downgrade() -> None:
    """Downgrade schema."""
    # Fails if any night has the same game logged twice; remove those repeats first.
    op.create_index(op.f("uq_plays_meetup_game"), "plays", ["meetup_id", "game_id"], unique=True)
    op.drop_column("plays", "position")
