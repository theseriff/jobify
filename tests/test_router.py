import pytest

from jobber import JobRouter
from jobber._internal.router.base import resolve_name
from tests.conftest import create_app


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

    app = create_app()
    app.include_router(router1)

    assert repr(router1) == "<NodeRouter>"
    assert router5.prefix == "1.2.3.4"

    for router, prefix in zip(sub4_routers, "abcd", strict=True):
        assert router.prefix == f"1.2.3.4.{prefix}"


def test_nested_name() -> None:
    router1 = JobRouter(prefix="level1")
    router2 = JobRouter(prefix="level2")
    router3 = JobRouter()

    async def t() -> None:
        pass

    f = router1.task(t, func_name="test1")
    f2 = router2.task(t, func_name="test2")
    f3 = router2.task(t)
    f4 = router3.task(t, func_name="test4")

    router1.include_router(router2)

    app = create_app()
    app.include_router(router1)
    app.include_router(router3)

    assert f.name == "level1:test1"
    assert f2.name == "level1.level2:test2"
    assert f3.name == f"level1.level2:{resolve_name(f3)}"
    assert f4.name == "test4"


async def test_router_include() -> None:
    router1 = JobRouter(prefix="level1")

    @router1.task(func_name="test1")
    async def f() -> str:
        return "test"

    match = (
        f"Job {f.name!r} is not attached to any Jobber app."
        " Did you forget to call app.include_router()?"
    )
    with pytest.raises(RuntimeError, match=match):
        _ = f.schedule()

    app = create_app()
    app.include_router(router1)

    async with app:
        job = await f.schedule().delay(0)
        await job.wait()

    assert job.result() == "test"


def test_router_wrong_usage() -> None:
    router = JobRouter()
    app = create_app()
    app.include_router(router)

    with pytest.raises(
        RuntimeError,
        match=f"Router is already attached to {app!r}",
    ):
        app.include_router(router)

    with pytest.raises(
        RuntimeError,
        match="Self-referencing routers is not allowed",
    ):
        app.include_router(app)

    with pytest.raises(
        RuntimeError,
        match="Circular referencing of Router is not allowed",
    ):
        router.include_router(app)

    with pytest.raises(
        ValueError,
        match="At least one router must be provided",
    ):
        app.include_routers()
