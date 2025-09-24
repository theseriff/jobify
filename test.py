import asyncio
from datetime import datetime

from taskaio import TaskScheduler

scheduler = TaskScheduler()


@scheduler.register(func_id="1")
def f(a: int, b: str) -> None:
    print("from async def f: ----->", a, b)


@scheduler.register(func_id="2")
async def f2(a: int, b: str, c) -> None:
    print("now:", datetime.now())
    print("tasks:", len(c))
    print("from async def f2: ----->", a, b)


async def main() -> None:
    # f(1, "main").call()
    # _ = f(1, "2").to_thread().delay(2)
    # _ = f2(3, "4", scheduler._wrapper.task_registered).to_thread().delay(1)
    # await f2(2, "main", scheduler._wrapper.task_registered).call()

    _ = f2(1, "cron", scheduler._wrapper.task_registered).cron("* * * * *")

    async for task_info in scheduler.wait_for_complete():
        print(task_info)
        task_info.cancel()


asyncio.run(main())
