import abc
import asyncio
from asyncio.base_events import Server
from typing import Optional

from backends.abackend import ABackend


class TCPBackend(ABackend, metaclass=abc.ABCMeta):
    """stub for further implementation if it's will be necessary"""

    server: Optional[Server]

    def __init__(self) -> None:
        self.server = None

    async def start_server(self) -> None:
        self.server = await asyncio.start_server(self.handle_connection, "localhost", self.port)
        async with self.server:
            await self.server.start_serving()
            self.start_signal()
            while True:
                await asyncio.sleep(3600)

    @staticmethod
    async def handle_connection(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        data = await reader.read(1024)
        # message = data.decode()
        writer.write(data)
        await writer.drain()
        writer.close()
