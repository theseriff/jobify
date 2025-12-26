import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, TypeVar

from typing_extensions import override

from jobber._internal.common.constants import EMPTY
from jobber._internal.storage.abc import ScheduledJob, Storage

if TYPE_CHECKING:
    from concurrent.futures import ThreadPoolExecutor

    from jobber._internal.common.types import LoopFactory

CREATE_SCHEDULED_TABLE_QUERY = """
CREATE TABLE IF NOT EXISTS {} (
    job_id TEXT PRIMARY KEY,
    func_name TEXT,
    message BLOB,
    status TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

SELECT_SCHEDULES_QUERY = """
SELECT job_id, func_name, message, status
FROM {};
"""

INSERT_SCHEDULE_QUERY = """
INSERT INTO {} (job_id, func_name, message, status)
VALUES (?, ?, ?, ?)
ON CONFLICT (job_id) DO UPDATE SET
    func_name = EXCLUDED.func_name,
    message = EXCLUDED.message,
    status = EXCLUDED.status,
    updated_at = CURRENT_TIMESTAMP;
"""

DELETE_SCHEDULE_QUERY = """
DELETE FROM {} WHERE job_id = ?;
"""


ReturnT = TypeVar("ReturnT")


class SQLiteStorage(Storage):
    def __init__(
        self,
        *,
        db_path: str | Path = "jobber.db",
        table_name: str = "jobber_schedules",
        timeout: float = 20.0,
    ) -> None:
        self.db_path: Path = (
            Path(db_path) if isinstance(db_path, str) else db_path
        )
        self.table_name: str = table_name
        self.timeout: float = timeout
        self.getloop: LoopFactory = EMPTY
        self.threadpool: ThreadPoolExecutor | None = EMPTY
        self._conn: sqlite3.Connection | None = None

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
        loop = self.getloop()
        return await loop.run_in_executor(self.threadpool, func)

    @override
    async def startup(self) -> None:
        conn = sqlite3.connect(
            database=self.db_path,
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
                    status=row[3],
                )
                for row in cursor.fetchall()
            ]

        return await self._to_thread(get)

    @override
    async def add_schedule(self, scheduled: ScheduledJob) -> None:
        def insert() -> None:
            with self.conn as conn:
                _ = conn.execute(
                    self.insert_schedule_query,
                    (
                        scheduled.job_id,
                        scheduled.func_name,
                        scheduled.message,
                        scheduled.status,
                    ),
                )

        return await self._to_thread(insert)

    @override
    async def delete_schedule(self, job_id: str) -> None:
        def delete() -> None:
            with self.conn as conn:
                _ = conn.execute(self.delete_schedule_query, (job_id,))

        return await self._to_thread(delete)
