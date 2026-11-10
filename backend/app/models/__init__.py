"""ORM models. Import every model module here so Alembic autogenerate sees it."""

from app.db import Base
from app.models.achievement import UserAchievement
from app.models.bgg_throttle import BggThrottle
from app.models.calendar import CalendarFeed
from app.models.discord import DiscordCard, DiscordChannel
from app.models.friend import Friendship, FriendshipStatus, InviteLink, UserBlock
from app.models.game import CUSTOM_GAME_IDS, Game, PlayerCountVotes, is_custom_id
from app.models.group import (
    Group,
    GroupInvite,
    GroupKind,
    GroupMember,
    GroupRole,
    Meetup,
    MeetupRsvp,
    MeetupRsvpMood,
    MeetupStatus,
    RsvpResponse,
)
from app.models.mood import Mood
from app.models.play import (
    BringAssignment,
    MeetupAttendee,
    MeetupNomination,
    MeetupVote,
    Play,
    PlayPlayer,
)
from app.models.rpg import (
    CUSTOM_RPG_SYSTEM_IDS,
    Character,
    CharacterStatus,
    RpgSystem,
    UserRpgSystem,
)
from app.models.user import CollectionVisibility, User
from app.models.user_game import (
    Ownership,
    PlayerCountVote,
    PlaytimeFeel,
    RemovedGame,
    Source,
    UserGame,
    UserGameMood,
    UserGamePlayerCount,
)

__all__ = [
    "CUSTOM_GAME_IDS",
    "CUSTOM_RPG_SYSTEM_IDS",
    "Base",
    "BggThrottle",
    "BringAssignment",
    "CalendarFeed",
    "Character",
    "CharacterStatus",
    "CollectionVisibility",
    "DiscordCard",
    "DiscordChannel",
    "Friendship",
    "FriendshipStatus",
    "Game",
    "Group",
    "GroupInvite",
    "GroupKind",
    "GroupMember",
    "GroupRole",
    "InviteLink",
    "Meetup",
    "MeetupAttendee",
    "MeetupNomination",
    "MeetupRsvp",
    "MeetupRsvpMood",
    "MeetupStatus",
    "MeetupVote",
    "Mood",
    "Ownership",
    "Play",
    "PlayPlayer",
    "PlayerCountVote",
    "PlayerCountVotes",
    "PlaytimeFeel",
    "RemovedGame",
    "RpgSystem",
    "RsvpResponse",
    "Source",
    "User",
    "UserAchievement",
    "UserBlock",
    "UserGame",
    "UserGameMood",
    "UserGamePlayerCount",
    "UserRpgSystem",
    "is_custom_id",
]
