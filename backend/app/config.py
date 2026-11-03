from functools import lru_cache
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    # True when running as DigitalOcean Functions (short-lived, behind a transaction pooler).
    serverless: bool = False
    database_url: str = "postgresql+asyncpg://boardgame:boardgame@localhost:5432/boardgamegroup"

    # Kinde business domain, e.g. https://yourname.kinde.com. Also the token issuer.
    kinde_domain: str = ""
    # Audience of the Kinde API registered for this backend.
    kinde_audience: str = ""

    # BoardGameGeek XML API application token (secret).
    bgg_api_token: str = ""
    # BGG asks for roughly 5 seconds between requests.
    bgg_min_interval_seconds: float = 5.0
    # Cached game details older than this are re-fetched when next viewed.
    game_refresh_days: int = 30

    @field_validator("database_url")
    @classmethod
    def use_asyncpg_driver(cls, url: str) -> str:
        """Accept a plain Postgres URL (as Supabase hands out) and adapt it for asyncpg."""
        parts = urlsplit(url)
        scheme = (
            "postgresql+asyncpg" if parts.scheme in ("postgres", "postgresql") else parts.scheme
        )
        # asyncpg spells libpq's sslmode as ssl.
        query = [
            ("ssl" if key == "sslmode" else key, value) for key, value in parse_qsl(parts.query)
        ]
        return urlunsplit(parts._replace(scheme=scheme, query=urlencode(query)))

    @field_validator("kinde_domain")
    @classmethod
    def strip_trailing_slash(cls, domain: str) -> str:
        return domain.rstrip("/")


@lru_cache
def get_settings() -> Settings:
    return Settings()
