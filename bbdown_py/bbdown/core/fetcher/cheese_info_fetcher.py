"""Cheese (course) info fetcher, ported from C# CheeseInfoFetcher.cs."""

from __future__ import annotations

import json

from bbdown.core.entity.entity import Page
from bbdown.core.entity.vinfo import VInfo
from bbdown.core.fetcher.ifetcher import IFetcher
from bbdown.core.util.http_util import get_web_source


class CheeseInfoFetcher(IFetcher):

    async def fetch(self, id: str) -> VInfo:
        id = id[7:]  # strip "cheese:" prefix
        index = ""
        api = f"https://api.bilibili.com/pugv/view/web/season?ep_id={id}"
        raw = await get_web_source(api)
        info_json = json.loads(raw)
        data = info_json["data"]

        cover: str = data["cover"]
        title: str = data["title"]
        desc: str = data.get("subtitle", "")
        owner_name: str = data["up_info"]["uname"]
        owner_mid: str = str(data["up_info"]["mid"])

        pages_raw = data.get("episodes", [])
        pages_info: list[Page] = []

        for page in pages_raw:
            p = Page(
                index=page["index"],
                aid=str(page["aid"]),
                cid=str(page["cid"]),
                epid=str(page["id"]),
                title=page["title"].strip(),
                dur=page.get("duration", 0),
                res="",
                pub_time=page.get("release_date", 0),
                cover="",
                desc="",
                owner_name=owner_name,
                owner_mid=owner_mid,
            )
            if p.epid == id:
                index = str(p.index)
            pages_info.append(p)

        pub_time: int = pages_info[0].pub_time if pages_info else 0

        return VInfo(
            title=title.strip(),
            desc=desc.strip(),
            pic=cover,
            pub_time=pub_time,
            pages_info=pages_info,
            is_bangumi=True,
            is_cheese=True,
            index=index,
        )
