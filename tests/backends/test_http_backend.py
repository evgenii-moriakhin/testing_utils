import re
import socket
from unittest.mock import AsyncMock, Mock

import pytest
from aiohttp.web_runner import AppRunner, BaseSite, TCPSite
from multidict import CIMultiDict, CIMultiDictProxy, istr
from schema import Optional, Or, Regex

from backends.http.http_backend import HTTPBackend, HTTPRule, _TCPSite
from backends.http.http_results import HTTPResult


class ConcreteBackend(HTTPBackend):
    port = 10102


class TestHTTPBackend:
    @pytest.skip(reason="NDA")
    def test_init(self, mocker):
        app_mock = Mock()
        app_runner_cls_spy = mocker.patch("aiohttp.web.Application", return_value=app_mock)

        backend = ConcreteBackend()

        app_runner_cls_spy.assert_called_once_with(middlewares=[...])
        assert backend.app is app_mock
        assert backend.server is None
        assert backend.rules == (HTTPRule(),)

    def test_run_server(self, mocker):
        app_mock = Mock()
        mocker.patch("aiohttp.web.Application", return_value=app_mock)
        backend = ConcreteBackend()
        start_signals_list = Mock(spec=list)
        app_runner_mock = AsyncMock(spec=AppRunner)
        app_runner_mock.setup = AsyncMock()
        app_runner_cls_spy = mocker.patch("aiohttp.web.AppRunner", return_value=app_runner_mock)
        server = AsyncMock(spec=TCPSite)
        server.start = AsyncMock()
        tcp_site_cls_spy = mocker.patch(
            "backends.http.http_backend._TCPSite", return_value=server
        )

        class StopServerCycleError(BaseException):
            pass

        mocker.patch("asyncio.sleep", AsyncMock(side_effect=StopServerCycleError))

        with pytest.raises(StopServerCycleError):
            backend.run(start_signals_list)

        endpoint = "/{any_endpoint:.*}"
        app_mock.router.add_get.assert_called_once_with(endpoint, backend.handle)
        app_mock.router.add_post.assert_called_once_with(endpoint, backend.handle)
        app_mock.router.add_put.assert_called_once_with(endpoint, backend.handle)
        app_mock.router.add_patch.assert_called_once_with(endpoint, backend.handle)
        app_mock.router.add_delete.assert_called_once_with(endpoint, backend.handle)

        app_runner_cls_spy.assert_called_once_with(backend.app)
        app_runner_mock.setup.assert_awaited_once_with()
        tcp_site_cls_spy.assert_called_once_with(app_runner_mock, "localhost", backend.port)
        server.start.assert_awaited_once_with()
        start_signals_list.append.assert_called_once_with(f"{backend!r} start message")

    async def test_handle(self, mocker, request_mock):
        backend = ConcreteBackend()
        response_mock = Mock()
        response_cls_spy = mocker.patch("aiohttp.web.Response", return_value=response_mock)

        response = await backend.handle(request_mock)

        response_cls_spy.assert_called_once_with(body="HTTP BACKEND RESULT", status=200)
        assert response is response_mock

    async def test_handle_several_rules(self, mocker, request_mock):
        backend = ConcreteBackend()
        backend.rules = (
            HTTPRule(query_params=re.compile("some_odd_request")),
            HTTPRule(result=HTTPResult("ANOTHER HTTP BACKEND RESULT")),
            HTTPRule(),
        )
        response_mock = Mock()
        response_cls_spy = mocker.patch("aiohttp.web.Response", return_value=response_mock)

        response = await backend.handle(request_mock)

        response_cls_spy.assert_called_once_with(body="ANOTHER HTTP BACKEND RESULT", status=200)
        assert response is response_mock

    async def test_handle_empty_rules(self, mocker, request_mock):
        backend = ConcreteBackend()
        backend.rules = ()
        response_mock = Mock()
        response_cls_spy = mocker.patch("aiohttp.web.json_response", return_value=response_mock)

        response = await backend.handle(request_mock)

        incoming_request_info = {
            "method": request_mock.method,
            "path": request_mock.rel_url.path,
            "query_params": dict(request_mock.rel_url.query),
            "headers": dict(request_mock.headers),
        }
        error_response_json = {
            "ERROR": "No matching rule found for incoming request",
            "incoming_request_info": incoming_request_info,
        }
        response_cls_spy.assert_called_once_with(error_response_json, status=404)
        assert response is response_mock


class TestTCPSite:
    """
    test overwritten _TCPSite.start() method behaviour. It is actually such TCPSite.start(),
    but with additional family=socket.AF_INET params for loop.create_server()"
    """

    async def test_overwritten_tcp_site_start(self, mocker):
        mock_runner = Mock(spec=AppRunner)
        site = _TCPSite(mock_runner, "localhost", 1000)
        base_site_start = mocker.spy(BaseSite, "start")
        mock_event_loop = AsyncMock()
        mocker.patch("asyncio.get_event_loop", return_value=mock_event_loop)

        await site.start()

        base_site_start.assert_awaited_once()
        mock_event_loop.create_server.assert_awaited_once_with(
            mock_runner.server,
            "localhost",
            1000,
            family=socket.AF_INET,
            ssl=None,
            backlog=128,
            reuse_address=None,
            reuse_port=None,
        )

    async def test_overwritten_tcp_site_start_assertion_error(self, mocker):
        mock_runner = Mock(spec=AppRunner)
        site = _TCPSite(mock_runner, "localhost", 1000)
        mock_runner.server = None
        base_site_start = mocker.spy(BaseSite, "start")

        with pytest.raises(AssertionError):
            await site.start()
        base_site_start.assert_awaited_once()


