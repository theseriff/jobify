import pytest

from benchmarks.serializers.common import serializer_case
from jobify.serializers import CBORSerializer
from .common import PairAdapter, parametrize_adapters


@pytest.mark.benchmark(group="serializers")
class TestCbor:
    def setup_method(self) -> None:
        self.serializer = CBORSerializer()

    @parametrize_adapters
    def test_measure(self, adapter: PairAdapter) -> None:
        serializer_case(self.serializer, adapter=adapter)
