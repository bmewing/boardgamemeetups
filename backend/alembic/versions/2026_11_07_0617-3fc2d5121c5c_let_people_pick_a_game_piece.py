"""let people pick a game piece

Revision ID: 3fc2d5121c5c
Revises: fc4590ef4cfd
Create Date: 2026-11-07 06:17:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3fc2d5121c5c"
down_revision: str | Sequence[str] | None = "fc4590ef4cfd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Plain strings: the app checks the names (app.pieces), so new pieces need no migration.
    op.add_column("users", sa.Column("piece", sa.String(length=32), nullable=True))
    op.add_column("users", sa.Column("piece_color", sa.String(length=16), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "piece_color")
    op.drop_column("users", "piece")
