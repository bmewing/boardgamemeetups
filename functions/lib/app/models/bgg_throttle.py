from datetime import datetime

from sqlalchemy import DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class BggThrottle(Base):
    """A single row: when the next request to BGG may start. See app.bgg.throttle."""

    __tablename__ = "bgg_throttle"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    next_request_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
