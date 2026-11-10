"""add rpg groups systems and characters

Revision ID: 4aab4dccdbdd
Revises: 61e2d4fc1f32
Create Date: 2026-11-10 13:00:21.627346

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4aab4dccdbdd"
down_revision: str | Sequence[str] | None = "61e2d4fc1f32"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Systems not on RPGGeek take ids counting down from -1, like custom games.
    op.execute(
        "CREATE SEQUENCE custom_rpg_system_ids "
        "INCREMENT BY -1 MINVALUE -2147483648 MAXVALUE -1 START -1"
    )
    op.create_table(
        "rpg_systems",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("name", sa.String(length=512), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("thumbnail_url", sa.String(length=1024), nullable=True),
        sa.Column("image_url", sa.String(length=1024), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column("details_fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name=op.f("fk_rpg_systems_created_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rpg_systems")),
    )
    op.create_index(
        "ix_rpg_systems_name_trgm",
        "rpg_systems",
        [sa.literal_column("lower(name) gin_trgm_ops")],
        unique=False,
        postgresql_using="gin",
    )
    op.create_table(
        "user_rpg_systems",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("system_id", sa.Integer(), nullable=False),
        sa.Column("knows", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("can_gm", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("want_to_play", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["system_id"],
            ["rpg_systems.id"],
            name=op.f("fk_user_rpg_systems_system_id_rpg_systems"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_rpg_systems_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", "system_id", name=op.f("pk_user_rpg_systems")),
    )
    op.create_index(
        op.f("ix_user_rpg_systems_system_id"), "user_rpg_systems", ["system_id"], unique=False
    )
    op.create_table(
        "characters",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("system_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("class_role", sa.String(length=120), nullable=True),
        sa.Column("level", sa.Integer(), nullable=True),
        sa.Column("ancestry", sa.String(length=120), nullable=True),
        sa.Column("pronouns", sa.String(length=40), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "active", "retired", "dead", name="characterstatus", native_enum=False, length=16
            ),
            server_default="active",
            nullable=False,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("portrait_url", sa.String(length=1024), nullable=True),
        sa.Column("sheet_url", sa.String(length=1024), nullable=True),
        sa.Column("group_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("level >= 0", name=op.f("ck_characters_level_not_negative")),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["groups.id"],
            name=op.f("fk_characters_group_id_groups"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["system_id"], ["rpg_systems.id"], name=op.f("fk_characters_system_id_rpg_systems")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_characters_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_characters")),
    )
    op.create_index(op.f("ix_characters_group_id"), "characters", ["group_id"], unique=False)
    op.create_index(op.f("ix_characters_user_id"), "characters", ["user_id"], unique=False)
    op.add_column(
        "group_members",
        sa.Column("is_gm", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "groups",
        sa.Column(
            "kind",
            sa.Enum("board_games", "rpg", name="groupkind", native_enum=False, length=16),
            server_default="board_games",  # every group so far plays board games
            nullable=False,
        ),
    )
    op.add_column("groups", sa.Column("rpg_system_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        op.f("fk_groups_rpg_system_id_rpg_systems"),
        "groups",
        "rpg_systems",
        ["rpg_system_id"],
        ["id"],
    )
    op.add_column("meetups", sa.Column("recap", sa.Text(), nullable=True))
    op.add_column(
        "meetups", sa.Column("recap_updated_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("meetups", "recap_updated_at")
    op.drop_column("meetups", "recap")
    op.drop_constraint(op.f("fk_groups_rpg_system_id_rpg_systems"), "groups", type_="foreignkey")
    op.drop_column("groups", "rpg_system_id")
    op.drop_column("groups", "kind")
    op.drop_column("group_members", "is_gm")
    op.drop_index(op.f("ix_characters_user_id"), table_name="characters")
    op.drop_index(op.f("ix_characters_group_id"), table_name="characters")
    op.drop_table("characters")
    op.drop_index(op.f("ix_user_rpg_systems_system_id"), table_name="user_rpg_systems")
    op.drop_table("user_rpg_systems")
    op.drop_index("ix_rpg_systems_name_trgm", table_name="rpg_systems", postgresql_using="gin")
    op.drop_table("rpg_systems")
    op.execute("DROP SEQUENCE custom_rpg_system_ids")
