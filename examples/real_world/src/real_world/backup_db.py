"""A backup db.

that backs up a database file randomly 3 times a day and syncs to GitHub.
"""

import asyncio
import logging
import secrets
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from jobify import INJECT, JobRouter, State

if TYPE_CHECKING:
    from real_world.configs import Configs


logger = logging.getLogger(__name__)
backup_router = JobRouter()


def backup_db(timestamp: str, file_path: Path) -> Path | None:
    """Create a backup of the database file."""
    if not file_path.exists():
        logger.warning("Database file not found: %s", file_path)
        return None

    backup_path = file_path.with_name(f"{file_path.stem}_{timestamp}.bak")

    _ = shutil.copy2(file_path, backup_path)
    logger.info("Backup created: %s", backup_path)
    return backup_path


async def sync_github(timestamp: str, file_path: Path) -> None:
    """Sync changes to GitHub by committing and pushing."""
    commands = [
        ("git", "add", file_path),
        ("git", "commit", "-m", f"Backup: {timestamp}"),
        ("git", "push"),
    ]
    for cmd in commands:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        output = f"{stdout.decode()}{stderr.decode()}"
        logger.info(output)


@backup_router.task
async def perform_backup(state: State = INJECT) -> None:
    """Perform the database backup and sync to GitHub."""
    configs: Configs = state.configs
    timestamp = datetime.now(configs.tz).strftime("%Y%m%d_%H%M%S")
    backup_path = backup_db(timestamp, Path(configs.db_file_path))
    if backup_path is not None:
        await sync_github(timestamp, backup_path)


@backup_router.task(name="Planning future backups")
async def schedule_daily_backups(state: State = INJECT) -> None:
    """Schedule database backups randomly 3 times a day."""
    configs: Configs = state.configs
    midnight = datetime.now(configs.tz).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    # 24 hours in milliseconds
    day_duration_ms = 24 * 60 * 60 * 1000

    for _ in range(3):
        mills = secrets.randbelow(day_duration_ms)
        run_at = midnight + timedelta(milliseconds=mills)
        _ = await perform_backup.schedule().at(run_at)
