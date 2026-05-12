import pytest

from benchmarks.serializers.common import serializer_case
from jobify.serializers import UnsafePickleSerializer


@pytest.mark.benchmark(group="serializers")
class TestPickle:
    def setup_method(self) -> None:
        self.serializer = UnsafePickleSerializer()

    def test_measure(self) -> None:
        serializer_case(self.serializer)
