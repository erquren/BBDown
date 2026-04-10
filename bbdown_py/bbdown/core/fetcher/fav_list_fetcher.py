"""Favorite list fetcher, ported from C# FavListFetcher.cs."""

from __future__ import annotations

import json
import math

from bbdown.core.entity.entity import Page
from bbdown.core.entity.vinfo import VInfo
from bbdown.core.fetcher.ifetcher import IFetcher
from bbdown.core.fetcher.normal_info_fetcher import NormalInfoFetcher
from bbdown.core.util.http_util import get_web_source


class FavListFetcher(IFetcher):

    async def fetch(self, id: str) -> VInfo:
        id = id[6:]  # strip "favId:" prefix
        parts = id.split(":")
        fav_id: str = parts[0]
        mid: str = parts[1]

        # 查找默认收藏夹
        if not fav_id:
            fav_list_api = f"https://api.bilibili.com/x/v3/fav/folder/created/list-all?up_mid={mid}"
            raw = await get_web_source(fav_list_api)
            fav_id = str(json.loads(raw)["data"]["list"][0]["id"])

        page_size = 20
        index = 1
        pages_info: list[Page] = []

        api = (
            f"https://api.bilibili.com/x/v3/fav/resource/list"
            f"?media_id={fav_id}&pn=1&ps={page_size}&order=mtime&type=2&tid=0&platform=web"
        )
        raw = await get_web_source(api)
        info_json = json.loads(raw)
        data = info_json["data"]

        total_count: int = data["info"]["media_count"]
        total_page: int = math.ceil(total_count / page_size)
        title: str = data["info"]["title"]
        intro: str = data["info"].get("intro", "")
        pub_time: int = data["info"].get("ctime", 0)
        # user_name: str = data["info"]["upper"]["name"]

        medias: list = list(data.get("medias", []) or [])

        for page_num in range(2, total_page + 1):
            api = (
                f"https://api.bilibili.com/x/v3/fav/resource/list"
                f"?media_id={fav_id}&pn={page_num}&ps={page_size}&order=mtime&type=2&tid=0&platform=web"
            )
            raw = await get_web_source(api)
            page_data = json.loads(raw)["data"]
            medias.extend(page_data.get("medias", []) or [])

        for m in medias:
            # 只处理未失效视频
            if m.get("attr", 0) != 0:
                continue

            page_count: int = m.get("page", 0)

            if page_count > 1:
                tmp_info = await NormalInfoFetcher().fetch(str(m["id"]))
                for item in tmp_info.pages_info:
                    p = Page(
                        index=index,
                        aid=item.aid,
                        cid=item.cid,
                        epid=item.epid,
                        title=f"{m['title']}_P{item.index}_{item.title}",
                        dur=item.dur,
                        res=item.res,
                        pub_time=item.pub_time,
                        cover=tmp_info.pic,
                        desc=m.get("intro", ""),
                        owner_name=item.owner_name,
                        owner_mid=item.owner_mid,
                    )
                    if p not in pages_info:
                        pages_info.append(p)
                        index += 1
            else:
                p = Page(
                    index=index,
                    aid=str(m["id"]),
                    cid=str(m["ugc"]["first_cid"]),
                    epid="",
                    title=m["title"],
                    dur=m.get("duration", 0),
                    res="",
                    pub_time=m.get("pubtime", 0),
                    cover=m.get("cover", ""),
                    desc=m.get("intro", ""),
                    owner_name=str(m.get("upper", {}).get("name", "")),
                    owner_mid=str(m.get("upper", {}).get("mid", "")),
                )
                if p not in pages_info:
                    pages_info.append(p)
                    index += 1

        return VInfo(
            title=title.strip(),
            desc=intro.strip(),
            pic="",
            pub_time=pub_time,
            pages_info=pages_info,
            is_bangumi=False,
        )
