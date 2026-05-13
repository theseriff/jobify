from datetime import datetime, timezone
from typing import NamedTuple
from unittest.mock import Mock, call
from uuid import UUID, uuid4

import pytest
from adaptix import Retort

from jobify import Jobify
from jobify._internal.message import AtArguments, PushArguments
from jobify.storage import SQLiteStorage
from jobify.typeadapter import Dumper, Loader, PydanticConverter

UTC = timezone.utc


class PairAdapter(Dumper, Loader): ...


TYPE_ADAPTERS = (
    pytest.param(Retort(), id="adaptix"),
    pytest.param(PydanticConverter(), id="pydantic"),
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
    data = CreateUser(uuid4(), "Kava", datetime.now(UTC))
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

    now = datetime.now(UTC)
    data = CreateUser(uuid4(), "Kava", now)

    job1_id1 = uuid4().hex
    job1_id2 = uuid4().hex

    await app.startup()

    await create_user.schedule(data)._persist_job(
        job1_id1,
        now,
        PushArguments(job1_id1),
    )
    await create_user.schedule(data)._persist_job(
        job1_id2,
        now,
        AtArguments(job1_id2, at=now),
    )
    await app.shutdown()

    async with app:
        await app.wait_all()

    mock.assert_has_calls([call(data), call(data)])
