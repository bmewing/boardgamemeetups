"""The game pieces people pick to stand for them around the app.

The frontend draws each one (frontend/src/components/pieces.tsx); these are only the names.
Someone who hasn't picked is shown as a meeple in a color worked out from their id.
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
