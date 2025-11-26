from jobber._internal.storage.abc import JobRepository, JobStored


class SQLiteJobRepository(JobRepository):
    def load_all(self) -> tuple[JobStored]:
        raise NotImplementedError
