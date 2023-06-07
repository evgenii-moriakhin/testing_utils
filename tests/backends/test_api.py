import logging
import re
from multiprocessing import Process
from queue import Empty, Queue
from unittest.mock import Mock, call

import pytest

from backends.abackend import ABackend
from backends.api import (
    LogsStorage,
    backends_manager,
    start_backends,
)


class TestBackendsManager:
    def test_backends_manager(self, mocker):
        backend1 = Mock(spec=ABackend)
        backend2 = Mock(spec=ABackend)
        start_backends_mock = mocker.patch("backends.api.start_backends")
        backend_processes = [Mock(spec=Process), Mock(spec=Process)]
        start_backends_mock.return_value = backend_processes

        with backends_manager([backend1, backend2]):
            pass

        start_backends_mock.assert_called_once_with([backend1, backend2])
        for proc in backend_processes:
            proc.terminate.assert_called_once_with()
            proc.join.assert_called_once_with()

    def test_success_start_backends(self, mocker):
        # arrange
        process_manager_mock = Mock()
        start_signals_list = ["start_mess1", "start_mess2"]
        process_manager_mock.list.return_value = start_signals_list
        mocker.patch("multiprocessing.Manager", return_value=process_manager_mock)

        backend_processes = [Mock(spec=Process), Mock(spec=Process)]
        process_spy_cls = mocker.patch("multiprocessing.Process", side_effect=iter(backend_processes))

        backend1 = Mock(spec=ABackend)
        backend2 = Mock(spec=ABackend)

        # action
        start_backends([backend1, backend2])

        # assert
        process_spy_cls.mock_calls = [
            call(
                name=f"backend application {backend1!r}", target=backend1.run, args=(start_signals_list,), daemon=True
            ),
            call(
                name=f"backend application {backend2!r}", target=backend2.run, args=(start_signals_list,), daemon=True
            ),
        ]
        for proc in backend_processes:
            proc.start.assert_called_once_with()
        process_manager_mock.shutdown.assert_called_once_with()

    def test_timeout_start_backends(self, mocker):
        # arrange
        process_manager_mock = Mock()
        start_signals_list = ["start_mess1"]
        process_manager_mock.list.return_value = start_signals_list
        mocker.patch("multiprocessing.Manager", return_value=process_manager_mock)

        backend_processes = [Mock(spec=Process), Mock(spec=Process)]
        process_spy_cls = mocker.patch("multiprocessing.Process", side_effect=iter(backend_processes))

        backend1 = Mock(spec=ABackend)
        backend2 = Mock(spec=ABackend)

        # action
        with pytest.raises(TimeoutError) as err:
            start_backends([backend1, backend2], start_timeout_sec=0.1)

        # assert
        assert (
            err.value.args[0]
            == f"There are backends which are not started with start_timeout_sec=0.1.\n{start_signals_list=}"
        )
        process_spy_cls.mock_calls = [
            call(
                name=f"backend application {backend1!r}", target=backend1.run, args=(start_signals_list,), daemon=True
            ),
            call(
                name=f"backend application {backend2!r}", target=backend2.run, args=(start_signals_list,), daemon=True
            ),
        ]
        for proc in backend_processes:
            proc.start.assert_called_once_with()
        process_manager_mock.shutdown.assert_called_once_with()

    def test_start_backends_with_same_ports(self):
        backend1 = Mock(spec=ABackend, port=100)
        backend2 = Mock(spec=ABackend, port=100)
        backends = [backend1, backend2]

        with pytest.raises(ValueError) as err:
            start_backends(backends)
        assert err.value.args[0] == f"Some given backends from <{backends=}> have same port"


