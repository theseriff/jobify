import asyncio
import sqlite3
from collections.abc import Callable, Sequence
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeAlias, TypeVar
from zoneinfo import ZoneInfo

from typing_extensions import override

from jobify._internal.common.constants import EMPTY, JobStatus
from jobify._internal.storage.base import (
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
    name TEXT,
    message BLOB,
    status TEXT,
    next_run_at TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

SELECT_SCHEDULES_QUERY = """
SELECT job_id, name, message, status, next_run_at
FROM {};
"""

INSERT_SCHEDULE_QUERY = """
INSERT INTO {} (job_id, name, message, status, next_run_at)
VALUES (?, ?, ?, ?, ?)
ON CONFLICT (job_id) DO UPDATE SET
    name = EXCLUDED.name,
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

_Callback = Callable[[], ReturnT]
_AsyncQueue: TypeAlias = asyncio.Queue[
    tuple[_Callback[Any], asyncio.Future[Any]],
]
_STOP: Any = object()


class SQLiteStorage(Storage):
    def __init__(
        self,
        database: str | Path = "jobify.db",
        *,
        table_name: str = "jobify_schedules",
        timeout: float = 20.0,
        max_queue_size: int = 1024,
    ) -> None:
        validate_table_name(table_name)
        self.database: Path = (
            Path(database) if isinstance(database, str) else database
        )
        self.table_name: str = table_name
        self.timeout: float = timeout
        self.tz: ZoneInfo = ZoneInfo("UTC")
        self.getloop: LoopFactory = asyncio.get_running_loop
        self.max_queue_size: int = max_queue_size
        self.threadpool: ThreadPoolExecutor | None = None

        self._conn: sqlite3.Connection = EMPTY
        self._loop: asyncio.AbstractEventLoop = EMPTY
        self._queue: _AsyncQueue = EMPTY
        self._worker_task: asyncio.Task[None] = EMPTY

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
        self._loop = self.getloop()
        self._queue = asyncio.Queue(self.max_queue_size)
        self._worker_task = asyncio.create_task(self._worker())

    @override
    async def shutdown(self) -> None:
        if self._queue is not EMPTY:
            await self._queue.put(_STOP)
            await self._queue.join()
            self._queue = EMPTY

        if self._worker_task is not EMPTY:
            await self._worker_task
            self._worker_task = EMPTY

        if self._conn is not EMPTY:
            self._conn.close()
            self._conn = EMPTY

        self._loop = EMPTY

    async def _execute(self, callback: _Callback[ReturnT]) -> ReturnT:
        loop = self.getloop()
        future: asyncio.Future[ReturnT] = loop.create_future()
        await self._queue.put((callback, future))
        return await future

    @override
    async def get_schedules(self) -> list[ScheduledJob]:
        def get() -> list[ScheduledJob]:
            cursor = self._conn.execute(self.select_schedules_query)
            return [
                ScheduledJob(
                    job_id=row[0],
                    name=row[1],
                    message=row[2],
                    status=JobStatus(row[3]),
                    next_run_at=(
                        datetime.fromisoformat(row[4]).astimezone(self.tz)
                    ),
                )
                for row in cursor.fetchall()
            ]

        return await self._execute(get)

    @override
    async def add_schedule(self, *scheduled: ScheduledJob) -> None:
        def insert_many() -> None:
            _ = self._conn.executemany(
                self.insert_schedule_query,
                [
                    (
                        sch.job_id,
                        sch.name,
                        sch.message,
                        sch.status,
                        sch.next_run_at.isoformat(),
                    )
                    for sch in scheduled
                ],
            )
            self._conn.commit()

        return await self._execute(insert_many)

    @override
    async def delete_schedule(self, job_id: str) -> None:
        def delete() -> None:
            _ = self._conn.execute(self.delete_schedule_query, (job_id,))
            self._conn.commit()

        return await self._execute(delete)

    @override
    async def delete_schedule_many(self, job_ids: Sequence[str]) -> None:
        if not job_ids:
            return None

        job_ids = sorted(job_ids)

        def delete_many() -> None:
            batch_size = 500
            for i in range(0, len(job_ids), batch_size):
                batch = job_ids[i : i + batch_size]
                query = DELETE_SCHEDULE_MANY_QUERY.format_map(
                    {
                        "table_name": self.table_name,
                        "placeholder": ",".join("?" * len(batch)),
                    }
                )
                _ = self._conn.execute(query, batch)
            self._conn.commit()

        return await self._execute(delete_many)

    async def _worker(self) -> None:
        while True:
            item = await self._queue.get()

            if item is _STOP:
                self._queue.task_done()
                break

            callback, future = item
            try:
                result = await self._loop.run_in_executor(
                    self.threadpool,
                    callback,
                )
            except Exception as exc:  # noqa: BLE001
                future.set_exception(exc)
            else:
                future.set_result(result)
            finally:
                self._queue.task_done()
