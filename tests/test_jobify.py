from unittest.mock import Mock

from jobify import Jobify
from jobify._internal.shared_state import SharedState
from jobify._internal.typeadapter.dummy import DummyDumper, DummyLoader
from jobify.serializers import ExtendedJSONSerializer, JSONSerializer
from jobify.storage import SQLiteStorage


async def test_app_setup() -> None:
    app = Jobify(dumper=None, loader=None, serializer=None)
    assert isinstance(app.configs.serializer, ExtendedJSONSerializer)
    assert isinstance(app.configs.storage, SQLiteStorage)
    assert isinstance(app.configs.dumper, DummyDumper)
    assert isinstance(app.configs.loader, DummyLoader)

    app = Jobify(serializer=JSONSerializer(), dumper=Mock(), loader=Mock())
    assert isinstance(app.configs.serializer, JSONSerializer)
    assert isinstance(app.configs.dumper, Mock)
    assert isinstance(app.configs.loader, Mock)

    mock = Mock()
    app._handle_message(mock, mock, mock, mock, mock, mock)


def test_shared_state() -> None:
    shared_state = SharedState()
    assert shared_state.idle_event.is_set()

    mock_job = Mock()
    mock_job.id = "test mock"

    shared_state.register_job(mock_job)
    assert shared_state.idle_event.is_set() is False
    shared_state.unregister_job("test mock")
    assert shared_state.idle_event.is_set()
    shared_state.unregister_job("invalid job id")
    assert shared_state.idle_event.is_set()
