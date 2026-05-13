from benchmarks.serializers.common import serializer_case
from jobify.serializers import OrjsonSerializer
from .common import PairAdapter, benchmark_serializer, parametrize_adapters


@benchmark_serializer
class TestOrjson:
    def setup_method(self) -> None:
        self.serializer = OrjsonSerializer()

    @parametrize_adapters
    def test_measure(self, adapter: PairAdapter) -> None:
        serializer_case(self.serializer, adapter=adapter)
