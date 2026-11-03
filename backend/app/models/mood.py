from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Mood(Base):
    """One entry in the shared mood list: used to tag games and to pick an RSVP mood.

    Moods that aren't `taggable` can't be put on a game: either they describe a meetup's
    history ("Something new") or they come from BGG's own data (co-op, from the mechanics).
    The rows are seeded by migrations.
    """

    __tablename__ = "moods"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(String(255))
    taggable: Mapped[bool] = mapped_column(Boolean)
    sort_order: Mapped[int] = mapped_column(Integer)
