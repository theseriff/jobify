from benchmarks.serializers.common import benchmark_serializer, serializer_case
from jobify.serializers import UnsafePickleSerializer


@benchmark_serializer
class TestPickle:
    def setup_method(self) -> None:
        self.serializer = UnsafePickleSerializer()

    def test_measure(self) -> None:
        serializer_case(self.serializer)
