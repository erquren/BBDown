"""International bangumi info fetcher, ported from C# IntlBangumiInfoFetcher.cs."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from bbdown.core import config
from bbdown.core.entity.entity import Page
from bbdown.core.entity.vinfo import VInfo
from bbdown.core.fetcher.ifetcher import IFetcher
from bbdown.core.util.http_util import get_web_source

_STATE_RE = re.compile(r"window\.__INITIAL_STATE__=([\s\S].*?);\(function\(\)")


class IntlBangumiInfoFetcher(IFetcher):

    async def fetch(self, id: str) -> VInfo:
        id = id[3:]  # strip "ep:" prefix
        index = ""

        host = "api.bilibili.tv" if config.HOST == "api.bilibili.com" else config.HOST
        api = (
            f"https://{host}/intl/gateway/v2/ogv/view/app/season"
            f"?ep_id={id}&platform=android&s_locale=zh_SG&mobi_app=bstar_a"
        )
        if config.TOKEN:
            api += f"&access_key={config.TOKEN}"

        raw = (await get_web_source(api)).replace("\\/", "/")
        info_json = json.loads(raw)
        result = info_json["result"]

        season_id: str = str(result["season_id"])
        cover: str = result.get("cover", "")
        title: str = result.get("title", "")
        desc: str = result.get("evaluate", "")

        if not cover:
            anime_url = f"https://bangumi.bilibili.com/anime/{season_id}"
            web = await get_web_source(anime_url)
            if web:
                m = _STATE_RE.search(web)
                if m:
                    state_data = json.loads(m.group(1))
                    media_info = state_data.get("mediaInfo", {})
                    cover = media_info.get("cover", cover)
                    title = media_info.get("title", title)
                    desc = media_info.get("evaluate", desc)

        pub_time_str: str = result.get("publish", {}).get("pub_time", "")
        pub_time: int = 0
        if pub_time_str:
            try:
                dt = datetime.strptime(pub_time_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                pub_time = int(dt.timestamp())
            except ValueError:
                pub_time = 0

        pages_raw: list = result.get("episodes", [])
        pages_info: list[Page] = []
        i = 1

        # Check modules for sections containing the ep id
        modules = result.get("modules", [])
        for section in modules:
            if f"/{id}" in json.dumps(section):
                pages_raw = section["data"]["episodes"]
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

            p_pub_time: int = 0
            try:
                p_pub_time = page["pub_time"]
            except (KeyError, TypeError):
                pass

            p = Page(
                index=i,
                aid=str(page["aid"]),
                cid=str(page["cid"]),
                epid=str(page["id"]),
                title=_title,
                dur=0,
                res=res,
                pub_time=p_pub_time,
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
