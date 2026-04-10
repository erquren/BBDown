"""Fetcher factory, ported from C# FetcherFactory pattern.

Selects the correct :class:`IFetcher` implementation based on the *aid_ori*
prefix string that the caller passes in.
"""

from __future__ import annotations

from bbdown.core.fetcher.ifetcher import IFetcher


def create_fetcher(aid_ori: str, intl: bool = False) -> IFetcher:
    """Return the appropriate :class:`IFetcher` for *aid_ori*.

    Parameters
    ----------
    aid_ori:
        The raw ID string (e.g. ``"ep:12345"``, ``"cheese:678"``, plain AV id).
    intl:
        Whether the international API should be used for bangumi content.
    """
    if aid_ori.startswith("cheese:"):
        from bbdown.core.fetcher.cheese_info_fetcher import CheeseInfoFetcher
        return CheeseInfoFetcher()

    if aid_ori.startswith("ep:"):
        if intl:
            from bbdown.core.fetcher.intl_bangumi_info_fetcher import IntlBangumiInfoFetcher
            return IntlBangumiInfoFetcher()
        from bbdown.core.fetcher.bangumi_info_fetcher import BangumiInfoFetcher
        return BangumiInfoFetcher()

    if aid_ori.startswith("mid:"):
        from bbdown.core.fetcher.space_video_fetcher import SpaceVideoFetcher
        return SpaceVideoFetcher()

    if aid_ori.startswith("listBizId:"):
        from bbdown.core.fetcher.media_list_fetcher import MediaListFetcher
        return MediaListFetcher()

    if aid_ori.startswith("seriesBizId:"):
        from bbdown.core.fetcher.series_list_fetcher import SeriesListFetcher
        return SeriesListFetcher()

    if aid_ori.startswith("favId:"):
        from bbdown.core.fetcher.fav_list_fetcher import FavListFetcher
        return FavListFetcher()

    from bbdown.core.fetcher.normal_info_fetcher import NormalInfoFetcher
    return NormalInfoFetcher()
