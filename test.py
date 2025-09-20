import asyncio

from taskaio import TaskScheduler

scheduler = TaskScheduler()


@scheduler.register(func_id="1")
def f(a: int, b: str) -> None:
    print("from async def f: ----->", a, b)


@scheduler.register(func_id="2")
async def f2(a: int, b: str) -> None:
    print("from async def f2: ----->", a, b)


async def main() -> None:
    f(1, "main").call()
    _ = f(1, "2").to_thread().delay(2)
    _ = f2(3, "4").to_thread().delay(1)
    await f2(2, "main").call()
    await scheduler.wait_for_complete()


asyncio.run(main())
