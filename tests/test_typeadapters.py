from datetime import datetime, timezone
from typing import NamedTuple
from unittest.mock import Mock
from uuid import UUID

import pytest
from adaptix import Retort
from uuid_utils.compat import uuid7

from jobify import Jobify, JobStatus
from jobify._internal.message import Message, PushArguments
from jobify._internal.storage.base import ScheduledJob
from jobify.storage import SQLiteStorage
from jobify.typeadapter import Dumper, Loader, PydanticConverter

UTC = timezone.utc


class PairAdapter(Dumper, Loader): ...


TYPE_ADAPTERS = (
    pytest.param(PydanticConverter(), id="pydantic"),
    pytest.param(Retort(), id="adaptix"),
)


class CreateUser(NamedTuple):
    id: UUID
    name: str
    created_at: datetime


@pytest.mark.parametrize("adapter", TYPE_ADAPTERS)
async def test_adapter_dump(adapter: PairAdapter) -> None:
    def create_user(d: CreateUser) -> CreateUser:
        return d

    app = Jobify(
        storage=SQLiteStorage(":memory:"),
        dumper=adapter,
        loader=adapter,
    )
    task = app.task(create_user)
    data = CreateUser(uuid7(), "Kava", datetime.now(UTC))
    async with app:
        job1 = await task.schedule(data).delay(0)
        job2 = await task.push(data)
        await app.wait_all()

    assert data == job1.result() == job2.result()


@pytest.mark.parametrize("adapter", TYPE_ADAPTERS)
async def test_adapter_load(adapter: PairAdapter, storage: SQLiteStorage) -> None:
    mock = Mock()
    app = Jobify(
        storage=storage,
        dumper=adapter,
        loader=adapter,
    )

    @app.task(name="test task")
    def create_user(d: CreateUser) -> CreateUser:
        mock(d)
        return d

    data = CreateUser(uuid7(), "Kava", datetime.now(UTC))

    await app.configs.storage.startup()
    await app.configs.storage.add_schedule(_dump_data(app, data))
    await app.configs.storage.shutdown()

    async with app:
        await app.wait_all()

    mock.assert_called_once_with(data)


def _dump_data(app: Jobify, data: CreateUser) -> ScheduledJob:
    id_ = data.id.hex

    message: bytes = app.configs.serializer.dumpb(
        app.configs.dumper.dump(
            Message(
                job_id=id_,
                name="test task",
                arguments={"d": app.configs.dumper.dump(data, CreateUser)},
                trigger=PushArguments(job_id=id_),
            ),
            Message,
        )
    )
    return ScheduledJob(
        job_id=id_,
        name="test task",
        message=message,
        status=JobStatus.SCHEDULED,
        next_run_at=datetime.now(tz=UTC),
    )
