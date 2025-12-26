import asyncio
from collections.abc import AsyncIterator, Iterator
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest

from jobber import Cron, Jobber, JobStatus
from jobber._internal.message import Message
from jobber._internal.storage.abc import ScheduledJob
from jobber._internal.storage.sqlite import SQLiteStorage
from tests.conftest import create_cron_factory


@pytest.fixture
def sqlite() -> Iterator[SQLiteStorage]:
    db_path = Path(f"{uuid4().hex}.db")
    yield SQLiteStorage(db_path=db_path, table_name="test_table")
    db_path.unlink()


@pytest.fixture
async def sqlite_life(sqlite: SQLiteStorage) -> AsyncIterator[SQLiteStorage]:
    sqlite.threadpool = None
    sqlite.getloop = lambda: asyncio.get_running_loop()
    await sqlite.startup()

    yield sqlite

    await sqlite.shutdown()


async def test_sqlite_lifespan() -> None:
    storage = SQLiteStorage(db_path=":memory:", table_name="test_table")
    with pytest.raises(RuntimeError):
        _ = storage.conn

    assert storage._conn is None
    await storage.shutdown()


async def test_sqlite(sqlite_life: SQLiteStorage) -> None:
    scheduled = ScheduledJob("1", "test_name", b"", JobStatus.SUCCESS)

    await sqlite_life.add_schedule(scheduled)
    schedules = await sqlite_life.get_schedules()
    assert schedules[0] == scheduled

    await sqlite_life.delete_schedule(scheduled.job_id)
    assert await sqlite_life.get_schedules() == []

    assert sqlite_life.db_path.exists()


async def test_sqlite_with_jobber(
    sqlite: SQLiteStorage,
    now: datetime,
) -> None:
    app = Jobber(storage=sqlite, cron_factory=create_cron_factory())

    @app.task
    async def f1() -> str:
        return "test"

    @app.task(durable=False)
    async def f2() -> str:
        return "test"

    async with app:
        job1 = await f1.schedule().delay(0.05, now=now)
        job2 = await f2.schedule().delay(0, now=now)

        cron = Cron("* * * * *", max_runs=1)
        job1_cron = await f1.schedule().cron(cron, now=now, job_id="test")

        raw_msg1 = app.configs.serializer.dumpb(
            app.configs.dumper.dump(
                Message(
                    job_id=job1.id,
                    func_name=f1.name,
                    arguments={},
                    at={"at": job1.exec_at, "job_id": job1.id, "now": now},
                ),
                Message,
            )
        )
        raw_msg2 = app.configs.serializer.dumpb(
            app.configs.dumper.dump(
                Message(
                    job_id=job1_cron.id,
                    func_name=f1.name,
                    arguments={},
                    cron={"cron": cron, "job_id": job1_cron.id, "now": now},
                ),
                Message,
            )
        )
        assert await app.configs.storage.get_schedules() == [
            ScheduledJob(
                job_id=job1.id,
                func_name=f1.name,
                message=raw_msg1,
                status=JobStatus.SCHEDULED,
            ),
            ScheduledJob(
                job_id=job1_cron.id,
                func_name=f1.name,
                message=raw_msg2,
                status=JobStatus.SCHEDULED,
            ),
        ]
        await job1.wait()
        await job2.wait()
        assert job1.result() == "test"
        assert job2.result() == "test"
        assert await app.configs.storage.get_schedules() == [
            ScheduledJob(
                job_id=job1_cron.id,
                func_name=f1.name,
                message=raw_msg2,
                status=JobStatus.SCHEDULED,
            )
        ]
