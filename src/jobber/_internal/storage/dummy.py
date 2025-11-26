from jobber._internal.storage.abc import JobRepository, JobStored


class DummyRepository(JobRepository):
    def load_all(self) -> list[JobStored]:
        return []
