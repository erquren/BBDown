"""Space video fetcher, ported from C# SpaceVideoFetcher.cs.

Fetches all videos from a user's space and writes the URLs to a text file.
"""

from __future__ import annotations

import json
import math
import os
import re
import time

from bbdown.core.entity.vinfo import VInfo
from bbdown.core.fetcher.ifetcher import IFetcher
from bbdown.core.logger import log
from bbdown.core.parser import wbi_sign
from bbdown.core.util.http_util import get_web_source

_INVALID_FNAME_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _get_valid_file_name(input_str: str, replacement: str = ".", filter_slash: bool = False) -> str:
    title = _INVALID_FNAME_RE.sub(replacement, input_str)
    if filter_slash:
        title = title.replace("/", replacement).replace("\\", replacement)
    return title


class SpaceVideoFetcher(IFetcher):

    async def fetch(self, id: str) -> VInfo:
        mid = id[4:]  # strip "mid:" prefix

        # Get user name from live API (bypasses w_rid)
        user_info_api = f"https://api.live.bilibili.com/live_user/v1/Master/info?uid={mid}"
        user_info_raw = await get_web_source(user_info_api)
        user_name = _get_valid_file_name(
            json.loads(user_info_raw)["data"]["info"]["uname"],
            ".",
            True,
        )

        urls: list[str] = []
        page_size = 50
        page_number = 1

        api_params = wbi_sign(
            f"mid={mid}&order=pubdate&pn={page_number}&ps={page_size}"
            f"&tid=0&wts={int(time.time())}"
        )
        api = f"https://api.bilibili.com/x/space/wbi/arc/search?{api_params}"
        raw = await get_web_source(api)
        info_json = json.loads(raw)

        for v in info_json["data"]["list"]["vlist"]:
            urls.append(f"https://www.bilibili.com/video/av{v['aid']}")

        total_count: int = info_json["data"]["page"]["count"]
        total_page = math.ceil(total_count / page_size)

        while page_number < total_page:
            page_number += 1
            urls.extend(await self._get_videos_by_page(page_number, page_size, mid))

        file_name = f"{user_name}的投稿视频.txt"
        with open(file_name, "w", encoding="utf-8") as f:
            f.write(os.linesep.join(urls))

        log("目前下载器不支持下载用户的全部投稿视频，不过程序已经获取到了该用户的全部投稿视频地址，"
            "你可以自行使用批处理脚本等手段调用本程序进行批量下载。如在Windows系统你可以使用如下代码：")
        print()
        print(
            '@echo Off\n'
            'For /F %%a in (urls.txt) Do (BBDown.exe "%%a")\n'
            'pause'
        )
        print()
        raise Exception("暂不支持该功能")

    @staticmethod
    async def _get_videos_by_page(page_number: int, page_size: int, mid: str) -> list[str]:
        urls: list[str] = []
        api_params = wbi_sign(
            f"mid={mid}&order=pubdate&pn={page_number}&ps={page_size}"
            f"&tid=0&wts={int(time.time())}"
        )
        api = f"https://api.bilibili.com/x/space/wbi/arc/search?{api_params}"
        raw = await get_web_source(api)
        info_json = json.loads(raw)
        for v in info_json["data"]["list"]["vlist"]:
            urls.append(f"https://www.bilibili.com/video/av{v['aid']}")
        return urls
