"""Media list (合集) fetcher, ported from C# MediaListFetcher.cs."""

from __future__ import annotations

import json

from bbdown.core.entity.entity import Page
from bbdown.core.entity.vinfo import VInfo
from bbdown.core.fetcher.ifetcher import IFetcher
from bbdown.core.util.http_util import get_web_source


class MediaListFetcher(IFetcher):

    async def fetch(self, id: str) -> VInfo:
        biz_id = id[10:]  # strip "listBizId:" prefix

        api = f"https://api.bilibili.com/x/v1/medialist/info?type=8&biz_id={biz_id}&tid=0"
        raw = await get_web_source(api)
        info_json = json.loads(raw)
        root = info_json
        data = root.get("data")

        if not isinstance(data, dict):
            # 部分情况下（合集被删除、设为私密或无权访问）data 会是 null
            # 也有可能是"系列"却被误识别为合集，这里优先尝试按系列解析
            try:
                from bbdown.core.fetcher.series_list_fetcher import SeriesListFetcher
                return await SeriesListFetcher().fetch(f"seriesBizId:{biz_id}")
            except Exception:
                code = root.get("code", 0)
                message = root.get("message", "未知错误")
                raise Exception(f"获取合集信息失败(code={code}): {message}")

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
                f"?type=8&oid={oid}&otype=2&biz_id={biz_id}"
                f"&with_current=true&mobi_app=web&ps=20&direction=false&sort_field=1&tid=0&desc=false"
            )
            raw = await get_web_source(list_api)
            list_json = json.loads(raw)
            list_root = list_json
            data = list_root.get("data")

            if not isinstance(data, dict):
                code = list_root.get("code", 0)
                message = list_root.get("message", "未知错误")
                raise Exception(f"获取合集视频列表失败(code={code}): {message}")

            has_more = data.get("has_more", False)

            for m in data.get("media_list", []):
                # 只处理未失效的视频条目
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
