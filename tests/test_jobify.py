import asyncio
import signal
import threading
from unittest.mock import Mock, call, patch

from jobify import Jobify
from jobify._internal.task_tracker import TaskTracker
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
    app._start_restored_job_in_memory(mock, mock, mock)


def test_task_tracker() -> None:
    task_tracker = TaskTracker({}, {}, asyncio.Event())

    mock_job = Mock()
    mock_job.id = "test mock"

    task_tracker.register_job(mock_job)
    assert task_tracker.idle_event.is_set() is False
    task_tracker.unregister_job("test mock")
    assert task_tracker.idle_event.is_set()
    task_tracker.unregister_job("invalid job id")
    assert task_tracker.idle_event.is_set()


async def test_wait_all_receives_signal() -> None:
    app = create_app()
    app.task._task_tracker.idle_event.clear()

    async def trigger_signal() -> None:
        await asyncio.sleep(0.01)
        app._handle_exit(signal.SIGINT, None)

    task = asyncio.create_task(trigger_signal())

    try:
        await app.wait_all(timeout=1.0)
        assert signal.SIGINT in app._captured_signals
    finally:
        await task


def test_capture_signals_restoration_logic() -> None:
    app = create_app()
    initial_handler = signal.getsignal(signal.SIGINT)

    with app._capture_signals():
        current_handler = signal.getsignal(signal.SIGINT)
        assert current_handler != initial_handler

    assert signal.getsignal(signal.SIGINT) == initial_handler


def test_capture_signals_in_subthread() -> None:
    app = create_app()
    _ = app.get_active_jobs()

    initial_handler = signal.getsignal(signal.SIGINT)

    def run_in_thread() -> None:
        with app._capture_signals():
            assert signal.getsignal(signal.SIGINT) == initial_handler

    thread = threading.Thread(target=run_in_thread)
    thread.start()
    thread.join()


async def test_shutdown_re_raises_signals_integration() -> None:
    app = create_app()
    app._handle_exit(signal.SIGINT, None)
    app._handle_exit(signal.SIGTERM, None)

    assert signal.SIGINT in app._captured_signals
    assert signal.SIGTERM in app._captured_signals

    with patch("signal.raise_signal") as mock_raise:
        await app.shutdown()
        mock_raise.assert_has_calls(
            [call(signal.SIGTERM), call(signal.SIGINT)]
        )
