from benchmarks.serializers.common import serializer_case
from jobify.serializers import CBORSerializer
from .common import PairAdapter, benchmark_serializer, parametrize_adapters


@benchmark_serializer
class TestCbor2:
    def setup_method(self) -> None:
        self.serializer = CBORSerializer()

    @parametrize_adapters
    def test_measure(self, adapter: PairAdapter) -> None:
        serializer_case(self.serializer, adapter=adapter)
