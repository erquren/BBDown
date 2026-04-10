"""Normal video info fetcher, ported from C# NormalInfoFetcher.cs."""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET

from bbdown.core.entity.entity import Page
from bbdown.core.entity.vinfo import VInfo
from bbdown.core.fetcher.ifetcher import IFetcher
from bbdown.core.util.http_util import get_web_source

_EP_ID_RE = re.compile(r"ep(\d+)")


class NormalInfoFetcher(IFetcher):

    async def fetch(self, id: str) -> VInfo:
        api = f"https://api.bilibili.com/x/web-interface/view?aid={id}"
        raw = await get_web_source(api)
        info_json = json.loads(raw)
        data = info_json["data"]

        title: str = data["title"]
        desc: str = data["desc"]
        pic: str = data["pic"]
        owner = data["owner"]
        owner_mid: str = str(owner["mid"])
        owner_name: str = owner["name"]
        pub_time: int = data["pubdate"]
        bangumi = False
        bvid: str = data["bvid"]
        cid: int = data["cid"]

        # 互动视频 1:是 0:否
        is_stein_gate: int = data["rights"]["is_stein_gate"]

        # 分p信息
        pages_info: list[Page] = []
        pages = data["pages"]
        for page in pages:
            dim = page.get("dimension", {})
            p = Page(
                index=page["page"],
                aid=id,
                cid=str(page["cid"]),
                epid="",
                title=page["part"].strip(),
                dur=page["duration"],
                res=f'{dim.get("width", "")}x{dim.get("height", "")}',
                pub_time=pub_time,
                cover="",
                desc="",
                owner_name=owner_name,
                owner_mid=owner_mid,
            )
            pages_info.append(p)

        if is_stein_gate == 1:
            # 互动视频获取分P信息
            player_so_api = f"https://api.bilibili.com/x/player.so?bvid={bvid}&id=cid:{cid}"
            player_so_text = await get_web_source(player_so_api)
            root = ET.fromstring(f"<root>{player_so_text}</root>")

            interaction_node = root.find(".//interaction")

            if interaction_node is not None and interaction_node.text and len(interaction_node.text) > 0:
                graph_version = json.loads(interaction_node.text)["graph_version"]
                edge_info_api = f"https://api.bilibili.com/x/stein/edgeinfo_v2?graph_version={graph_version}&bvid={bvid}"
                edge_info_raw = await get_web_source(edge_info_api)
                edge_info_data = json.loads(edge_info_raw)["data"]
                questions = edge_info_data["edges"]["questions"]
                index = 2  # 互动视频分P索引从2开始
                for question in questions:
                    choices = question["choices"]
                    for choice in choices:
                        p = Page(
                            index=index,
                            aid=id,
                            cid=str(choice["cid"]),
                            epid="",
                            title=choice["option"].strip(),
                            dur=0,
                            res="",
                            pub_time=pub_time,
                            cover="",
                            desc="",
                            owner_name=owner_name,
                            owner_mid=owner_mid,
                        )
                        pages_info.append(p)
                        index += 1
            else:
                raise Exception("互动视频获取分P信息失败")

        try:
            redirect_url = data.get("redirect_url", "")
            if redirect_url and "bangumi" in redirect_url:
                bangumi = True
                m = _EP_ID_RE.search(redirect_url)
                if m:
                    ep_id = m.group(1)
                    # 番剧内容通常不会有分P，如果有分P则不需要epId参数
                    if len(pages) == 1:
                        for p in pages_info:
                            p.epid = ep_id
        except Exception:
            pass

        return VInfo(
            title=title.strip(),
            desc=desc.strip(),
            pic=pic,
            pub_time=pub_time,
            pages_info=pages_info,
            is_bangumi=bangumi,
            is_stein_gate=is_stein_gate == 1,
        )
