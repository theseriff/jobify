import asyncio
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, call

import pytest

from jobify import Cron, Job, Jobify, JobStatus
from jobify._internal.message import Message
from jobify._internal.storage.abc import ScheduledJob
from jobify._internal.storage.sqlite import SQLiteStorage
from jobify.serializers import ExtendedJSONSerializer
from tests.conftest import create_cron_factory


async def test_sqlite() -> None:
    db = Path("test.db")
    storage = SQLiteStorage(database=db, table_name="test_table")
    storage.threadpool = None
    storage.getloop = asyncio.get_running_loop

    with pytest.raises(RuntimeError):
        _ = storage.conn
    await storage.shutdown()

    scheduled = ScheduledJob("1", "test_name", b"", JobStatus.SUCCESS)
    await storage.startup()
    try:
        await storage.add_schedule(scheduled)
        schedules = await storage.get_schedules()
        assert schedules[0] == scheduled

        await storage.delete_schedule(scheduled.job_id)
        assert await storage.get_schedules() == []
        assert storage.database.exists()
    finally:
        await storage.shutdown()
        db.unlink()


async def test_sqlite_with_jobify(now: datetime) -> None:
    app = Jobify(
        storage=SQLiteStorage(":memory:"),
        cron_factory=create_cron_factory(),
    )

    @app.task
    async def f1(name: str) -> str:
        return name

    @app.task(durable=False)
    async def f2() -> str:
        return "test"

    async with app:
        job1 = await f1.schedule("biba_delay").delay(0.05, now=now)
        job2 = await f2.schedule().delay(0, now=now)
        cron = Cron("* * * * *", max_runs=1)
        job1_cron = await f1.schedule("biba_cron").cron(
            cron,
            now=now,
            job_id="test",
        )

        raw_msg1 = app.configs.serializer.dumpb(
            app.configs.dumper.dump(
                Message(
                    job_id=job1.id,
                    func_name=f1.name,
                    arguments={"name": "biba_delay"},
                    trigger={
                        "at": job1.exec_at,
                        "job_id": job1.id,
                        "now": now,
                    },
                ),
                Message,
            )
        )
        raw_msg2 = app.configs.serializer.dumpb(
            app.configs.dumper.dump(
                Message(
                    job_id=job1_cron.id,
                    func_name=f1.name,
                    arguments={"name": "biba_cron"},
                    trigger={"cron": cron, "job_id": job1_cron.id, "now": now},
                ),
                Message,
            )
        )
        at_scheduled = ScheduledJob(
            job_id=job1.id,
            func_name=f1.name,
            message=raw_msg1,
            status=JobStatus.SCHEDULED,
        )
        cron_scheduled = ScheduledJob(
            job_id=job1_cron.id,
            func_name=f1.name,
            message=raw_msg2,
            status=JobStatus.SCHEDULED,
        )
        assert await app.configs.storage.get_schedules() == [
            at_scheduled,
            cron_scheduled,
        ]
        await job1.wait()
        await job1_cron.wait()
        await job2.wait()

        assert job1.result() == "biba_delay"
        assert job1_cron.result() == "biba_cron"
        assert job2.result() == "test"
        assert await app.configs.storage.get_schedules() == [cron_scheduled]


@pytest.fixture
def storage() -> Iterator[SQLiteStorage]:
    s = SQLiteStorage("test_restore.db")
    yield s
    s.database.unlink()


