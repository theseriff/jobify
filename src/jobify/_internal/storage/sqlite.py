import asyncio
import sqlite3
import threading
from collections.abc import Callable, Sequence
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, TypeVar
from zoneinfo import ZoneInfo

from typing_extensions import override

from jobify._internal.common.constants import JobStatus
from jobify._internal.storage.abc import (
    ScheduledJob,
    Storage,
    validate_table_name,
)

if TYPE_CHECKING:
    from concurrent.futures import ThreadPoolExecutor

    from jobify._internal.common.types import LoopFactory

CREATE_SCHEDULED_TABLE_QUERY = """
CREATE TABLE IF NOT EXISTS {} (
    job_id TEXT PRIMARY KEY,
    func_name TEXT,
    message BLOB,
    status TEXT,
    next_run_at TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

SELECT_SCHEDULES_QUERY = """
SELECT job_id, func_name, message, status, next_run_at
FROM {};
"""

INSERT_SCHEDULE_QUERY = """
INSERT INTO {} (job_id, func_name, message, status, next_run_at)
VALUES (?, ?, ?, ?, ?)
ON CONFLICT (job_id) DO UPDATE SET
    func_name = EXCLUDED.func_name,
    message = EXCLUDED.message,
    status = EXCLUDED.status,
    next_run_at = EXCLUDED.next_run_at,
    updated_at = CURRENT_TIMESTAMP;
"""

DELETE_SCHEDULE_QUERY = """
DELETE FROM {} WHERE job_id = ?;
"""

DELETE_SCHEDULE_MANY_QUERY = """
DELETE FROM {table_name} WHERE job_id IN ({placeholder});
"""

ReturnT = TypeVar("ReturnT")


class SQLiteStorage(Storage):
    def __init__(
        self,
        database: str | Path = "jobify.db",
        *,
        table_name: str = "jobify_schedules",
        timeout: float = 20.0,
    ) -> None:
        validate_table_name(table_name)
        self.database: Path = (
            Path(database) if isinstance(database, str) else database
        )
        self.table_name: str = table_name
        self.timeout: float = timeout
        self.tz: ZoneInfo = ZoneInfo("UTC")
        self.getloop: LoopFactory = asyncio._get_running_loop
        self.threadpool: ThreadPoolExecutor | None = None
        self._conn: sqlite3.Connection | None = None
        self._lock: threading.Lock = threading.Lock()

        self.create_scheduled_table_query: str = (
            CREATE_SCHEDULED_TABLE_QUERY.format(table_name)
        )
        self.select_schedules_query: str = SELECT_SCHEDULES_QUERY.format(
            table_name,
        )
        self.insert_schedule_query: str = INSERT_SCHEDULE_QUERY.format(
            table_name,
        )
        self.delete_schedule_query: str = DELETE_SCHEDULE_QUERY.format(
            table_name,
        )

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            msg = "Database not initialized. Call startup() first."
            raise RuntimeError(msg)
        return self._conn

    async def _to_thread(self, func: Callable[[], ReturnT]) -> ReturnT:
        def thread_safe() -> ReturnT:
            with self._lock:
                return func()

        loop = self.getloop()
        return await loop.run_in_executor(self.threadpool, thread_safe)

    @override
    async def startup(self) -> None:
        conn = sqlite3.connect(
            database=self.database,
            timeout=self.timeout,
            check_same_thread=False,
        )
        _ = conn.execute("PRAGMA journal_mode=WAL;")
        _ = conn.execute("PRAGMA synchronous=NORMAL;")
        _ = conn.execute(self.create_scheduled_table_query)
        conn.commit()
        self._conn = conn

    @override
    async def shutdown(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    @override
    async def get_schedules(self) -> list[ScheduledJob]:
        def get() -> list[ScheduledJob]:
            cursor = self.conn.execute(self.select_schedules_query)
            return [
                ScheduledJob(
                    job_id=row[0],
                    func_name=row[1],
                    message=row[2],
                    status=JobStatus(row[3]),
                    next_run_at=(
                        datetime.fromisoformat(row[4]).astimezone(self.tz)
                    ),
                )
                for row in cursor.fetchall()
            ]

        return await self._to_thread(get)

    @override
    async def add_schedule(self, *scheduled: ScheduledJob) -> None:
        def insert_many() -> None:
            with self.conn as conn:
                _ = conn.executemany(
                    self.insert_schedule_query,
                    [
                        (
                            sch.job_id,
                            sch.func_name,
                            sch.message,
                            sch.status,
                            sch.next_run_at.isoformat(),
                        )
                        for sch in scheduled
                    ],
                )

        return await self._to_thread(insert_many)

    @override
    async def delete_schedule(self, job_id: str) -> None:
        def delete() -> None:
            with self.conn as conn:
                _ = conn.execute(self.delete_schedule_query, (job_id,))

        return await self._to_thread(delete)

    @override
    async def delete_schedule_many(self, job_ids: Sequence[str]) -> None:
        if not job_ids:
            return None

        def delete_many() -> None:
            batch_size = 500
            with self.conn as conn:
                for i in range(0, len(job_ids), batch_size):
                    batch = job_ids[i : i + batch_size]
                    query = DELETE_SCHEDULE_MANY_QUERY.format_map(
                        {
                            "table_name": self.table_name,
                            "placeholder": ",".join("?" * len(batch)),
                        }
                    )
                    _ = conn.execute(query, batch)

        return await self._to_thread(delete_many)
