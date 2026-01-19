import asyncio
import signal
import threading
from unittest.mock import Mock, call, patch

from jobify import Jobify
from jobify._internal.shared_state import SharedState
from jobify._internal.typeadapter.dummy import DummyDumper, DummyLoader
from jobify.serializers import ExtendedJSONSerializer, JSONSerializer
from jobify.storage import SQLiteStorage
from tests.conftest import create_app


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


async def test_wait_all_receives_signal() -> None:
    app = create_app()
    app.task._shared_state.idle_event.clear()

    async def trigger_signal() -> None:
        await asyncio.sleep(0.01)
        signal.raise_signal(signal.SIGINT)

    trigger_task = asyncio.create_task(trigger_signal())

    try:
        await app.wait_all(timeout=1.0)
        assert signal.SIGINT in app._captured_signals

    finally:
        await trigger_task


async def test_capture_signals_restoration_logic() -> None:
    app = create_app()
    initial_handler = signal.getsignal(signal.SIGINT)

    with app._capture_signals():
        current_handler = signal.getsignal(signal.SIGINT)
        assert current_handler != initial_handler

    assert signal.getsignal(signal.SIGINT) == initial_handler


async def test_capture_signals_in_subthread() -> None:
    app = create_app()

    initial_handler = signal.getsignal(signal.SIGINT)

    def run_in_thread() -> None:
        with app._capture_signals():
            assert signal.getsignal(signal.SIGINT) == initial_handler

    thread = threading.Thread(target=run_in_thread)
    thread.start()
    thread.join()


async def test_shutdown_re_raises_signals_integration() -> None:
    app = create_app()
    with app._capture_signals():
        signal.raise_signal(signal.SIGINT)
        signal.raise_signal(signal.SIGTERM)

        assert signal.SIGINT in app._captured_signals
        assert signal.SIGTERM in app._captured_signals

    with patch("signal.raise_signal") as mock_raise:
        await app.shutdown()
        mock_raise.assert_has_calls(
            [call(signal.SIGTERM), call(signal.SIGINT)]
        )
