from iojobs._internal.durable.abc import JobRepository, PersistedJob


class SQLiteJobRepository(JobRepository):
    def load_all(self, persisted_job: PersistedJob) -> None:
        _ = persisted_job
