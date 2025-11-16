from jobber._internal.durable.abc import JobPersisted, JobRepository


class DummyRepository(JobRepository):
    def load_all(self) -> list[JobPersisted]:
        return []
