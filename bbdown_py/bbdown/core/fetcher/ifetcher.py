"""Abstract base for all fetchers, ported from C# IFetcher interface."""

from __future__ import annotations

import abc

from bbdown.core.entity.vinfo import VInfo


class IFetcher(abc.ABC):
    """Every fetcher must implement :meth:`fetch`."""

    @abc.abstractmethod
    async def fetch(self, id: str) -> VInfo:
        """Fetch video information for *id* and return a :class:`VInfo`."""
        ...
