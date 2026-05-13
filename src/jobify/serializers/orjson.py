"""JSON serializer implementation using the orjson library."""

from collections.abc import Callable
from typing import Any

from typing_extensions import override

from jobify._internal.common.constants import UNSET
from jobify._internal.serializers.base import JSONCompat, Serializer

try:
    import orjson
except ImportError:
    orjson = UNSET


class OrjsonSerializer(Serializer):
    """Serialize and deserialize data using the orjson library.

    See https://github.com/ijl/orjson for more information.
    """

    def __init__(
        self,
        *,
        default: Callable[[Any], Any] | None = None,
        option: int | None = None,
    ) -> None:
        """Initialize the orjson serializer.

        Args:
            default: Callable invoked for types not natively supported by
                orjson. Should return a JSON-serializable value or raise
                ``TypeError`` if the type cannot be handled.
            option: Bitmask of ``orjson.OPT_*`` flags controlling serialization
                behavior. Multiple flags are combined with ``|``, e.g.
                ``orjson.OPT_NAIVE_UTC | orjson.OPT_NON_STR_KEYS``.

        Raises:
            ImportError: If orjson is not installed.

        """
        if orjson is UNSET:  # pragma: no cover
            msg = "orjson is required: `uv add jobify[orjson]`"
            raise ImportError(msg)

        self.default = default
        self.option = option

    @override
    def dumpb(self, data: JSONCompat) -> bytes:
        """Serialize data to JSON bytes.

        Args:
            data: The value to serialize.

        Returns:
            JSON-encoded bytes.

        """
        return orjson.dumps(data, default=self.default, option=self.option)

    @override
    def loadb(self, data: bytes) -> JSONCompat:
        """Deserialize JSON bytes to a Python object.

        Args:
            data: JSON-encoded bytes to deserialize.

        Returns:
            The deserialized Python object.

        """
        r: JSONCompat = orjson.loads(data)
        return r