class TestHTTPRule:
    def test_init(self):
        rule = HTTPRule()
        assert rule.method is None
        assert rule.path is None
        assert rule.query_params is None
        assert rule.headers is None
        assert rule.result == HTTPResult("HTTP BACKEND RESULT")

    @pytest.mark.parametrize(
        "method, matches_expected", ((None, True), ("get", True), ("GeT", True), ("post", False), ("", False))
    )
    def test_method_matches(self, method, matches_expected, request_mock):
        rule = HTTPRule(method=method)

        matches_result = rule.method_mathes(request_mock)

        assert matches_result is matches_expected

    @pytest.mark.parametrize(
        "path, matches_expected",
        (
            (None, True),
            ("/search", True),
            ("/another_search", False),
            ("", False),
            (Regex("/se.*"), True),
            (Regex("/an.*"), False),
        ),
    )
    def test_path_matches(self, path, matches_expected, request_mock):
        rule = HTTPRule(path=path)

        matches_result = rule.path_matches(request_mock)

        assert matches_result is matches_expected

    @pytest.mark.parametrize(
        "query_params, matches_expected",
        (
            (None, True),
            ({"q": "vk", "num": "10"}, True),
            ({"q": Regex(".*v.*k.*"), "num": "10"}, True),
            ({Regex(".*"): Regex(".*")}, True),
            ({Regex("nu.*"): Regex("1.*"), Optional("q"): str}, True),
            ({"q": "ya"}, False),
            ({"foo": "bar"}, False),
            ({}, False),
            ({str: Or(Regex(".*vk"), "10")}, True),
        ),
    )
    def test_query_params_match(self, query_params, matches_expected, request_mock):
        rule = HTTPRule(query_params=query_params)

        matches_result = rule.query_params_match(request_mock)

        assert matches_result is matches_expected

    @pytest.mark.parametrize(
        "query_params, matches_expected",
        (
            ({"q": "vk"}, True),
            ({"q": Regex(".*v.*k.*")}, True),
            ({"num": "10"}, True),
            ({Regex("nu.*"): "10"}, True),
            ({"foo": "bar"}, False),
            ({"q": "ya"}, False),
            ({}, True),
        ),
    )
    def test_query_params_match_ignore_extra(self, query_params, matches_expected, request_mock):
        rule = HTTPRule(query_params=query_params, ignore_extra_query_params=True)

        matches_result = rule.query_params_match(request_mock)

        assert matches_result is matches_expected

    @pytest.mark.parametrize(
        "headers, matches_expected",
        (
            (None, True),
            ({"foo": "bar", "foo1": "bar1", "foo2": "bar2"}, True),
            ({"foo": "bar", "foo1": Regex(".*ba"), "foo2": "bar2"}, True),
            ({"foo": "bar", "foo1": "bar1"}, False),
            ({"foo4": "bar4"}, False),
            ({}, False),
            ({"foo": Regex(".*ba"), "foo1": Regex(".*ba")}, False),
            ({Regex("fo.*"): Regex(".*ba")}, True),
            ({str: Regex("bar.*")}, True),
            ({str: Regex("bar1.*")}, False),
        ),
    )
    def test_headers_match(self, headers, matches_expected, request_mock):
        # arrange request headers for that test purposes
        request_mock.headers = CIMultiDictProxy(
            CIMultiDict([(istr("foo"), "bar"), ("foo1", "bar1"), (istr("foo2"), "bar2")])
        )
        rule = HTTPRule(headers=headers)

        matches_result = rule.headers_match(request_mock)

        assert matches_result is matches_expected

    @pytest.mark.parametrize(
        "headers, matches_expected",
        (
            ({"foo": "bar", "foo1": "bar1", "foo2": "bar2"}, True),
            ({"foo4": "bar4"}, False),
            ({"foo": "bar", "foo1": "bar1"}, True),
            ({"foo": "bar", "foo1": Regex(".*ba")}, True),
            ({}, True),
            ({"foo": Regex(".*ba"), "foo1": Regex(".*ba")}, True),
        ),
    )
    def test_headers_match_ignore_extra(self, headers, matches_expected, request_mock):
        # arrange request headers for that test purposes
        request_mock.headers = CIMultiDictProxy(
            CIMultiDict([(istr("foo"), "bar"), ("foo1", "bar1"), (istr("foo2"), "bar2")])
        )
        rule = HTTPRule(headers=headers, ignore_extra_headers=True)

        matches_result = rule.headers_match(request_mock)

        assert matches_result is matches_expected

    def test_matches_calls(self, object_spy, request_mock):
        # rule, that matches with any request
        rule = HTTPRule()
        object_spy(rule)

        rule.matches(request_mock)

        rule.method_mathes.assert_called_once_with(request_mock)
        rule.path_matches.assert_called_once_with(request_mock)
        rule.query_params_match.assert_called_once_with(request_mock)
        rule.headers_match.assert_called_once_with(request_mock)

        assert rule.matches.spy_return is all(
            [
                rule.method_mathes.spy_return,
                rule.path_matches.spy_return,
                rule.query_params_match.spy_return,
                rule.headers_match.spy_return,
            ]
        )


class TestHTTPResult:
    def test_init_status_http_result(self):
        result = HTTPResult()

        assert result.status == 200
        assert result.data == ""

    @pytest.mark.parametrize("init_params", (({}), ({"data": "some_data", "status": 424})))
    async def test_process_status_http_result(self, mocker, request_mock, init_params):
        result = HTTPResult(**init_params)

        response_mock = Mock()
        response_cls_spy = mocker.patch("aiohttp.web.Response", return_value=response_mock)

        response = await result.process(request_mock)

        response_cls_spy.assert_called_once_with(
            body=init_params.get("data", ""), status=init_params.get("status", 200)
        )
        assert response is response_mock
