import asyncio
import random
import time
from concurrent.futures.process import ProcessPoolExecutor

from taskaio import TaskScheduler

scheduler = TaskScheduler()


def blocking_task() -> int:
    time.sleep(1)
    return random.randrange(10)


def on_complete(future: asyncio.Future[int]) -> None:
    print(future.result(), "get result")


async def main() -> None:
    loop = asyncio.get_running_loop()
    with ProcessPoolExecutor() as pool:
        future1 = loop.run_in_executor(pool, blocking_task)
        future2 = loop.run_in_executor(pool, blocking_task)
        future3 = loop.run_in_executor(pool, blocking_task)
        future1.add_done_callback(on_complete)
        future2.add_done_callback(on_complete)
        future3.add_done_callback(on_complete)

        start = time.perf_counter()
        _ = await asyncio.gather(future1, future2, future3)
        print(f"ended for {time.perf_counter() - start}")


asyncio.run(main())
