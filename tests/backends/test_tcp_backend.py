import asyncio
from asyncio.base_events import Server
from unittest.mock import AsyncMock, Mock

import pytest

from backends.tcp_backend import TCPBackend


class ConcreteBackend(TCPBackend):
    port = 10103


class TestTCPBackend:
    def test_run_server(self, mocker):
        backend = ConcreteBackend()
        start_signals_list = Mock(spec=list)
        asyncio_server_mock = AsyncMock(spec=Server)
        start_server_spy = mocker.patch("asyncio.start_server", return_value=asyncio_server_mock)

        class StopServerCycleError(BaseException):
            pass

        mocker.patch("asyncio.sleep", AsyncMock(side_effect=StopServerCycleError))

        with pytest.raises(StopServerCycleError):
            backend.run(start_signals_list)

        start_server_spy.assert_awaited_once_with(backend.handle_connection, "localhost", backend.port)
        asyncio_server_mock.start_serving.assert_awaited_once_with()
        start_signals_list.append.assert_called_once_with(f"{backend!r} start message")

    async def test_handle_connection(self):
        # test for current stub implementation TCPBackend handle_connection method
        backend = ConcreteBackend()
        mock_reader = AsyncMock(spec=asyncio.StreamReader)
        mock_reader.read = AsyncMock(return_value=b"data")
        mock_writer = AsyncMock(spec=asyncio.StreamWriter)
        mock_writer.drain = AsyncMock()

        await backend.handle_connection(mock_reader, mock_writer)

        mock_reader.read.assert_awaited_once_with(1024)
        mock_writer.write.assert_called_once_with(b"data")
        mock_writer.drain.assert_awaited_once_with()
        mock_writer.close.assert_called_once_with()
