"""Loader and Dumper implementation using the pydantic library."""

from __future__ import annotations

from collections.abc import Hashable
from typing import TYPE_CHECKING, Any, TypeVar

from typing_extensions import override

from jobify._internal.common.constants import UNSET
from jobify._internal.typeadapter.base import Dumper, Loader

if TYPE_CHECKING:
    from pydantic import ConfigDict

try:
    import pydantic
except ImportError:
    pydantic = UNSET


T = TypeVar("T", bound=Hashable)


class PydanticConverter(Loader, Dumper):
    """Load and dump data using pydantic's TypeAdapter.

    See https://docs.pydantic.dev/latest/api/type_adapter/ for more information.
    """

    def __init__(  # noqa: PLR0913
        self,
        *,
        config: ConfigDict | None = None,
        strict: bool | None = None,
        from_attributes: bool | None = None,
        by_alias: bool = False,
        exclude_none: bool = False,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the pydantic converter.

        Args:
            config: Pydantic ``ConfigDict`` passed to each ``TypeAdapter``.
                Cannot be used when the target type already defines its own
                config (e.g. ``BaseModel``, ``TypedDict``, ``dataclass``).
            strict: If ``True``, disable coercions and require exact types
                during validation.
            from_attributes: If ``True``, extract data from object attributes
                as well as dict keys during validation. Useful when loading
                from ORM objects such as SQLAlchemy models.
            by_alias: If ``True``, use field serialization aliases as output
                keys instead of Python attribute names.
            exclude_none: If ``True``, omit fields whose value is ``None``
                from the serialized output.
            context: Arbitrary context object passed to validators and
                serializers that accept a ``ValidationInfo`` or
                ``SerializationInfo`` argument.

        Raises:
            ImportError: If pydantic is not installed.

        """
        if pydantic is UNSET:
            msg = "pydantic is required: `uv add jobify[pydantic]`"
            raise ImportError(msg)

        self._config = config
        self.strict = strict
        self.from_attributes = from_attributes
        self.by_alias = by_alias
        self.exclude_none = exclude_none
        self.context = context
        self._cache_adapters: dict[Hashable, pydantic.TypeAdapter[Any]] = {}

    def _adapter(self, tp: type[T]) -> pydantic.TypeAdapter[T]:
        adapter = self._cache_adapters.get(tp)

        if adapter is None:
            adapter = pydantic.TypeAdapter(tp, config=self._config)
            self._cache_adapters[tp] = adapter

        return adapter

    @override
    def load(self, data: Any, tp: type[T], /) -> T:
        """Validate and coerce data into the specified type.

        Args:
            data: The raw input to validate.
            tp: The target type to validate against.

        Returns:
            The validated and coerced object of type ``tp``.

        """
        return self._adapter(tp).validate_python(
            data,
            strict=self.strict,
            from_attributes=self.from_attributes,
            context=self.context,
        )

    @override
    def dump(self, data: Any, tp: Any, /) -> Any:
        """Serialize an object to a JSON-compatible Python structure.

        Converts complex types such as dataclasses, Pydantic models, enums,
        and datetimes into plain ``dict``, ``list``, ``str``, ``int``,
        ``float``, ``bool``, or ``None`` values suitable for any binary
        serializer (e.g. orjson, cbor2, msgpack).

        Args:
            data: The object to serialize.
            tp: The type whose pydantic schema governs serialization.

        Returns:
            A JSON-compatible Python object.

        """
        return self._adapter(tp).dump_python(
            data,
            mode="json",
            by_alias=self.by_alias,
            exclude_none=self.exclude_none,
            context=self.context,
        )
