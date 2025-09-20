import asyncio

from taskaio import TaskScheduler

scheduler = TaskScheduler()


@scheduler.register(func_id="1")
def f(a: int, b: str) -> None:
    print("from async def f\n", a, b)


@scheduler.register(func_id="2")
async def f2(a: int, b: str) -> None:
    print("from async def f2\n", a, b)


async def main() -> None:
    f(1, "0")
    _ = f(1, "2").delay(2)
    _ = f2(3, "4").delay(1)
    f(1, "2").call()
    f2(2, "0")
    await scheduler.wait_for_complete()


asyncio.run(main())
