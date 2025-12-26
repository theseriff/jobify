from collections.abc import Callable

import pytest

from jobber._internal.router.base import resolve_name
from jobber.exceptions import RouteAlreadyRegisteredError
from tests.conftest import create_app


def somefunc() -> None:
    pass


async def main() -> None:
    pass


@pytest.mark.parametrize("func", [somefunc, lambda: None, main])
def test_create_default_name(func: Callable[..., None]) -> None:
    if func.__name__ == "main":
        main.__module__ = "__main__"

    name = func.__name__
    module = func.__module__

    job_name = resolve_name(func)
    if func.__module__ == "__main__":
        assert job_name.endswith(f"pytest:{name}")
    elif func.__name__ == "<lambda>":
        assert job_name.startswith(f"{module}:lambda")
    else:
        assert job_name == f"{module}:{name}"


async def test_original_func_call() -> None:
    jobber = create_app()

    @jobber.task
    def t1(num: int) -> int:
        return num + 1

    @jobber.task
    async def t2(num: int) -> int:
        return num + 1

    expected_val = 2
    assert t1(1) == expected_val
    assert await t2(1) == expected_val


def test_patch_job_name() -> None:
    jobber = create_app()

    @jobber.task
    def t() -> None:
        pass

    match = f"A route with the name {t.name!r} has already been registered."
    with pytest.raises(RouteAlreadyRegisteredError, match=match):
        _ = jobber.task(t)

    t1_reg = jobber.task(t, func_name="test1")
    t2_reg = jobber.task(t, func_name="test2")

    new_name = "t__jobber_original"
    new_qualname = f"test_patch_job_name.<locals>.{new_name}"

    assert t.func.__name__ == new_name
    assert t.func.__name__ == new_name
    assert t1_reg.func.__name__ == new_name
    assert t2_reg.func.__name__ == new_name
    assert t.func.__qualname__ == new_qualname
    assert t1_reg.func.__qualname__ == new_qualname
    assert t2_reg.func.__qualname__ == new_qualname

    assert t1_reg is not t
    assert t2_reg is not t
    assert t1_reg is not t2_reg
