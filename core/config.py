import os


class Settings:
    TESTING: bool = os.getenv("TESTING", "0") == "1"
    SQL_ECHO: bool = os.getenv("SQL_ECHO", "1") == "1"

    ASYNC_DATABASE_URL: str = os.getenv(
        "ASYNC_DATABASE_URL", "postgresql+asyncpg://pulsinator@localhost:5432/pulse"
    )

    SYNC_DATABASE_URL: str = os.getenv(
        "SYNC_DATABASE_URL", "postgresql+psycopg://pulsinator@localhost:5432/pulse"
    )


settings = Settings()
