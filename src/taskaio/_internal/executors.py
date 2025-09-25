import concurrent.futures

from taskaio._internal._types import EMPTY


class ExecutorPool:
    def __init__(self) -> None:
        self._processpool: concurrent.futures.ProcessPoolExecutor = EMPTY
        self._threadpool: concurrent.futures.ThreadPoolExecutor = EMPTY

    @property
    def processpool_executor(self) -> concurrent.futures.ProcessPoolExecutor:
        if self._processpool is EMPTY:
            self._processpool = concurrent.futures.ProcessPoolExecutor()
        return self._processpool

    @property
    def threadpool_executor(self) -> concurrent.futures.ThreadPoolExecutor:
        if self._threadpool is EMPTY:
            self._threadpool = concurrent.futures.ThreadPoolExecutor()
        return self._threadpool

    def shutdown(self) -> None:
        if self._processpool is not EMPTY:
            self._processpool.shutdown()
        if self._threadpool is not EMPTY:
            self._threadpool.shutdown()
