"""MessagePack serializer implementation using the msgpack library."""

from collections.abc import Callable
from typing import Any, cast

from typing_extensions import override

from jobify._internal.common.constants import UNSET
from jobify._internal.serializers.base import JSONCompat, Serializer

try:
    import msgpack
except ImportError:
    msgpack = UNSET


class MsgpackSerializer(Serializer):
    """Serialize and deserialize data using the msgpack library.

    See https://msgpack-python.readthedocs.io for more information.
    """

    def __init__(  # noqa: PLR0913
        self,
        *,
        # Packer options
        default: Callable[[Any], Any] | None = None,
        use_bin_type: bool = True,
        strict_types: bool = False,
        datetime: bool = False,
        unicode_errors: str | None = None,
        # Unpacker options
        raw: bool = False,
        timestamp: int = 0,
        strict_map_key: bool = True,
        use_list: bool = True,
        object_hook: Callable[[dict[Any, Any]], Any] | None = None,
        object_pairs_hook: Callable[[list[tuple[Any, Any]]], Any] | None = None,
        list_hook: Callable[[list[Any]], Any] | None = None,
        ext_hook: Callable[[int, bytes], Any] | None = None,
        max_str_len: int = -1,
        max_bin_len: int = -1,
        max_array_len: int = -1,
        max_map_len: int = -1,
        max_ext_len: int = -1,
    ) -> None:
        """Initialize the MessagePack serializer with packer and unpacker options.

        Args:
            default: Callable invoked for types not natively supported by
                msgpack. Should return a msgpack-serializable value or raise
                ``TypeError`` if the type cannot be handled.
            use_bin_type: Use the msgpack 2.0 ``bin`` type for ``bytes``
                objects. Also enables ``str8`` type for unicode. Should be
                ``True`` (default) for all modern use; set to ``False`` only
                for compatibility with very old msgpack consumers.
            strict_types: If ``True``, only exact types are serialized;
                subclasses are forwarded to ``default``. Also prevents tuples
                from being serialized as arrays.
            datetime: If ``True``, ``datetime`` objects with ``tzinfo`` are
                packed as the msgpack ``Timestamp`` ext type. The timezone
                offset is stripped; use ``timestamp=3`` in unpacker options
                to recover UTC ``datetime`` on the other end.
            unicode_errors: Error handler for encoding unicode strings
                (e.g. ``"strict"``, ``"replace"``, ``"ignore"``). Avoid
                unless you have a specific reason to handle bad unicode.
            raw: If ``True``, unpack msgpack ``raw`` bytes to Python ``bytes``
                instead of decoding to ``str``. Useful when round-tripping
                data packed with ``use_bin_type=False``.
            timestamp: Controls how msgpack ``Timestamp`` ext type is
                deserialized:

                - ``0`` — return a ``msgpack.Timestamp`` object (default).
                - ``1`` — return a ``float`` (seconds since epoch).
                - ``2`` — return an ``int`` (nanoseconds since epoch).
                - ``3`` — return a UTC-aware ``datetime.datetime``.

            strict_map_key: If ``True`` (default), only ``str`` or ``bytes``
                are accepted as map keys, preventing hash-DoS attacks from
                untrusted input.
            use_list: If ``True`` (default), unpack msgpack arrays to Python
                ``list``. If ``False``, unpack to ``tuple``.
            object_hook: Callable invoked with each deserialized ``dict``.
                Its return value replaces the dict in output.
            object_pairs_hook: Callable invoked with a list of ``(key, value)``
                pairs for each deserialized map. Mutually exclusive with
                ``object_hook``.
            list_hook: Callable invoked with each deserialized ``list``. Its
                return value replaces the list in output.
            ext_hook: Callable invoked for ext types with no built-in decoder.
                Receives ``(code, data)`` and should return a Python object.
                Defaults to returning ``msgpack.ExtType(code, data)``.
            max_str_len: Maximum allowed byte length for ``str`` values.
                ``-1`` means no limit.
            max_bin_len: Maximum allowed byte length for ``bytes`` values.
                ``-1`` means no limit.
            max_array_len: Maximum allowed number of elements in arrays.
                ``-1`` means no limit.
            max_map_len: Maximum allowed number of key-value pairs in maps.
                ``-1`` means no limit.
            max_ext_len: Maximum allowed byte length for ext type data.
                ``-1`` means no limit.

        Raises:
            ImportError: If msgpack is not installed.

        """
        if msgpack is UNSET:  # pragma: no cover
            msg = "msgpack is required: `uv add jobify[msgpack]`"
            raise ImportError(msg)

        self.default = default
        self.use_bin_type = use_bin_type
        self.strict_types = strict_types
        self.datetime = datetime
        self.unicode_errors = unicode_errors
        self.raw = raw
        self.timestamp = timestamp
        self.strict_map_key = strict_map_key
        self.use_list = use_list
        self.object_hook = object_hook
        self.object_pairs_hook = object_pairs_hook
        self.list_hook = list_hook
        self.ext_hook = ext_hook
        self.max_str_len = max_str_len
        self.max_bin_len = max_bin_len
        self.max_array_len = max_array_len
        self.max_map_len = max_map_len
        self.max_ext_len = max_ext_len

    @override
    def dumpb(self, data: JSONCompat) -> bytes:
        """Serialize data to MessagePack bytes.

        Args:
            data: The value to serialize.

        Returns:
            MessagePack-encoded bytes.

        """
        return cast(
            "bytes",
            msgpack.dumps(
                data,
                default=self.default,
                use_bin_type=self.use_bin_type,
                strict_types=self.strict_types,
                datetime=self.datetime,
                unicode_errors=self.unicode_errors,
            ),
        )

    @override
    def loadb(self, data: bytes) -> JSONCompat:
        """Deserialize MessagePack bytes to a Python object.

        Args:
            data: MessagePack-encoded bytes to deserialize.

        Returns:
            The deserialized Python object.

        """
        r: JSONCompat = msgpack.loads(
            data,
            raw=self.raw,
            timestamp=self.timestamp,
            strict_map_key=self.strict_map_key,
            use_list=self.use_list,
            object_hook=self.object_hook,
            object_pairs_hook=self.object_pairs_hook,
            list_hook=self.list_hook,
            ext_hook=self.ext_hook,
            max_str_len=self.max_str_len,
            max_bin_len=self.max_bin_len,
            max_array_len=self.max_array_len,
            max_map_len=self.max_map_len,
            max_ext_len=self.max_ext_len,
        )
        return r
