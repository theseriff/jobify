from iojobs._internal.durable.abc import JobPersisted, JobRepository


class SQLiteJobRepository(JobRepository):
    def load_all(self) -> tuple[JobPersisted]:
        raise NotImplementedError
