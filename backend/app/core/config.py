from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    APP_NAME: str = "WordleStack"
    DEBUG: bool = False

    DATABASE_URL: str

    SECRET_KEY: str

    ADMIN_USERNAME: str
    ADMIN_PASSWORD: str

    TIMEZONE: str = "Asia/Kolkata"

    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()