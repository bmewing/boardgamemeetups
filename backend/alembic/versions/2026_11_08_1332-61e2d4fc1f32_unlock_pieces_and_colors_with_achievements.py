"""unlock pieces and colors with achievements

Revision ID: 61e2d4fc1f32
Revises: ff0a7a379779
Create Date: 2026-11-08 13:32:29.319645

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "61e2d4fc1f32"
down_revision: str | Sequence[str] | None = "ff0a7a379779"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RUNNERS = "m.role IN ('owner', 'admin')"
GROUP_SIZES = "SELECT group_id, count(*) AS size FROM group_members GROUP BY group_id"

# Who has already earned each achievement: a query for their user ids, as near as the data
# shows it. Who brought whom to the app was never kept, so the referral ones start fresh.
BACKFILL = {
    "add_game": "SELECT user_id FROM user_games",
    "import_collection": """
        SELECT id FROM users WHERE bgg_pulled_at IS NOT NULL
        UNION SELECT user_id FROM user_games WHERE source IN ('bgg', 'file')
    """,
    "can_teach": "SELECT user_id FROM user_games WHERE can_teach",
    "rate_games": """
        SELECT user_id FROM user_games WHERE rating IS NOT NULL
        GROUP BY user_id HAVING count(*) >= 10
    """,
    "stay_in_loop": """
        SELECT id FROM users WHERE discord_id IS NOT NULL
        UNION SELECT user_id FROM calendar_feeds WHERE revoked_at IS NULL
    """,
    "make_friend": """
        SELECT user_low_id FROM friendships WHERE status = 'accepted'
        UNION SELECT user_high_id FROM friendships WHERE status = 'accepted'
    """,
    "friends_5": """
        SELECT user_id FROM (
            SELECT user_low_id AS user_id FROM friendships WHERE status = 'accepted'
            UNION ALL SELECT user_high_id FROM friendships WHERE status = 'accepted'
        ) AS sides GROUP BY user_id HAVING count(*) >= 5
    """,
    "start_group": "SELECT user_id FROM group_members WHERE role = 'owner'",
    # Who added a date isn't kept, so anyone running a group that has dates.
    "schedule_meetup": f"""
        SELECT m.user_id FROM group_members m JOIN groups g ON g.id = m.group_id
        WHERE {RUNNERS}
          AND (g.schedule IS NOT NULL OR EXISTS (SELECT 1 FROM meetups WHERE group_id = g.id))
    """,
    "group_of_4": f"""
        SELECT m.user_id FROM group_members m JOIN ({GROUP_SIZES}) s ON s.group_id = m.group_id
        WHERE {RUNNERS} AND s.size >= 4
    """,
    # Likewise who locked or logged, so anyone running a group where it happened.
    "lock_pick": f"""
        SELECT m.user_id FROM group_members m JOIN meetups t ON t.group_id = m.group_id
        WHERE {RUNNERS} AND t.picks_locked_at IS NOT NULL
    """,
    "log_night": f"""
        SELECT m.user_id FROM group_members m JOIN meetups t ON t.group_id = m.group_id
        WHERE {RUNNERS} AND t.logged_at IS NOT NULL AND NOT t.log_assumed
    """,
    "join_group": "SELECT user_id FROM group_members WHERE role <> 'owner'",
    "rsvp_yes": "SELECT user_id FROM meetup_rsvps WHERE response = 'yes'",
    "nominate_picked": "SELECT nominated_by_id FROM meetup_nominations WHERE picked",
    "vote": """
        SELECT v.user_id FROM meetup_votes v JOIN meetup_nominations n ON n.id = v.nomination_id
        WHERE n.nominated_by_id IS DISTINCT FROM v.user_id
    """,
    "bring_game": "SELECT user_id FROM bring_assignments",
    "attend_1": "SELECT user_id FROM meetup_attendees",
    "attend_5": "SELECT user_id FROM meetup_attendees GROUP BY user_id HAVING count(*) >= 5",
    "attend_20": "SELECT user_id FROM meetup_attendees GROUP BY user_id HAVING count(*) >= 20",
    "win_game": """
        SELECT pp.user_id FROM play_players pp JOIN plays p ON p.id = pp.play_id
        WHERE pp.won OR (p.coop AND p.coop_won)
    """,
    "coop_win": """
        SELECT pp.user_id FROM play_players pp JOIN plays p ON p.id = pp.play_id
        WHERE p.coop AND p.coop_won
    """,
}


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "user_achievements",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        # A plain string: the app checks the names, so new achievements need no migration.
        sa.Column("achievement", sa.String(length=32), nullable=False),
        sa.Column(
            "earned_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_achievements_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", "achievement", name=op.f("pk_user_achievements")),
    )
    op.add_column("users", sa.Column("referred_by_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_users_referred_by_id_users"),
        "users",
        "users",
        ["referred_by_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Credit what people did before pieces were locked, so nobody loses much they could
    # pick yesterday (and a piece already picked stays theirs). Marked seen: none of it is news.
    for achievement, user_ids in BACKFILL.items():
        op.execute(
            f"""
            INSERT INTO user_achievements (user_id, achievement, seen_at)
            SELECT DISTINCT earned.user_id, '{achievement}', now()
            FROM ({user_ids}) AS earned (user_id)
            WHERE earned.user_id IS NOT NULL
            ON CONFLICT DO NOTHING
            """
        )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(op.f("fk_users_referred_by_id_users"), "users", type_="foreignkey")
    op.drop_column("users", "referred_by_id")
    op.drop_table("user_achievements")
