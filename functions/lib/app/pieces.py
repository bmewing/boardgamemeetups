"""The game pieces people pick to stand for them around the app.

These are only the names. The frontend draws each one from
frontend/src/components/pieces/svg/<name>.svg and labels it in pieces/shapes.ts.
Someone who hasn't picked is shown as a meeple in a color worked out from their id.
Most pieces are locked until an achievement unlocks them (app.achievements).
"""

from enum import StrEnum


class Piece(StrEnum):
    # Pieces from the table
    MEEPLE = "meeple"
    PAWN = "pawn"
    CUBE = "cube"
    DIE = "die"
    ROOK = "rook"
    KNIGHT = "knight"
    CROWN = "crown"
    # The classic metal tokens
    TOP_HAT = "top_hat"
    RACE_CAR = "race_car"
    DOG = "dog"
    THIMBLE = "thimble"
    BOOT = "boot"
    BATTLESHIP = "battleship"
    IRON = "iron"
    WHEELBARROW = "wheelbarrow"
    # Odds and ends
    CAT = "cat"
    DUCK = "duck"
    ROCKET = "rocket"


class PieceColor(StrEnum):
    TEAL = "teal"
    CORAL = "coral"
    GOLD = "gold"
    CREAM = "cream"
    SLATE = "slate"
    PLUM = "plum"
    LEAF = "leaf"
    SKY = "sky"
    ORANGE = "orange"


class Achievement(StrEnum):
    """Things people do around the app, which unlock pieces and colors (app.achievements).
    Grouped here the way the profile shows them."""

    # Getting set up
    ADD_GAME = "add_game"  # put a game on your list
    IMPORT_COLLECTION = "import_collection"  # bring games in from BGG or a file
    CAN_TEACH = "can_teach"  # mark a game you can teach
    RATE_GAMES = "rate_games"  # rate enough of your games
    STAY_IN_LOOP = "stay_in_loop"  # link Discord or subscribe to the calendar feed
    # Bringing people in
    MAKE_FRIEND = "make_friend"
    FRIENDS_5 = "friends_5"
    RECRUIT = "recruit"  # someone new joins through your invite
    RECRUIT_ATTENDS = "recruit_attends"  # ...and comes to a game night
    JOINED_BY_INVITE = "joined_by_invite"  # you came in through someone's invite
    # Running a group
    START_GROUP = "start_group"
    SCHEDULE_MEETUP = "schedule_meetup"  # add a date, or give a group a schedule
    GROUP_OF_4 = "group_of_4"  # a group you run has enough members for a table
    LOCK_PICK = "lock_pick"
    LOG_NIGHT = "log_night"
    # At the table
    JOIN_GROUP = "join_group"  # accept an invite to someone else's group
    RSVP_YES = "rsvp_yes"
    NOMINATE_PICKED = "nominate_picked"  # a game you put forward gets picked
    VOTE = "vote"  # vote for a game someone else put forward
    BRING_GAME = "bring_game"
    ATTEND_1 = "attend_1"  # game nights come to, as play logs record it
    ATTEND_5 = "attend_5"
    ATTEND_20 = "attend_20"
    WIN_GAME = "win_game"
    COOP_WIN = "coop_win"
