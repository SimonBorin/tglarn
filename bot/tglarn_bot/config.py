"""Runtime configuration for the Telegram bot."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

MapView = Literal["medium", "wide", "max"]
GameAdapterName = Literal["placeholder", "relarn_process"]
_VALID_MAP_VIEWS = frozenset({"medium", "wide", "max"})
_LEGACY_MAP_VIEW_ALIASES = {
    "compact": "medium",
    "normal": "medium",
    "desktop": "max",
    "max_size": "max",
    "maximum": "max",
}


class Settings(BaseSettings):
    """Settings loaded from environment variables and optional .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    bot_token: str = Field(alias="TG_LARN_BOT_TOKEN")
    mongo_uri: str = Field(
        default="mongodb://localhost:27017/tglarn",
        alias="MONGO_URI",
    )
    mongo_database: str = Field(default="tglarn", alias="MONGO_DATABASE")
    default_map_view: MapView = Field(default="wide", alias="DEFAULT_MAP_VIEW")
    game_adapter: GameAdapterName = Field(default="placeholder", alias="GAME_ADAPTER")
    relarn_binary_path: str = Field(
        default="/opt/relarn/lib/relarn/relarn.bin",
        alias="RELARN_BINARY_PATH",
    )
    relarn_install_root: str = Field(default="/opt/relarn", alias="RELARN_INSTALL_ROOT")
    relarn_cycle_timeout_seconds: float = Field(
        default=3.0,
        alias="RELARN_CYCLE_TIMEOUT_SECONDS",
    )
    relarn_cycle_settle_seconds: float = Field(
        default=0.12,
        alias="RELARN_CYCLE_SETTLE_SECONDS",
    )
    active_session_ttl_seconds: float = Field(
        default=180.0,
        alias="ACTIVE_SESSION_TTL_SECONDS",
    )
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    database_startup_attempts: int = Field(default=30, alias="DATABASE_STARTUP_ATTEMPTS")
    database_startup_delay_seconds: float = Field(
        default=2.0,
        alias="DATABASE_STARTUP_DELAY_SECONDS",
    )

    @field_validator("bot_token")
    @classmethod
    def validate_bot_token(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("TG_LARN_BOT_TOKEN is required")
        return value.strip()

    @field_validator("default_map_view", mode="before")
    @classmethod
    def normalize_default_map_view(cls, value: object) -> str:
        normalized = str(value).strip().lower()
        normalized = _LEGACY_MAP_VIEW_ALIASES.get(normalized, normalized)
        if normalized not in _VALID_MAP_VIEWS:
            expected = ", ".join(sorted(_VALID_MAP_VIEWS))
            raise ValueError(f"DEFAULT_MAP_VIEW must be one of: {expected}")
        return normalized


    @field_validator("game_adapter", mode="before")
    @classmethod
    def normalize_game_adapter(cls, value: object) -> str:
        normalized = str(value).strip().lower().replace("-", "_")
        if normalized in {"relarn", "original", "upstream"}:
            return "relarn_process"
        if normalized not in {"placeholder", "relarn_process"}:
            raise ValueError("GAME_ADAPTER must be placeholder or relarn_process")
        return normalized


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
