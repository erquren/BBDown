"""Fetcher package – video metadata retrieval from various Bilibili APIs."""

from bbdown.core.fetcher.ifetcher import IFetcher
from bbdown.core.fetcher.fetcher_factory import create_fetcher

__all__ = [
    "IFetcher",
    "create_fetcher",
]
