from collections.abc import Iterator
from datetime import datetime, timedelta
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest

from jobify import Cron, Job, Jobify, JobStatus, MisfirePolicy
from jobify._internal.message import AtArguments, CronArguments, Message
from jobify._internal.storage.abc import ScheduledJob
from jobify._internal.storage.sqlite import SQLiteStorage
from jobify.crontab import create_crontab
from jobify.serializers import ExtendedJSONSerializer
from tests.conftest import create_cron_factory

UTC = ZoneInfo("UTC")


def test_invalid_table_name() -> None:
    invalid_table_name = "1"
    msg = (
        f"Invalid table name: {invalid_table_name!r}. "
        f"Must contain only letters, digits, and underscores."
    )
    with pytest.raises(ValueError, match=msg):
        _ = SQLiteStorage(database=":memory:", table_name=invalid_table_name)


async def test_sqlite(now: datetime) -> None:
    db = Path("test.db")
    storage = SQLiteStorage(database=db, table_name="test_table")

    with pytest.raises(RuntimeError):
        _ = storage.conn
    await storage.shutdown()

    scheduled = ScheduledJob(
        "1",
        "test_name",
        b"",
        JobStatus.SUCCESS,
        next_run_at=now,
    )
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


async def test_delete_schedule_many(now: datetime) -> None:
    storage = SQLiteStorage(":memory:")
    await storage.startup()
    try:
        await storage.add_schedule(
            ScheduledJob(
                job_id="1",
                name="any_func",
                message=b"",
                status=JobStatus.SCHEDULED,
                next_run_at=now,
            ),
            ScheduledJob(
                job_id="2",
                name="any_func",
                message=b"",
                status=JobStatus.SCHEDULED,
                next_run_at=now,
            ),
        )
        expected_scheduled = 2
        assert len(await storage.get_schedules()) == expected_scheduled

        await storage.delete_schedule_many(["1", "2"])

        expected_scheduled = 0
        assert len(await storage.get_schedules()) == expected_scheduled
    finally:
        await storage.shutdown()


