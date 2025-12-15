from collections.abc import Callable

import pytest

from jobber import Jobber
from jobber._internal.router.base import resolve_name


def somefunc() -> None:
    pass


async def main() -> None:
    pass


@pytest.mark.parametrize("func", [somefunc, lambda: None, main])
def test_create_default_name(func: Callable[..., None]) -> None:
    if func.__name__ == "main":
        main.__module__ = "__main__"

    job_name = resolve_name(func)
    if func.__module__ == "__main__":
        assert job_name.endswith(f"pytest:{main.__name__}")
    elif func.__name__ == "<lambda>":
        assert job_name.startswith("tests.test_func_wrapper:lambda")
    else:
        assert job_name == f"tests.test_func_wrapper:{somefunc.__name__}"


async def test_original_func_call() -> None:
    jobber = Jobber()

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
    jobber = Jobber()

    @jobber.task
    @jobber.task
    def t() -> None:
        pass

    t1_reg = jobber.task(t)
    t2_reg = jobber.task(t)

    new_name = "t__jobber_original"
    new_qualname = f"test_patch_job_name.<locals>.{new_name}"

    assert t.func.__name__ == new_name
    assert t1_reg.func.__name__ == new_name
    assert t2_reg.func.__name__ == new_name
    assert t.func.__qualname__ == new_qualname
    assert t1_reg.func.__qualname__ == new_qualname
    assert t2_reg.func.__qualname__ == new_qualname
    assert t1_reg is t2_reg is t
