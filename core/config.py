import os


class Settings:
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "postgresql+asyncpg://pulsinator@localhost:5432/pulse"
    )
    TESTING: bool = os.getenv("TESTING", "0") == "1"
    SQL_ECHO: bool = os.getenv("SQL_ECHO", "1") == "1"


settings = Settings()
