# pylint: disable=unsubscriptable-object
# for E1136: Value 'Queue' is unsubscriptable (unsubscriptable-object)
# https://github.com/PyCQA/pylint/issues/3488
# and for error E1136: Value 'Pattern' is unsubscriptable (unsubscriptable-object)
# looks like that pylint return failure positive result https://github.com/PyCQA/pylint/issues/3882
# but if remove generic type parameter mypy strict mode error occurs:
# error: Missing type parameters for generic type "Pattern"
from __future__ import annotations

import contextlib
import logging
import multiprocessing
import re
from multiprocessing.managers import ListProxy
from pathlib import Path
from queue import Empty, Queue
from re import Pattern
from time import monotonic
from types import TracebackType
from typing import Generator, List, Optional, Type, Union

from backends.abackend import ABackend


@contextlib.contextmanager
def NDA_application_manager(
    NDA_application_cls: Type[...],
    NDA_conf_filepath: Union[str, Path],
    server_start_timeout_sec: float = 5,
) -> Generator[Queue[logging.LogRecord], None, None]:
    manager = multiprocessing.Manager()
    server_log_queue = manager.Queue()
    app_name = f"... application {NDA_application_cls!r}"
    NDA_app = multiprocessing.Process(
        name=app_name,
        target=...,
        args=(NDA_application_cls, server_log_queue, NDA_conf_filepath),
        daemon=True,
    )
    try:
        logs_storage = LogsStorage(server_log_queue)
        NDA_app.start()
        start = monotonic()
        while monotonic() - start < server_start_timeout_sec:
            if logs_storage.has_info_log_record(
                re.compile(".*Start serving on.*"), collect_new_records_from_queue=True
            ):
                break
        else:
            errors = [error_log.message for error_log in logs_storage.filter_logs("ERROR")]
            errors_traces = "\n***\n".join(errors) or "<empty>"
            raise TimeoutError(
                f"{app_name} not starts with given timeout {server_start_timeout_sec=}\n\n"
                f"{app_name} ERRORS:\n\n{errors_traces}"
            )

        yield server_log_queue
    finally:
        manager.shutdown()
        NDA_app.terminate()
        NDA_app.join()


@contextlib.contextmanager
def backends_manager(backends_to_start: List[ABackend]) -> Generator[None, None, None]:
    """
    context manager which starts multiple backends each one in separate daemon process

    example for integration tests with pytest e.g.:

    @pytest.fixture(scope="session", autouse=True)
    def run_backends():
        backends = [SomeBackend()]
        with backends_manager(backends):
            yield
    """
    backends_processes = []
    try:
        backends_processes = start_backends(backends_to_start)
        yield
    finally:
        for proc in backends_processes:
            proc.terminate()
        for proc in backends_processes:
            proc.join()


def start_backends(backends: List[ABackend], start_timeout_sec: float = 5) -> List[multiprocessing.Process]:
    if len(backends) != len({backend.port for backend in backends}):
        raise ValueError(f"Some given backends from <{backends=}> have same port")

    def start_backend(backend: ABackend, start_signals: ListProxy[str]) -> multiprocessing.Process:
        proc = multiprocessing.Process(
            name=f"backend application {backend!r}", target=backend.run, args=(start_signals,), daemon=True
        )
        proc.start()
        return proc

    manager = multiprocessing.Manager()
    try:
        start_signals_list: ListProxy[str] = manager.list()
        backend_processes = [start_backend(backend, start_signals_list) for backend in backends]
        start = monotonic()
        while monotonic() - start < start_timeout_sec:
            if len(start_signals_list) == len(backend_processes):
                break
        else:
            raise TimeoutError(
                f"There are backends which are not started with {start_timeout_sec=}.\n"
                f"start_signals_list={start_signals_list}"
            )
    finally:
        manager.shutdown()
    return backend_processes


class LogsStorage:
    """
    A helper class for keeping track of logs that are written to the Queue.

    Can be used as a contextmanager, in which case it clears the queue of logs
    that were before the contextmanager was created and captures logs that were written during context execution

    contextmanager is the recommended use of this class (for testing purposes, for which this class was designed),
    but you can call some methods manually if necessary
    """

    logs_queue: Queue[logging.LogRecord]
    logs_storage: List[logging.LogRecord]

    def __init__(self, logs_queue: Queue[logging.LogRecord]):
        # it is expected that the logging.LogRecord are queued
        self.logs_queue = logs_queue
        self.logs_storage = []

    def __enter__(self) -> "LogsStorage":
        """clear queue before start collect logs to storage"""
        self.clear_logs_queue()
        return self

    def __exit__(
        self, exc_type: Optional[Type[BaseException]], exc_val: Optional[BaseException], exc_tb: Optional[TracebackType]
    ) -> None:
        """collect and store items from queue of the end"""
        self.collect_from_queue()

    def clear_logs_queue(self) -> None:
        """Clear tracked logs queue"""
        while True:
            try:
                self.logs_queue.get_nowait()
            except Empty:
                break

    def clear_logs_storage(self) -> None:
        self.logs_storage.clear()

    def collect_from_queue(self) -> None:
        """Updates the log_storage with new logs from queue"""
        while True:
            try:
                self.logs_storage.append(self.logs_queue.get_nowait())
            except Empty:
                break

    def has_log_record(
        self, message_pattern: Pattern[str], level: str, collect_new_records_from_queue: bool = False
    ) -> bool:
        """
        server logs have or have no log record for this pattern and debug level

        collect_new_records_from_queue - parameter to search also for new logs in the queue,
        not only those currently in the storage.
        method call with this parameter updates the log_storage
        """
        if collect_new_records_from_queue:
            self.collect_from_queue()
        for log in self.filter_logs(level):
            if message_pattern.match(log.message):
                return True
        return False

    def filter_logs(self, level: Optional[str] = None, name: Optional[str] = None) -> List[logging.LogRecord]:
        filtered_logs = (log for log in self.logs_storage)
        if level is not None:
            filtered_logs = (log for log in filtered_logs if log.levelname == level)
        if name is not None:
            filtered_logs = (log for log in filtered_logs if log.name == name)
        return [*filtered_logs]

    def has_info_log_record(self, message_pattern: Pattern[str], collect_new_records_from_queue: bool = False) -> bool:
        return self.has_log_record(
            message_pattern, level="INFO", collect_new_records_from_queue=collect_new_records_from_queue
        )

    def has_error_log_record(self, message_pattern: Pattern[str], collect_new_records_from_queue: bool = False) -> bool:
        return self.has_log_record(
            message_pattern, level="ERROR", collect_new_records_from_queue=collect_new_records_from_queue
        )

    def has_warning_log_record(
        self, message_pattern: Pattern[str], collect_new_records_from_queue: bool = False
    ) -> bool:
        return self.has_log_record(
            message_pattern, level="WARNING", collect_new_records_from_queue=collect_new_records_from_queue
        )