async def test_sqlite_with_jobify(now: datetime) -> None:
    app = Jobify(
        storage=SQLiteStorage(":memory:"),
        cron_factory=create_cron_factory(30000),
    )

    @app.task
    async def f1(name: str) -> str:
        return name

    @app.task(durable=False)
    async def f2() -> str:
        return "test"

    async with app:
        job1 = await f1.schedule("biba_delay").delay(0.05)
        job2 = await f2.schedule().delay(-1)
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
                    name=f1.name,
                    arguments={"name": "biba_delay"},
                    trigger=AtArguments(job1.exec_at, job1.id),
                ),
                Message,
            )
        )
        raw_msg2 = app.configs.serializer.dumpb(
            app.configs.dumper.dump(
                Message(
                    job_id=job1_cron.id,
                    name=f1.name,
                    arguments={"name": "biba_cron"},
                    trigger=CronArguments(cron, job1_cron.id, now),
                ),
                Message,
            )
        )
        at_scheduled = ScheduledJob(
            job_id=job1.id,
            name=f1.name,
            message=raw_msg1,
            status=JobStatus.SCHEDULED,
            next_run_at=job1.exec_at,
        )
        cron_scheduled = ScheduledJob(
            job_id=job1_cron.id,
            name=f1.name,
            message=raw_msg2,
            status=JobStatus.SCHEDULED,
            next_run_at=job1_cron.exec_at,
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

    microseconds = 30000  # 0.03 milliseconds
    cron_factory_mock = create_cron_factory(init=microseconds)
    app = Jobify(storage=storage, cron_factory=cron_factory_mock)

    f = app.task(_f, name="test_name")
    async with app:
        cron = Cron("* * * * *", max_runs=1)
        job_cron = await f.schedule("biba_cron_restore").cron(
            cron,
            job_id="test_cron",
            now=now,
        )
        exec_at = now + timedelta(seconds=0.03)
        job_at = await f.schedule("biba_at_restore").at(exec_at)

    await storage.startup()
    try:
        expected_scheduled = 2
        assert len(await storage.get_schedules()) == expected_scheduled
    finally:
        await storage.shutdown()

    app2 = Jobify(storage=storage, cron_factory=cron_factory_mock)
    _ = app2.task(_f, name="test_name")

    async with app2:
        job_at_restored: Job[str] | None = app2.find_job(job_at.id)
        job_cron_restored: Job[str] | None = app2.find_job(job_cron.id)
        expected_jobs = 2

        assert job_at_restored
        assert job_cron_restored
        assert len(app2.task._shared_state.pending_jobs) == expected_jobs
        assert job_cron_restored is app2.find_job(job_cron.id)

        await job_at_restored.wait()
        await job_cron_restored.wait()
        assert job_at_restored.result() == "biba_at_restore"
        assert job_cron_restored.result() == "biba_cron_restore"


async def test_restore_schedules_invalid_jobs(storage: SQLiteStorage) -> None:
    now = datetime.now(tz=UTC)
    serializer = ExtendedJSONSerializer()

    missing_route_job = ScheduledJob(
        job_id="job_missing_route",
        name="removed_func",
        message=serializer.dumpb(
            Message(
                job_id="job_missing_route",
                name="removed_func",
                arguments={},
                trigger=AtArguments(now, "job_missing_route"),
            )
        ),
        status=JobStatus.SCHEDULED,
        next_run_at=now,
    )
    invalid_payload_job = ScheduledJob(
        job_id="corrupted_data_001",
        name="any_func",
        message=b"invalid { json: [data",
        status=JobStatus.SCHEDULED,
        next_run_at=now,
    )
    invalid_argument_job = ScheduledJob(
        job_id="job_unexpected_arguments",
        name="test",
        message=serializer.dumpb(
            Message(
                job_id="job_unexpected_arguments",
                name="job_unexpected_arguments",
                arguments={"name": "biba_cron"},
                trigger=CronArguments(
                    Cron("* * * * *"),
                    "job_unexpected_arguments",
                    now,
                ),
            )
        ),
        status=JobStatus.SCHEDULED,
        next_run_at=now,
    )

    schedules = [missing_route_job, invalid_payload_job, invalid_argument_job]

    mock_storage = AsyncMock()
    mock_storage.get_schedules.return_value = schedules
    mock_storage.delete_schedule_many = AsyncMock()

    app = Jobify(storage=mock_storage)

    @app.task(name="job_unexpected_arguments")
    def _() -> None:
        pass

    await app._restore_schedules()
    mock_storage.delete_schedule_many.assert_awaited_once_with(
        [s.job_id for s in schedules]
    )

    app1 = Jobify(storage=storage)
    app2 = Jobify(storage=storage)

    @app1.task(name="removed_param")
    def f1(_name: str) -> None: ...

    @app2.task(name="removed_param")
    def _() -> None: ...

    async with app1:
        _job = await f1.schedule("biba").at(now + timedelta(7))

    async with app2:
        pass


async def test_restore_cron_stateful(storage: SQLiteStorage) -> None:
    microseconds = 30000  # 0.03 milliseconds
    cron_factory_mock = create_cron_factory(init=microseconds)
    app = Jobify(storage=storage, cron_factory=cron_factory_mock)

    @app.task(cron=Cron("* * * * * * *", max_runs=2))
    async def _f() -> str:
        return "test"

    async with app:
        scheduled_job1 = (await app.configs.storage.get_schedules())[0]
        job = app.task._shared_state.pending_jobs.popitem()[1]
        await job.wait()
        assert job.result() == "test"

    app2 = Jobify(storage=storage, cron_factory=cron_factory_mock)
    _ = app2.task(_f)

    async with app2:
        scheduled_job2 = (await app2.configs.storage.get_schedules())[0]
        job = app2.task._shared_state.pending_jobs.popitem()[1]
        await job.wait()
        assert job.result() == "test"

    assert scheduled_job1.next_run_at < scheduled_job2.next_run_at


async def test_declarative_cron_updated(storage: SQLiteStorage) -> None:
    now = datetime.now(tz=UTC)
    app1 = Jobify(storage=storage, cron_factory=create_crontab)
    app2 = Jobify(storage=storage, cron_factory=create_crontab)
    name = "test_declarative"

    @app1.task(
        cron=Cron(
            "1 1 1 1 1",
            max_runs=1,
            max_failures=1,
            misfire_policy=MisfirePolicy.ALL,
        ),
        name=name,
    )
    def _() -> None: ...

    cron = Cron(
        "2 2 2 2 2",
        max_runs=2,
        max_failures=2,
        misfire_policy=MisfirePolicy.GRACE(timedelta(days=7)),
    )

    @app2.task(cron=cron, name=name)
    def _() -> None: ...

    async with app1:
        pass

    async with app2:
        job_id = f"{name}__jobify_cron_definition"
        job: Job[None] | None = app2.find_job(job_id)

        routes = tuple(app2.routes)
        cron_options = routes[0].options.get("cron")

        real_cron_parser = create_crontab("2 2 2 2 2")
        next_run_at = real_cron_parser.next_run(now=now)

        scheduled_jobs = await app2.configs.storage.get_schedules()
        scheduled = scheduled_jobs[0]

        deserializer = app2.configs.serializer.loadb
        loader = app2.configs.loader.load
        trigger = cast(
            "CronArguments",
            loader(deserializer(scheduled.message), Message).trigger,
        )
        assert job
        assert job.cron_expression == "2 2 2 2 2"
        assert job.exec_at == next_run_at
        assert len(routes) == 1
        assert len(scheduled_jobs) == 1
        assert cron_options == cron
        assert scheduled == ScheduledJob(
            job_id=job_id,
            name="test_declarative",
            message=app2.configs.serializer.dumpb(
                Message(
                    job_id=job_id,
                    name="test_declarative",
                    arguments={},
                    trigger=CronArguments(cron, job_id, trigger.offset),
                )
            ),
            status=JobStatus.SCHEDULED,
            next_run_at=next_run_at,
        )


async def test_start_pending_crons_parse_error(storage: SQLiteStorage) -> None:
    name = "test_parse_error"
    job_id = f"{name}__jobify_cron_definition"
    app = Jobify(storage=storage)

    await storage.startup()
    await storage.add_schedule(
        ScheduledJob(
            job_id=job_id,
            name=name,
            message=b"invalid-json",
            status=JobStatus.SCHEDULED,
            next_run_at=datetime.now(tz=UTC),
        )
    )
    await storage.shutdown()

    @app.task(cron="* * * * *", name=name)
    def _() -> None:
        pass

    async with app:
        job: Job[None] | None = app.find_job(job_id)
        assert job is not None


async def test_start_pending_crons_non_cron_trigger(
    storage: SQLiteStorage,
) -> None:
    now = datetime.now(tz=UTC)
    name = "test_non_cron"
    job_id = f"{name}__jobify_cron_definition"
    app = Jobify(storage=storage)

    raw_msg = app.configs.serializer.dumpb(
        app.configs.dumper.dump(
            Message(
                job_id=job_id,
                name=name,
                arguments={},
                trigger=AtArguments(at=now, job_id=job_id),
            ),
            Message,
        )
    )
    await storage.startup()
    await storage.add_schedule(
        ScheduledJob(
            job_id=job_id,
            name=name,
            message=raw_msg,
            status=JobStatus.SCHEDULED,
            next_run_at=now,
        )
    )
    await storage.shutdown()

    @app.task(cron="1 1 1 1 1", name=name)
    def _() -> None:
        pass

    async with app:
        job: Job[None] | None = app.find_job(job_id)

        assert job is not None
        assert len(app.task._shared_state.pending_jobs) == 1
        assert len(await app.configs.storage.get_schedules()) == 1
