import asyncio
from datetime import datetime
import itertools
from typing import Literal

from taskaio import TaskScheduler

scheduler = TaskScheduler()


@scheduler.register(func_id="1")
def f(a: int, b: str) -> None:
    print("from async def f: ----->", a, b)


@scheduler.register(func_id="2")
async def f2(a: int, b: str, c) -> None:
    print("-" * 30)
    print("now:", datetime.now())
    print("tasks:", len(c))
    print("from async def f2: ----->", a, b)
    print("-" * 30)


@scheduler.register(func_id="2")
async def f3(a: int, b: str, c) -> Literal[5]:
    print("-" * 30)
    print("now:", datetime.now())
    print("tasks:", len(c))
    print("from async def f3: ----->", a, b)
    print("-" * 30)
    return 5


async def main() -> None:
    # f(1, "main").call()
    # _ = f(1, "2").to_thread().delay(2)
    # _ = f2(3, "4", scheduler._wrapper.task_registered).to_thread().delay(1)
    # await f2(2, "main", scheduler._wrapper.task_registered).call()

    _ = f2(2, "cron2", scheduler._wrapper.task_registered).cron("*/2 * * * *")
    _ = f3(1, "cron3", scheduler._wrapper.task_registered).cron("* * * * *")

    cnt = itertools.count()
    await scheduler.wait_for_complete()


asyncio.run(main())
