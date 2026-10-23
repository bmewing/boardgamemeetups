from functools import lru_cache
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    database_url: str = "postgresql+asyncpg://boardgame:boardgame@localhost:5432/boardgamegroup"

    @field_validator("database_url")
    @classmethod
    def use_asyncpg_driver(cls, url: str) -> str:
        """Accept a plain Postgres URL (as Neon hands out) and adapt it for asyncpg."""
        parts = urlsplit(url)
        scheme = (
            "postgresql+asyncpg" if parts.scheme in ("postgres", "postgresql") else parts.scheme
        )
        query = []
        for key, value in parse_qsl(parts.query):
            if key == "sslmode":
                query.append(("ssl", value))
            elif key != "channel_binding":  # asyncpg doesn't accept it
                query.append((key, value))
        return urlunsplit(parts._replace(scheme=scheme, query=urlencode(query)))


@lru_cache
def get_settings() -> Settings:
    return Settings()
