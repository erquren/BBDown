"""HTTP utility functions ported from C# HTTPUtil.cs."""

import httpx
import random

from bbdown.core import config
from bbdown.core.logger import log_debug

_platforms = [
    "Windows NT 10.0; Win64",
    "Macintosh; Intel Mac OS X 10_15",
    "X11; Linux x86_64",
]


def _random_version(min_v: int, max_v: int) -> str:
    version = random.uniform(min_v, max_v)
    return f"{version:.3f}"


def _get_random_user_agent() -> str:
    browsers = [
        f"AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{_random_version(80, 110)} Safari/537.36",
        f"Gecko/20100101 Firefox/{_random_version(80, 110)}",
    ]
    return f"Mozilla/5.0 ({random.choice(_platforms)}) {random.choice(browsers)}"


user_agent: str = _get_random_user_agent()

_client = httpx.AsyncClient(
    timeout=httpx.Timeout(120.0),
    follow_redirects=True,
    verify=False,
)


async def get_web_source(url: str, custom_user_agent: str | None = None) -> str:
    """Fetch a web page as text (GET request)."""
    headers: dict[str, str] = {
        "User-Agent": custom_user_agent or user_agent,
        "Accept-Encoding": "gzip, deflate",
        "Cookie": (
            (config.COOKIE + ";CURRENT_FNVAL=4048;")
            if ("/ep" in url or "/ss" in url)
            else config.COOKIE
        ),
        "Cache-Control": "no-cache",
    }
    if "api.bilibili.com" in url:
        headers["Referer"] = "https://www.bilibili.com/"
    if "api.bilibili.tv" in url:
        headers["sec-ch-ua"] = (
            '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"'
        )

    log_debug(f"获取网页内容: Url: {url}")
    resp = await _client.get(url, headers=headers)
    resp.raise_for_status()
    text = resp.text
    log_debug(f"Response: {text[:200]}...")
    return text


async def get_web_location(url: str) -> str:
    """Follow redirects and return the final URL (HEAD request)."""
    headers: dict[str, str] = {
        "User-Agent": user_agent,
        "Accept-Encoding": "gzip, deflate",
        "Cache-Control": "no-cache",
    }
    log_debug(f"获取网页重定向地址: Url: {url}")
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(120.0), follow_redirects=True, verify=False
    ) as client:
        resp = await client.head(url, headers=headers)
        resp.raise_for_status()
        location = str(resp.url)
        log_debug(f"Location: {location}")
        return location


async def get_post_response(
    url: str,
    post_data: bytes,
    headers: dict[str, str] | None = None,
) -> bytes:
    """Send a POST request with gRPC-style content and return raw bytes."""
    log_debug(f"Post to: {url}")
    if headers is None:
        headers = {
            "User-Agent": (
                "Dalvik/2.1.0 (Linux; U; Android 6.0.1; oneplus a5010 Build/V417IR) "
                "6.10.0 os/android model/oneplus a5010 mobi_app/android build/6100500 "
                "channel/bili innerVer/6100500 osVer/6.0.1 network/2"
            ),
            "grpc-encoding": "gzip",
        }
    headers["Content-Type"] = "application/grpc"
    resp = await _client.post(url, content=post_data, headers=headers)
    return resp.content
