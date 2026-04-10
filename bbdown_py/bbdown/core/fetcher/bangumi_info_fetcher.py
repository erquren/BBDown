"""Bangumi (anime) info fetcher, ported from C# BangumiInfoFetcher.cs."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from bbdown.core import config
from bbdown.core.entity.entity import Page
from bbdown.core.entity.vinfo import VInfo
from bbdown.core.fetcher.ifetcher import IFetcher
from bbdown.core.util.http_util import get_web_source


class BangumiInfoFetcher(IFetcher):

    async def fetch(self, id: str) -> VInfo:
        id = id[3:]  # strip "ep:" prefix
        index = ""
        api = f"https://{config.EPHOST}/pgc/view/web/season?ep_id={id}"
        raw = await get_web_source(api)
        info_json = json.loads(raw)
        result = info_json["result"]

        cover: str = result["cover"]
        title: str = result["title"]
        desc: str = result.get("evaluate", "")
        pub_time_str: str = result.get("publish", {}).get("pub_time", "")
        pub_time: int = 0
        if pub_time_str:
            try:
                dt = datetime.strptime(pub_time_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                pub_time = int(dt.timestamp())
            except ValueError:
                pub_time = 0

        pages_raw = result.get("episodes", [])
        pages_info: list[Page] = []
        i = 1

        # episodes为空; 或者未包含对应epid，番外/花絮什么的
        ep_marker = f"/ep{id}"
        if not (pages_raw and ep_marker in json.dumps(pages_raw)):
            sections = result.get("section", [])
            for section in sections:
                if ep_marker in json.dumps(section):
                    title += "[" + section["title"] + "]"
                    pages_raw = section["episodes"]
                    break

        for page in pages_raw:
            # 跳过预告
            if page.get("badge", "") == "预告":
                continue

            res = ""
            try:
                dim = page["dimension"]
                res = f'{dim["width"]}x{dim["height"]}'
            except (KeyError, TypeError):
                pass

            _title = (page.get("title", "") + " " + page.get("long_title", "")).strip()

            p = Page(
                index=i,
                aid=str(page["aid"]),
                cid=str(page["cid"]),
                epid=str(page["id"]),
                title=_title,
                dur=0,
                res=res,
                pub_time=page.get("pub_time", 0),
            )
            if p.epid == id:
                index = str(p.index)
            pages_info.append(p)
            i += 1

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
