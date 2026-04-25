from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gemini_api_key: str = ""
    secret_key: str = "change-me-in-production-32-chars-min"
    database_url: str = "sqlite+aiosqlite:///./wellness.db"
    cors_origins: str = "http://localhost:5173"
    embedding_cache_size: int = 1000
    access_token_expire_days: int = 30

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]


@lru_cache
def get_settings() -> Settings:
    return Settings()
