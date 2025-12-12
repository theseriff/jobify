import pytest

from jobber import Jobber, JobRouter
from jobber._internal.routers.base import resolve_fname


def test_nested_prefix() -> None:
    router1 = JobRouter(prefix="1")
    router2 = JobRouter(prefix="2")
    router3 = JobRouter(prefix="3")
    router4 = JobRouter(prefix="4")
    router5 = JobRouter()

    sub4_routers = [JobRouter(prefix=char) for char in "abcd"]
    router4.include_routers(*sub4_routers)
    router4.include_router(router5)

    router1.include_router(router2)
    router2.include_router(router3)
    router3.include_router(router4)

    app = Jobber()
    app.include_router(router1)

    assert router5.prefix == "1.2.3.4"

    for router, prefix in zip(sub4_routers, "abcd", strict=True):
        assert router.prefix == f"1.2.3.4.{prefix}"


def test_nested_fname() -> None:
    router1 = JobRouter(prefix="level1")
    router2 = JobRouter(prefix="level2")

    @router1.task(func_name="test1")
    async def f() -> None:
        pass

    @router2.task(func_name="test2")
    async def f2() -> None:
        pass

    @router2.task
    async def f3() -> None:
        pass

    router1.include_router(router2)

    app = Jobber()
    app.include_router(router1)

    assert f.fname == "level1:test1"
    assert f2.fname == "level1.level2:test2"
    assert f3.fname == f"level1.level2:{resolve_fname(f3)}"


def test_router_not_included() -> None:
    router1 = JobRouter(prefix="level1")

    @router1.task(func_name="test1")
    async def f() -> None:
        pass

    match = (
        f"Job {f.fname!r} is not attached to any Jobber app."
        " Did you forget to call app.include_router()?"
    )
    with pytest.raises(RuntimeError, match=match):
        _ = f.schedule()


async def test_router_included() -> None:
    router1 = JobRouter(prefix="level1")

    @router1.task(func_name="test1")
    async def f() -> str:
        return "test"

    app = Jobber()
    app.include_router(router1)

    async with app:
        job = await f.schedule().delay(0)
        await job.wait()

    assert job.result() == "test"
