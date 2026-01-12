from collections.abc import Sequence

from typing_extensions import override

from jobify._internal.storage.abc import ScheduledJob, Storage


class DummyStorage(Storage):
    @override
    async def startup(self) -> None:
        pass

    @override
    async def shutdown(self) -> None:
        pass

    @override
    async def get_schedules(self) -> Sequence[ScheduledJob]:
        return []

    @override
    async def add_schedule(self, *scheduled: ScheduledJob) -> None:
        pass

    @override
    async def delete_schedule(self, job_id: str) -> None:
        pass

    @override
    async def delete_schedule_many(self, job_ids: Sequence[str]) -> None:
        pass
