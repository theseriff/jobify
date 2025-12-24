from typing_extensions import override

from jobber._internal.storage.abc import ScheduledJob, Storage


class SQLiteStorage(Storage):
    @override
    async def all(self) -> list[ScheduledJob]:
        return []

    @override
    async def add(self, scheduled: ScheduledJob) -> None:
        pass

    @override
    async def delete(self, job_id: str) -> None:
        pass