class TestLogsStorage:
    def test_init(self):
        queue_mock = Mock(spec=Queue)

        logs_storage = LogsStorage(queue_mock)

        assert logs_storage.logs_queue is queue_mock
        assert not logs_storage.logs_storage

    def test_clear_log_queue(self):
        queue = Queue()
        queue.put(Mock(levelname="INFO", message="log1", spec=logging.LogRecord))
        queue.put(Mock(levelname="INFO", message="log2", spec=logging.LogRecord))
        logs_storage = LogsStorage(queue)

        logs_storage.clear_logs_queue()

        with pytest.raises(Empty):
            queue.get_nowait()

    def test_clear_log_storage(self):
        queue_mock = Mock(spec=Queue)
        logs_storage = LogsStorage(queue_mock)
        logs_storage.logs_storage = [Mock(levelname="INFO", message="log1", spec=logging.LogRecord)]

        logs_storage.clear_logs_storage()

        assert not logs_storage.logs_storage

    def test_collect_from_queue(self):
        queue = Queue()
        mock_log1 = Mock(levelname="INFO", message="log1", spec=logging.LogRecord)
        mock_log2 = Mock(levelname="INFO", message="log2", spec=logging.LogRecord)
        queue.put(mock_log1)
        queue.put(mock_log2)
        logs_storage = LogsStorage(queue)

        logs_storage.collect_from_queue()

        assert logs_storage.logs_storage == [mock_log1, mock_log2]

    def test_filter_logs(self):
        queue_mock = Mock(spec=Queue)
        logs_storage = LogsStorage(queue_mock)
        log_info = Mock(levelname="INFO", message="log1", spec=logging.LogRecord)
        log_info.name = "access"
        log_warning = Mock(levelname="WARNING", message="log2", spec=logging.LogRecord)
        log_warning.name = "extra"
        log_error1 = Mock(levelname="ERROR", message="log3", spec=logging.LogRecord)
        log_error1.name = "package1.errors"
        log_error2 = Mock(levelname="ERROR", message="log4", spec=logging.LogRecord)
        log_error2.name = "package2.errors"
        logs_storage.logs_storage = [log_info, log_warning, log_error1, log_error2]

        assert logs_storage.filter_logs("INFO") == [log_info]
        assert logs_storage.filter_logs("WARNING") == [log_warning]
        assert logs_storage.filter_logs("ERROR") == [log_error1, log_error2]

        assert logs_storage.filter_logs("INFO", name="access") == [log_info]
        assert logs_storage.filter_logs("INFO", name="extra") == []
        assert logs_storage.filter_logs("WARNING", name="extra") == [log_warning]
        assert logs_storage.filter_logs("ERROR", name="extra") == []
        assert logs_storage.filter_logs("ERROR", name="package1.errors") == [log_error1]
        assert logs_storage.filter_logs("ERROR", name="package2.errors") == [log_error2]

    def test_has_log_record(self):
        queue_mock = Mock(spec=Queue)
        logs_storage = LogsStorage(queue_mock)
        log_info1 = Mock(levelname="INFO", message="log_info1", spec=logging.LogRecord)
        log_info2 = Mock(levelname="INFO", message="log_info2", spec=logging.LogRecord)
        log_warning = Mock(levelname="WARNING", message="log2", spec=logging.LogRecord)
        log_error = Mock(levelname="ERROR", message="log3", spec=logging.LogRecord)
        logs_storage.logs_storage = [log_info1, log_info2, log_warning, log_error]

        assert logs_storage.has_log_record(re.compile("log_info1"), level="INFO")
        assert logs_storage.has_log_record(re.compile("log_info2"), level="INFO")
        assert not logs_storage.has_log_record(re.compile("log_info2"), level="ERROR")
        assert not logs_storage.has_log_record(re.compile("log2"), level="INFO")
        assert logs_storage.has_log_record(re.compile(".*2"), level="WARNING")
        assert logs_storage.has_log_record(re.compile("log3"), level="ERROR")

    def test_has_log_record_wrappers(self):
        queue_mock = Mock(spec=Queue)
        logs_storage = LogsStorage(queue_mock)
        log_info = Mock(levelname="INFO", message="log1", spec=logging.LogRecord)
        log_warning = Mock(levelname="WARNING", message="log2", spec=logging.LogRecord)
        log_error = Mock(levelname="ERROR", message="log3", spec=logging.LogRecord)
        logs_storage.logs_storage = [log_info, log_warning, log_error]

        assert logs_storage.has_info_log_record(re.compile("log1"))
        assert not logs_storage.has_info_log_record(re.compile("log2"))
        assert logs_storage.has_warning_log_record(re.compile("log2"))
        assert logs_storage.has_error_log_record(re.compile(".*3"))

    def test_has_log_record_collect_new_records_from_queue(self):
        queue = Queue()
        logs_storage = LogsStorage(queue)
        log_info = Mock(levelname="INFO", message="log1", spec=logging.LogRecord)
        log_warning = Mock(levelname="WARNING", message="log2", spec=logging.LogRecord)
        log_error = Mock(levelname="ERROR", message="log3", spec=logging.LogRecord)
        logs_storage.logs_storage = [log_info, log_warning, log_error]

        assert not logs_storage.has_log_record(re.compile("new_log1"), level="INFO")
        assert not logs_storage.has_log_record(re.compile("new_log2"), level="ERROR")

        queue.put(Mock(levelname="INFO", message="new_log1", spec=logging.LogRecord))
        queue.put(Mock(levelname="ERROR", message="new_log2", spec=logging.LogRecord))

        assert logs_storage.has_log_record(re.compile("new_log1"), level="INFO", collect_new_records_from_queue=True)
        assert logs_storage.has_log_record(re.compile("new_log2"), level="ERROR", collect_new_records_from_queue=True)

    def test_context_manager_logs_storage(self):
        queue = Queue()
        mock_log1 = Mock(levelname="INFO", message="log1", spec=logging.LogRecord)
        mock_log2 = Mock(levelname="INFO", message="log2", spec=logging.LogRecord)
        queue.put(mock_log1)
        queue.put(mock_log2)

        new_log1 = Mock(levelname="INFO", message="new_log1", spec=logging.LogRecord)
        new_log2 = Mock(levelname="ERROR", message="new_log2", spec=logging.LogRecord)
        with LogsStorage(queue) as logs:
            queue.put(new_log1)
            queue.put(new_log2)

        logs.logs_storage = [new_log1, new_log2]
