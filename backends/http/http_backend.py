from __future__ import annotations

import abc
import asyncio
import dataclasses
import socket
from typing import Any, Dict, Optional, Sequence, Union

from aiohttp import web
from aiohttp.web_runner import BaseSite, TCPSite
from schema import Regex, Schema

from backends.abackend import ABackend
from backends.http.http_results import HTTPResult, IHTTPResult


@dataclasses.dataclass
class HTTPRule:
    """
    A rule used by the HTTP backend to determine from incoming get-arguments or headers
    which result to give to the client
    """

    method: Optional[str] = None
    path: Optional[Union[str, Regex]] = None
    query_params: Optional[Dict[Any, Any]] = None
    ignore_extra_query_params: bool = False
    headers: Optional[Dict[Any, Any]] = None
    ignore_extra_headers: bool = False
    result: IHTTPResult = HTTPResult("HTTP BACKEND RESULT")

    def matches(self, request: web.Request) -> bool:
        return (
            self.method_mathes(request)
            and self.path_matches(request)
            and self.query_params_match(request)
            and self.headers_match(request)
        )

    def method_mathes(self, request: web.Request) -> bool:
        if self.method is None:
            return True
        return request.method.lower() == self.method.lower()

    def path_matches(self, request: web.Request) -> bool:
        """The path can be either a string (full match will check) or a Regex from Schema-library"""
        path = None if self.path is None else request.rel_url.path
        return Schema(self.path).is_valid(path)  # type: ignore

    def query_params_match(self, request: web.Request) -> bool:
        """
        If self.query_params is None any request query params mark as matched
        If self.query_params is a dictionary, it can be Schema-library compatible (Regex, Optional etc.)
        for check match

        with ignore_extra_query_params is True checks only subset incoming query_params,
        otherwise all incoming query_params
        """
        query = None if self.query_params is None else dict(request.rel_url.query)
        return Schema(self.query_params, ignore_extra_keys=self.ignore_extra_query_params).is_valid(  # type: ignore
            query
        )

    def headers_match(self, request: web.Request) -> bool:
        """
        If self.headers is None any request headers mark as matched
        If self.headers is a dictionary, it can be Schema-library compatible (Regex, Optional etc.) for check match

        with ignore_extra_headers is True checks only subset incoming headers, otherwise all incoming headers
        """
        headers = None if self.headers is None else dict(request.headers)
        return Schema(self.headers, ignore_extra_keys=self.ignore_extra_headers).is_valid(headers)  # type: ignore


class _TCPSite(TCPSite):
    async def start(self) -> None:
        """
        overwrite TCPSite start method, because Gitlab CI with its Docker engine fails with error

        OSError: [Errno 99] error while attempting to bind on address (...): cannot assign requested address

        from https://gitlab.com/systerel/S2OPC/-/issues/486 such problem figure out that problem is the following:
        TCPSite do not allow directly set family for socket, loop.create_server() uses default family=socket.AF_UNSPEC

        this class explicit set family=socket.AF_INET
        """
        await BaseSite.start(self)
        loop = asyncio.get_event_loop()
        server = self._runner.server
        assert server is not None  # nosec
        self._server = await loop.create_server(
            server,
            self._host,
            self._port,
            family=socket.AF_INET,
            ssl=self._ssl_context,
            backlog=self._backlog,
            reuse_address=self._reuse_address,
            reuse_port=self._reuse_port,
        )


class HTTPBackend(ABackend, metaclass=abc.ABCMeta):
    """A class for creating HTTP test backends that use rules to give an HTTP response"""

    rules: Sequence[HTTPRule] = (HTTPRule(),)
    server: Optional[_TCPSite]

    def __init__(self) -> None:
        self.app = web.Application(middlewares=[...])
        self.server = None

    async def handle(self, request: web.Request) -> web.Response:
        for rule in self.rules:
            if rule.matches(request):
                return await rule.result.process(request)
        incoming_request_info = {
            "method": request.method,
            "path": request.rel_url.path,
            "query_params": dict(request.rel_url.query),
            "headers": dict(request.headers),
        }
        error_response_json = {
            "ERROR": "No matching rule found for incoming request",
            "incoming_request_info": incoming_request_info,
        }
        return web.json_response(error_response_json, status=404)

    async def start_server(self) -> None:
        endpoint = "/{any_endpoint:.*}"
        router = self.app.router
        router.add_get(endpoint, self.handle)
        router.add_post(endpoint, self.handle)
        router.add_put(endpoint, self.handle)
        router.add_patch(endpoint, self.handle)
        router.add_delete(endpoint, self.handle)

        runner = web.AppRunner(self.app)
        await runner.setup()
        self.server = _TCPSite(runner, "localhost", self.port)
        await self.server.start()
        self.start_signal()
        while True:
            await asyncio.sleep(3600)
