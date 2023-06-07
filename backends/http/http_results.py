import abc
import dataclasses
from typing import Union

from aiohttp import web


class IHTTPResult(metaclass=abc.ABCMeta):
    """class for building the result for an HTTP response."""

    @abc.abstractmethod
    async def process(self, request: web.Request) -> web.Response:
        """if it's required additional logic overwrite this method"""


@dataclasses.dataclass
class HTTPResult(IHTTPResult):
    """returns the specified status and data in HTTP result"""

    data: Union[str, bytes] = ""
    status: int = 200

    async def process(self, request: web.Request) -> web.Response:  # pylint: disable=unused-argument
        return web.Response(body=self.data, status=self.status)
