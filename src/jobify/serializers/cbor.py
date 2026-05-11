"""CBOR serializer implementation using the cbor2 library."""

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, TypeAlias

from typing_extensions import override

from jobify._internal.common.constants import UNSET
from jobify._internal.serializers.base import JSONCompat, Serializer

if TYPE_CHECKING:
    from cbor2 import (
        EncoderHook,
        ObjectHook,
        SemanticDecoderCallback,
        ShareableDecoderInitializer,
        TagHook,
    )

try:
    import cbor2
except ImportError:
    cbor2 = UNSET


SemanticDecoders: TypeAlias = (
    "Mapping[int, SemanticDecoderCallback | ShareableDecoderInitializer] | None"
)


class CBORSerializer(Serializer):
    """Serialize and deserialize data using the cbor2 library.

    See https://cbor2.readthedocs.io/en/stable/ for more information.
    """

    def __init__(  # noqa: PLR0913
        self,
        *,
        # Encoder options
        datetime_as_timestamp: bool = False,
        timezone: datetime.tzinfo | None = None,
        value_sharing: bool = False,
        encoders: Mapping[type, "EncoderHook"] | None = None,
        default: "EncoderHook | None" = None,
        canonical: bool = False,
        date_as_datetime: bool = False,
        string_referencing: bool = False,
        indefinite_containers: bool = False,
        # Decoder options
        tag_hook: "TagHook | None" = None,
        object_hook: "ObjectHook | None" = None,
        semantic_decoders: SemanticDecoders = None,
        str_errors: str = "strict",
        max_depth: int = 400,
        allow_indefinite: bool = True,
        immutable: bool = False,
    ) -> None:
        """Initialize the CBOR serializer with encoder and decoder options.

        Args:
            datetime_as_timestamp: Serialize datetimes as UNIX timestamps.
                Makes datetimes more concise on the wire, but loses timezone info.
            timezone: Default timezone for naive datetimes. If not set, naive
                datetimes raise ``ValueError`` during encoding.
            value_sharing: Allow efficient serialization of repeated values and
                cyclic data structures, at the cost of extra overhead.
            encoders: Mapping of Python types to encoder hooks, overriding the
                default encoding for those types.
            default: Fallback encoder hook called when no suitable encoder is found
                for a value.
            canonical: Use canonical CBOR representation (e.g. sorted maps/sets),
                ensuring serializations are comparable without decoding.
            date_as_datetime: Serialize ``date`` objects as datetimes (CBOR tag 0).
                This was the default behavior in cbor2 <= 4.1.2.
            string_referencing: Allow more efficient serialization of repeated
                string values.
            indefinite_containers: Encode containers as indefinite-length using a
                stop code instead of an explicit length prefix.
            tag_hook: Decoder hook for CBOR tags with no built-in decoder. Called
                with the ``CBORTag``; its return value replaces the tag in output.
            object_hook: Decoder hook called for each deserialized ``dict``. Its
                return value replaces the dict in output.
            semantic_decoders: Mapping of semantic tag numbers to decoder callbacks,
                overriding the default decoding for those tags.
            str_errors: Unicode error handler for string decoding (e.g.
                ``"strict"``, ``"replace"``, ``"ignore"``).
            max_depth: Maximum allowed nesting depth for containers.
            allow_indefinite: If ``False``, raise ``CBORDecodeError`` on
                indefinite-length strings or containers in the input.
            immutable: Return immutable types (``tuple``, ``frozenset``) instead of
                mutable ones (``list``, ``set``).

        Raises:
            ImportError: If cbor2 is not installed.

        """
        if cbor2 is UNSET:  # pragma: no cover
            msg = "cbor2 is required: `uv add jobify[cbor2]`"
            raise ImportError(msg)

        self.datetime_as_timestamp = datetime_as_timestamp
        self.timezone = timezone
        self.value_sharing = value_sharing
        self.encoders = encoders
        self.default = default
        self.canonical = canonical
        self.date_as_datetime = date_as_datetime
        self.string_referencing = string_referencing
        self.indefinite_containers = indefinite_containers
        self.tag_hook = tag_hook
        self.object_hook = object_hook
        self.semantic_decoders = semantic_decoders
        self.str_errors = str_errors
        self.max_depth = max_depth
        self.allow_indefinite = allow_indefinite
        self.immutable = immutable

    @override
    def dumpb(self, data: JSONCompat) -> bytes:
        """Serialize data to CBOR bytes.

        Args:
            data: The value to serialize.

        Returns:
            CBOR-encoded bytes.

        """
        return cbor2.dumps(
            data,
            datetime_as_timestamp=self.datetime_as_timestamp,
            timezone=self.timezone,
            value_sharing=self.value_sharing,
            encoders=self.encoders,
            default=self.default,
            canonical=self.canonical,
            date_as_datetime=self.date_as_datetime,
            string_referencing=self.string_referencing,
            indefinite_containers=self.indefinite_containers,
        )

    @override
    def loadb(self, data: bytes) -> JSONCompat:
        """Deserialize CBOR bytes to a Python object.

        Args:
            data: CBOR-encoded bytes to deserialize.

        Returns:
            The deserialized Python object.

        """
        r: JSONCompat = cbor2.loads(
            data,
            tag_hook=self.tag_hook,
            object_hook=self.object_hook,
            semantic_decoders=self.semantic_decoders,
            str_errors=self.str_errors,
            max_depth=self.max_depth,
            allow_indefinite=self.allow_indefinite,
            immutable=self.immutable,
        )
        return r
