from __future__ import annotations

from types import SimpleNamespace
from typing import ClassVar

import pytest

import jobify.typeadapter.pydantic as pydantic_typeadapter
from jobify._internal.common.constants import UNSET
from jobify._internal.typeadapter.dummy import DummyDumper, DummyLoader
from jobify.typeadapter import Dumper, Loader, PydanticConverter


class FakeTypeAdapter:
    instances: ClassVar[list[FakeTypeAdapter]] = []

    def __init__(
        self,
        tp: object,
        *,
        config: dict[str, object] | None = None,
    ) -> None:
        self.tp = tp
        self.config = config
        self.validate_calls: list[dict[str, object]] = []
        self.dump_calls: list[dict[str, object]] = []
        FakeTypeAdapter.instances.append(self)

    def validate_python(
        self,
        data: object,
        *,
        strict: bool | None,
        from_attributes: bool | None,
        context: dict[str, object] | None,
    ) -> tuple[str, object, object]:
        self.validate_calls.append(
            {
                "data": data,
                "strict": strict,
                "from_attributes": from_attributes,
                "context": context,
            }
        )
        return ("loaded", self.tp, data)

    def dump_python(
        self,
        data: object,
        *,
        mode: str,
        by_alias: bool,
        exclude_none: bool,
        context: dict[str, object] | None,
    ) -> dict[str, object]:
        self.dump_calls.append(
            {
                "data": data,
                "mode": mode,
                "by_alias": by_alias,
                "exclude_none": exclude_none,
                "context": context,
            }
        )
        return {"dumped": data, "type": self.tp}


@pytest.fixture(autouse=True)
def reset_fake_type_adapter() -> None:
    FakeTypeAdapter.instances.clear()


@pytest.fixture
def fake_pydantic(monkeypatch: pytest.MonkeyPatch) -> None:
    module = SimpleNamespace(ConfigDict=dict, TypeAdapter=FakeTypeAdapter)
    monkeypatch.setattr(pydantic_typeadapter, "pydantic", module)


def test_dummy_loader_returns_data_unchanged() -> None:
    data = {"id": "1"}

    assert DummyLoader().load(data, dict) is data


def test_dummy_dumper_returns_data_unchanged() -> None:
    data = {"id": "1"}

    assert DummyDumper().dump(data, dict) is data


def test_public_typeadapter_exports() -> None:
    assert PydanticConverter.__name__ == "PydanticConverter"
    assert Loader.__name__ == "Loader"
    assert Dumper.__name__ == "Dumper"


def test_pydantic_converter_requires_pydantic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pydantic_typeadapter, "pydantic", UNSET)

    with pytest.raises(ImportError, match="pydantic is required"):
        PydanticConverter()


@pytest.mark.usefixtures("fake_pydantic")
def test_pydantic_converter_load_uses_type_adapter_options() -> None:
    context = {"request_id": "test"}
    config = {"arbitrary_types_allowed": True}
    converter = PydanticConverter(
        config=config,
        strict=True,
        from_attributes=True,
        context=context,
    )

    loaded = converter.load({"id": "1"}, int)

    assert loaded == ("loaded", int, {"id": "1"})
    assert len(FakeTypeAdapter.instances) == 1
    adapter = FakeTypeAdapter.instances[0]
    assert adapter.tp is int
    assert adapter.config is config
    assert adapter.validate_calls == [
        {
            "data": {"id": "1"},
            "strict": True,
            "from_attributes": True,
            "context": context,
        }
    ]


@pytest.mark.usefixtures("fake_pydantic")
def test_pydantic_converter_dump_uses_json_mode_and_options() -> None:
    context = {"request_id": "test"}
    converter = PydanticConverter(
        by_alias=True,
        exclude_none=True,
        context=context,
    )

    dumped = converter.dump({"name": None}, dict)

    assert dumped == {"dumped": {"name": None}, "type": dict}
    assert len(FakeTypeAdapter.instances) == 1
    assert FakeTypeAdapter.instances[0].dump_calls == [
        {
            "data": {"name": None},
            "mode": "json",
            "by_alias": True,
            "exclude_none": True,
            "context": context,
        }
    ]


@pytest.mark.usefixtures("fake_pydantic")
def test_pydantic_converter_reuses_cached_adapter_for_same_type() -> None:
    converter = PydanticConverter()

    converter.load("1", int)
    converter.dump(2, int)
    converter.load("name", str)

    assert [adapter.tp for adapter in FakeTypeAdapter.instances] == [int, str]
    int_adapter = FakeTypeAdapter.instances[0]
    assert len(int_adapter.validate_calls) == 1
    assert len(int_adapter.dump_calls) == 1
