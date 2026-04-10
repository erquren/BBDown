"""Series list (系列) fetcher, ported from C# SeriesListFetcher.cs."""

from __future__ import annotations

import json

from bbdown.core.entity.entity import Page
from bbdown.core.entity.vinfo import VInfo
from bbdown.core.fetcher.ifetcher import IFetcher
from bbdown.core.util.http_util import get_web_source


class SeriesListFetcher(IFetcher):

    async def fetch(self, id: str) -> VInfo:
        biz_id = id[12:]  # strip "seriesBizId:" prefix

        api = f"https://api.bilibili.com/x/v1/medialist/info?type=5&biz_id={biz_id}&tid=0"
        raw = await get_web_source(api)
        info_json = json.loads(raw)
        data = info_json["data"]

        list_title: str = data["title"]
        intro: str = data.get("intro", "")
        pub_time: int = data.get("ctime", 0)

        pages_info: list[Page] = []
        has_more = True
        oid = ""
        index = 1

        while has_more:
            list_api = (
                f"https://api.bilibili.com/x/v2/medialist/resource/list"
                f"?type=5&oid={oid}&otype=2&biz_id={biz_id}"
                f"&bvid=&with_current=true&mobi_app=web&ps=20&direction=false&sort_field=1&tid=0&desc=true"
            )
            raw = await get_web_source(list_api)
            list_json = json.loads(raw)
            data = list_json["data"]
            has_more = data.get("has_more", False)

            for m in data.get("media_list", []):
                # 只处理未失效的视频条目（与收藏夹解析逻辑保持一致）
                attr = m.get("attr", 0)
                if attr != 0:
                    continue

                page_count: int = m.get("page", 0)
                m_desc: str = m.get("intro", "")
                owner_name: str = str(m.get("upper", {}).get("name", ""))
                owner_mid: str = str(m.get("upper", {}).get("mid", ""))

                for page in m.get("pages", []):
                    dim = page.get("dimension", {})
                    m_title = m.get("title", "")
                    if page_count == 1:
                        p_title = m_title
                    else:
                        p_title = f"{m_title}_P{page.get('page', '')}_{page.get('title', '')}"

                    p = Page(
                        index=index,
                        aid=str(m["id"]),
                        cid=str(page["id"]),
                        epid="",
                        title=p_title,
                        dur=page.get("duration", 0),
                        res=f'{dim.get("width", "")}x{dim.get("height", "")}',
                        pub_time=m.get("pubtime", 0),
                        cover=m.get("cover", ""),
                        desc=m_desc,
                        owner_name=owner_name,
                        owner_mid=owner_mid,
                    )
                    if p not in pages_info:
                        pages_info.append(p)
                        index += 1
                    # duplicate – don't increment index

                oid = str(m["id"])

        return VInfo(
            title=list_title.strip(),
            desc=intro.strip(),
            pic="",
            pub_time=pub_time,
            pages_info=pages_info,
            is_bangumi=False,
        )
