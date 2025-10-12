import multiprocessing
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

from iojobs._internal._types import EMPTY


class ExecutorPool:  # pragma: no cover
    __slots__: tuple[str, ...] = ("_processpool", "_threadpool")

    def __init__(self) -> None:
        self._processpool: ProcessPoolExecutor = EMPTY
        self._threadpool: ThreadPoolExecutor = EMPTY

    @property
    def processpool_executor(self) -> ProcessPoolExecutor:
        if self._processpool is EMPTY:
            mp_ctx = multiprocessing.get_context("spawn")
            self._processpool = ProcessPoolExecutor(mp_context=mp_ctx)
        return self._processpool

    @property
    def threadpool_executor(self) -> ThreadPoolExecutor:
        if self._threadpool is EMPTY:
            self._threadpool = ThreadPoolExecutor()
        return self._threadpool

    def shutdown(self) -> None:
        if self._processpool is not EMPTY:
            self._processpool.shutdown(wait=True, cancel_futures=True)
        if self._threadpool is not EMPTY:
            self._threadpool.shutdown(wait=True, cancel_futures=True)
