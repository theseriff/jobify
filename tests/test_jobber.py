from unittest.mock import Mock

from jobber import Jobber
from jobber._internal.typeadapter.dummy import DummyDumper, DummyLoader
from jobber.serializers import ExtendedJSONSerializer, JSONSerializer
from jobber.storage import SQLiteStorage


def test_jobber_setup() -> None:
    app = Jobber(storage=None, dumper=None, loader=None, serializer=None)

    assert isinstance(app.configs.serializer, ExtendedJSONSerializer)
    assert isinstance(app.configs.storage, SQLiteStorage)
    assert isinstance(app.configs.dumper, DummyDumper)
    assert isinstance(app.configs.loader, DummyLoader)

    app = Jobber(serializer=JSONSerializer(), dumper=Mock(), loader=Mock())

    assert isinstance(app.configs.serializer, JSONSerializer)
    assert isinstance(app.configs.dumper, Mock)
    assert isinstance(app.configs.loader, Mock)
