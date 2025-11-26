# pyright: reportPrivateUsage=false
from collections.abc import Callable

import pytest

from jobber import Jobber
from jobber._internal.routing import create_default_name


def somefunc() -> None:
    pass


async def main() -> None:
    pass


@pytest.mark.parametrize("func", [somefunc, lambda: None, main])
def test_create_default_name(func: Callable[..., None]) -> None:
    if func.__name__ == "main":
        main.__module__ = "__main__"

    job_name = create_default_name(func)
    if func.__module__ == "__main__":
        assert job_name.endswith(f"pytest:{main.__name__}")
    elif func.__name__ == "<lambda>":
        assert job_name.startswith("tests.test_func_wrapper:lambda")
    else:
        assert job_name == f"tests.test_func_wrapper:{somefunc.__name__}"


async def test_original_func_call(jobber: Jobber) -> None:
    @jobber.register
    def t1(num: int) -> int:
        return num + 1

    @jobber.register
    async def t2(num: int) -> int:
        return num + 1

    expected_val = 2
    assert t1(1) == expected_val
    assert await t2(1) == expected_val


def test_patch_job_name(jobber: Jobber) -> None:
    @jobber.register
    @jobber.register
    def t() -> None:
        pass

    t1_reg = jobber.register(t)
    t2_reg = jobber.register(t)

    new_name = "t__jobber_original"
    new_qualname = f"test_patch_job_name.<locals>.{new_name}"

    assert t._original_func.__name__ == new_name
    assert t1_reg._original_func.__name__ == new_name
    assert t2_reg._original_func.__name__ == new_name
    assert t._original_func.__qualname__ == new_qualname
    assert t1_reg._original_func.__qualname__ == new_qualname
    assert t2_reg._original_func.__qualname__ == new_qualname
    assert t1_reg is t2_reg is t
