from __future__ import annotations

import abc
import asyncio
from typing import List, Optional


class ABackend(metaclass=abc.ABCMeta):
    """
    Abstract class for test backends.
    The implementations must call self.start_signal() that indicates successfully start for the code
    that controls (by using start_signals_list) the launch of the backends.
    """

    start_signals_list: Optional[List[str]] = None

    @property
    @abc.abstractmethod
    def port(self) -> int:
        pass

    def run(self, start_signals: List[str]) -> None:
        self.start_signals_list = start_signals
        asyncio.run(self._run())

    def start_signal(self) -> None:
        if self.start_signals_list is not None:
            self.start_signals_list.append(f"{self!r} start message")

    async def _run(self) -> None:
        await self.start_server()

    @abc.abstractmethod
    async def start_server(self) -> None:
        pass