async def test_restore_schedules(
    storage: SQLiteStorage,
    now: datetime,
) -> None:
    async def _f(name: str) -> str:
        return name

    app = Jobify(storage=storage)

    f = app.task(_f, func_name="test_name")
    async with app:
        cron = Cron("* * * * *", max_runs=1)
        job_cron = await f.schedule("biba_cron_restore").cron(
            cron,
            job_id="test_cron",
            now=now,
        )
        job_at = await f.schedule("biba_at_restore").delay(0.03, now=now)

    await storage.startup()
    try:
        total_scheduled = 2
        assert len(await storage.get_schedules()) == total_scheduled
    finally:
        await storage.shutdown()

    microseconds = 30000  # 0.03 milliseconds
    cron_factory_mock = create_cron_factory(init=microseconds)

    app2 = Jobify(storage=storage, cron_factory=cron_factory_mock)
    _ = app2.task(_f, func_name="test_name")

    async with app2:
        job_at_restored: Job[str] | None = app2.find_job(job_at.id)
        job_cron_restored: Job[str] | None = app2.find_job(job_cron.id)
        assert job_at_restored
        assert job_cron_restored

        await app2.task.start_pending_crons()
        await app2._restore_schedules()

        expected_jobs = 2
        assert len(app2.task._shared_state.pending_jobs) == expected_jobs
        assert job_cron_restored is app2.find_job(job_cron.id)

        await job_at_restored.wait()
        await job_cron_restored.wait()

        assert job_at_restored.result() == "biba_at_restore"
        assert job_cron_restored.result() == "biba_cron_restore"


async def test_restore_schedules_invalid_jobs() -> None:
    serializer = ExtendedJSONSerializer()

    now = datetime.now(tz=timezone.utc)
    missing_route_job = ScheduledJob(
        job_id="job_missing_route",
        func_name="removed_func",
        message=serializer.dumpb(
            Message(
                job_id="job_missing_route",
                func_name="removed_func",
                arguments={},
                trigger={"at": now, "job_id": "job_missing_route", "now": now},
            )
        ),
        status=JobStatus.SCHEDULED,
    )
    invalid_payload_job = ScheduledJob(
        job_id="corrupted_data_001",
        func_name="any_func",
        message=b"invalid { json: [data",
        status=JobStatus.SCHEDULED,
    )
    invalid_argument_job = ScheduledJob(
        job_id="job_unexpected_arguments",
        func_name="test",
        message=serializer.dumpb(
            Message(
                job_id="job_unexpected_arguments",
                func_name="job_unexpected_arguments",
                arguments={"name": "biba_cron"},
                trigger={
                    "cron": Cron("* * * * *"),
                    "job_id": "job_unexpected_arguments",
                    "now": datetime.now(tz=timezone.utc),
                },
            )
        ),
        status=JobStatus.SCHEDULED,
    )
    mock_storage = AsyncMock()
    mock_storage.get_schedules.return_value = [
        missing_route_job,
        invalid_payload_job,
        invalid_argument_job,
    ]
    mock_storage.delete_schedule = AsyncMock()

    app = Jobify(storage=mock_storage)

    @app.task(func_name="job_unexpected_arguments")
    def _() -> None:
        pass

    await app._restore_schedules()
    mock_storage.delete_schedule.assert_has_awaits(
        [
            call("job_missing_route"),
            call("corrupted_data_001"),
            call("job_unexpected_arguments"),
        ],
    )


async def test_restore_cron_stateful(storage: SQLiteStorage) -> None:
    microseconds = 30000  # 0.03 milliseconds
    cron_factory_mock = create_cron_factory(init=microseconds)
    app = Jobify(storage=storage, cron_factory=cron_factory_mock)

    @app.task(cron=Cron("* * * * * * *", max_runs=2))
    async def _f() -> str:
        return "test"

    async with app:
        scheduled_job1 = list(await app.configs.storage.get_schedules()).pop()
        job = app.task._shared_state.pending_jobs.popitem()[1]
        await job.wait()
        assert job.result() == "test"

    app2 = Jobify(storage=storage, cron_factory=cron_factory_mock)
    _ = app2.task(_f)

    async with app2:
        scheduled_job2 = list(await app2.configs.storage.get_schedules()).pop()
        job = app2.task._shared_state.pending_jobs.popitem()[1]
        await job.wait()
        assert job.result() == "test"

    now_old: datetime = app.configs.serializer.loadb(
        scheduled_job1.message,
    ).trigger["now"]
    now_new: datetime = app2.configs.serializer.loadb(
        scheduled_job2.message,
    ).trigger["now"]

    assert now_old < now_new
