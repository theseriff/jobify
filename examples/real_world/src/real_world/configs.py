"""Module for loading application configurations from environment variables."""

import os
from typing import NamedTuple
from zoneinfo import ZoneInfo


class Configs(NamedTuple):
    """Configuration settings for the application."""

    tz: ZoneInfo
    cron: str
    db_file_path: str

    @classmethod
    def from_env(cls) -> "Configs":
        """Load configurations from environment variables with defaults."""
        return cls(
            tz=ZoneInfo(os.getenv("TZ", "UTC")),
            cron=os.getenv("CRON", "@daily"),  # Default to midnight
            db_file_path=os.getenv("DB_FILE_PATH", "db.sqlite"),
        )
