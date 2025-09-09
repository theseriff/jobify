import asyncio

from taskaio import TaskScheduler

scheduler = TaskScheduler()


@scheduler.register
def f(a: int, b: str) -> None:
    print(a, b)


@scheduler.register
async def f2(a: int, b: str) -> None:
    print("from async def f2", a, b)


f(1, "dsa")


async def main() -> None:
    s = f.schedule(2, "das")

    # f.schedule(3, "Dsa")
    # await f2(21, "vvv")
    # f2.schedule(4, "aaa").delay(1).to_thread()
    # # f2.schedule(4, "das").delay(2)
    await scheduler.wait_for_complete()


asyncio.run(main())
