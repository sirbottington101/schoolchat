from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://schoolchat:schoolchat@db:5432/schoolchat"

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # JWT
    jwt_secret: str = "CHANGE_ME"
    jwt_access_expire_minutes: int = 15
    jwt_refresh_expire_days: int = 7

    # Encryption
    encryption_key: str = "CHANGE_ME"

    # Server
    server_name: str = "SchoolChat"
    allowed_origins: str = "*"

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
