from unittest.mock import Mock

from backends.abackend import ABackend


class ConcreteBackend(ABackend):
    async def start_server(self) -> None:
        pass

    port = 10101


class TestABackend:
    def test_run_server(self, mocker):
        backend = ConcreteBackend()
        mock_start_signals_list = Mock(spec=list)
        mocker.spy(backend, "start_server")

        backend.run(mock_start_signals_list)

        backend.start_server.assert_awaited_once_with()

    def test_start_signal(self):
        backend = ConcreteBackend()
        mock_start_signals_list = Mock(spec=list)
        backend.run(mock_start_signals_list)

        backend.start_signal()

        mock_start_signals_list.append.assert_called_once_with(f"{backend!r} start message")
