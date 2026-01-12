from unittest.mock import Mock

from jobify import Jobify
from jobify._internal.typeadapter.dummy import DummyDumper, DummyLoader
from jobify.serializers import ExtendedJSONSerializer, JSONSerializer
from jobify.storage import SQLiteStorage


def test_app_setup() -> None:
    app = Jobify(storage=None, dumper=None, loader=None, serializer=None)
    assert isinstance(app.configs.serializer, ExtendedJSONSerializer)
    assert isinstance(app.configs.storage, SQLiteStorage)
    assert isinstance(app.configs.dumper, DummyDumper)
    assert isinstance(app.configs.loader, DummyLoader)

    app = Jobify(serializer=JSONSerializer(), dumper=Mock(), loader=Mock())
    assert isinstance(app.configs.serializer, JSONSerializer)
    assert isinstance(app.configs.dumper, Mock)
    assert isinstance(app.configs.loader, Mock)
