import os
from pathlib import Path

from dotenv import load_dotenv

ENV_FILE = os.getenv("ENV_FILE", ".env")
load_dotenv(Path(ENV_FILE))


class Settings:
    def __init__(self) -> None:
        self.ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
        self.TESTING = os.getenv("TESTING", "0") == "1"
        self.SQL_ECHO = os.getenv("SQL_ECHO", "1") == "1"

        self.ASYNC_DATABASE_SHARD0_URL = os.getenv(
            "ASYNC_DATABASE_SHARD0_URL",
            "postgresql+asyncpg://postgres:postgres@postgres_shard0:5432/pulse",
        )
        self.ASYNC_DATABASE_SHARD1_URL = os.getenv(
            "ASYNC_DATABASE_SHARD1_URL",
            "postgresql+asyncpg://postgres:postgres@postgres_shard1:5433/pulse",
        )
        self.SYNC_DATABASE_SHARD0_URL = os.getenv(
            "SYNC_DATABASE_SHARD0_URL",
            "postgresql+psycopg://postgres:postgres@postgres_shard0:5432/pulse",
        )
        self.SYNC_DATABASE_SHARD1_URL = os.getenv(
            "SYNC_DATABASE_SHARD1_URL",
            "postgresql+psycopg://postgres:postgres@postgres_shard1:5433/pulse",
        )
        self.REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.CELERY_RESULT_BACKEND = os.getenv(
            "CELERY_RESULT_BACKEND",
            "redis://localhost:6379/1",
        )


settings = Settings()
