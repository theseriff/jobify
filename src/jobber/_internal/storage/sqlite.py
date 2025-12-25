import functools
import sqlite3
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import ParamSpec, TypeVar

from typing_extensions import override

from jobber._internal.common.types import LoopFactory
from jobber._internal.storage.abc import ScheduledJob, Storage

CREATE_SCHEDULED_TABLE_QUERY = """
CREATE TABLE IF NOT EXISTS {} (
    job_id TEXT PRIMARY KEY,
    route_name TEXT,
    message BLOB,
    status TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

SELECT_SCHEDULES_QUERY = """
SELECT job_id, route_name, message, status
FROM {};
"""

INSERT_SCHEDULE_QUERY = """
INSERT INTO {} (job_id, route_name, message, status)
VALUES (?, ?, ?, ?)
ON CONFLICT (job_id) DO UPDATE SET
    route_name = EXCLUDED.route_name,
    message = EXCLUDED.message,
    status = EXCLUDED.status,
    updated_at = CURRENT_TIMESTAMP;
"""

DELETE_SCHEDULE_QUERY = """
DELETE FROM {} WHERE job_id = ?;
"""


ReturnT = TypeVar("ReturnT")
ParamsT = ParamSpec("ParamsT")


class SQLiteStorage(Storage):
    def __init__(
        self,
        *,
        db_name: str = "jobber.db",
        table_name: str = "jobber_schedules",
        timeout: float = 20.0,
        getloop: LoopFactory,
        threadpool: ThreadPoolExecutor | None,
    ) -> None:
        self.db_name: str = db_name
        self.table_name: str = table_name
        self.timeout: float = timeout
        self.getloop: LoopFactory = getloop
        self.threadpool: ThreadPoolExecutor | None = threadpool

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

    async def _to_thread(
        self,
        func: Callable[ParamsT, ReturnT],
        *args: ParamsT.args,
        **kwargs: ParamsT.kwargs,
    ) -> ReturnT:
        loop = self.getloop()
        func_call = functools.partial(func, *args, **kwargs)
        return await loop.run_in_executor(self.threadpool, func_call)

    @override
    async def startup(self) -> None:
        with sqlite3.connect(self.db_name) as conn:
            _ = conn.execute("PRAGMA journal_mode=WAL;")
            _ = conn.execute("PRAGMA synchronous=NORMAL;")
            _ = conn.execute(self.create_scheduled_table_query)
            conn.commit()

    @override
    async def shutdown(self) -> None:
        pass

    @override
    async def get_schedules(self) -> list[ScheduledJob]:
        def stmt() -> list[ScheduledJob]:
            with sqlite3.connect(self.db_name, timeout=self.timeout) as conn:
                cursor = conn.execute(self.select_schedules_query)
                return [ScheduledJob(*row) for row in cursor.fetchall()]

        return await self._to_thread(stmt)

    @override
    async def add_schedule(self, scheduled: ScheduledJob) -> None:
        def stmt() -> None:
            with sqlite3.connect(self.db_name, timeout=self.timeout) as conn:
                _ = conn.execute(self.insert_schedule_query, scheduled)
                conn.commit()

        return await self._to_thread(stmt)

    @override
    async def delete_schedule(self, job_id: str) -> None:
        def stmt() -> None:
            with sqlite3.connect(self.db_name, timeout=self.timeout) as conn:
                _ = conn.execute(self.delete_schedule_query, (job_id,))
                conn.commit()

        return await self._to_thread(stmt)
