from benchmarks.serializers.common import serializer_case
from jobify.serializers import ExtendedJSONSerializer
from .common import (
    BenchData,
    BenchDataclass,
    BenchNamedTuple,
    NestedBenchDataclass,
    Permissions,
    Priority,
    Status,
    benchmark_serializer,
)


@benchmark_serializer
class TestExtendedJson:
    def setup_method(self) -> None:
        self.serializer = ExtendedJSONSerializer(
            (
                BenchDataclass,
                NestedBenchDataclass,
                BenchNamedTuple,
                Status,
                Priority,
                Permissions,
                BenchData,
            )
        )

    def test_measure(self) -> None:
        serializer_case(self.serializer)
