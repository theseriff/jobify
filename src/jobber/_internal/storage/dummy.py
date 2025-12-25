from typing_extensions import override

from jobber._internal.storage.abc import ScheduledJob, Storage


class DummyStorage(Storage):
    @override
    async def startup(self) -> None:
        pass

    @override
    async def shutdown(self) -> None:
        pass

    @override
    async def get_schedules(self) -> list[ScheduledJob]:
        return []

    @override
    async def add_schedule(self, scheduled: ScheduledJob) -> None:
        pass

    @override
    async def delete_schedule(self, job_id: str) -> None:
        pass
