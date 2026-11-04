"""ORM models. Import every model module here so Alembic autogenerate sees it."""

from app.db import Base
from app.models.bgg_throttle import BggThrottle
from app.models.calendar import CalendarFeed
from app.models.friend import Friendship, FriendshipStatus, InviteLink, UserBlock
from app.models.game import Game, PlayerCountVotes
from app.models.group import (
    Group,
    GroupInvite,
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
    "Base",
    "BggThrottle",
    "BringAssignment",
    "CalendarFeed",
    "CollectionVisibility",
    "Friendship",
    "FriendshipStatus",
    "Game",
    "Group",
    "GroupInvite",
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
    "RsvpResponse",
    "Source",
    "User",
    "UserBlock",
    "UserGame",
    "UserGameMood",
    "UserGamePlayerCount",
]
