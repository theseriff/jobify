import pytest

from benchmarks.serializers.common import serializer_case
from jobify.serializers import MsgpackSerializer
from .common import PairAdapter, parametrize_adapters


@pytest.mark.benchmark(group="serializers")
class TestMsgpack:
    def setup_method(self) -> None:
        self.serializer = MsgpackSerializer()

    @parametrize_adapters
    def test_measure(self, adapter: PairAdapter) -> None:
        serializer_case(self.serializer, adapter=adapter)
