"""Utility functions ported from C# BBDownUtil.cs."""

from __future__ import annotations

import hashlib
import json
import os
import random
import re
import shutil
import string
import subprocess
import time
from typing import List, Optional

from bbdown.core import config
from bbdown.core.logger import log, log_debug, log_error, log_warn, log_color
from bbdown.core.util.http_util import get_web_source, get_web_location
from bbdown.core.util.bv_converter import decode as bv_decode
from bbdown.core.entity.entity import ViewPoint

# Current version
VERSION = "0.1.0"

# ---------------------------------------------------------------------------
#  Regex patterns (ported from C# GeneratedRegex attributes)
# ---------------------------------------------------------------------------

_AV_RE = re.compile(r"av(\d+)")
_BV_RE = re.compile(r"[Bb][Vv]1(\w+)")
_EP_RE = re.compile(r"/ep(\d+)")
_SS_RE = re.compile(r"/ss(\d+)")
_UID_RE = re.compile(r"space\.bilibili\.com/(\d+)")
_GLOBAL_EP_RE = re.compile(r"\.bilibili\.tv/\w+/play/\d+/(\d+)")
_BANGUMI_MD_RE = re.compile(r"bangumi/media/(md\d+)")
_STATE_RE = re.compile(r"window\.__INITIAL_STATE__=([\s\S].*?);\(function\(\)")
_MD_RE = re.compile(r"md(\d+)")
_QUERY_RE = re.compile(r"(^|&)?(\w+)=([^&]+)(&|$)?")
_LIBAVUTIL_RE = re.compile(r"libavutil\s+(\d+)\. +(\d+)\.")

# TV API sign key
_APP_KEY = "59b43e04ad6965f34319062b478f83dd"

# WBI mixin key enc tab
_MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35,
    27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13,
]

# Characters considered invalid in filenames (matching C# InvalidChars)
_INVALID_CHARS = set(
    chr(c) for c in
    [34, 60, 62, 124] + list(range(0, 32)) + [58, 42, 63, 92, 47]
)

# Random string character set
_RANDOM_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_0123456789"


# ---------------------------------------------------------------------------
#  Public helper functions
# ---------------------------------------------------------------------------


async def check_update() -> None:
    """Check for new versions on GitHub. Log if a newer version exists."""
    try:
        redirect_url = await get_web_location(
            "https://github.com/nilaoda/BBDown/releases/latest"
        )
        latest_ver = redirect_url.replace(
            "https://github.com/nilaoda/BBDown/releases/tag/", ""
        )
        if VERSION != latest_ver and not latest_ver.startswith("https"):
            log_color(f"发现新版本：{latest_ver}")
    except Exception:
        pass


async def get_av_id(input_str: str) -> str:
    """Parse a URL or shorthand input into a normalised AV/EP/SS identifier.

    Handles all Bilibili URL formats including short links, video pages,
    cheese (paid courses), bangumi, collections, series, favourites, user
    spaces, and global (bilibili.tv) episode links.
    """
    avid = input_str

    if input_str.startswith("http"):
        # Follow b23.tv short-link redirects
        if "b23.tv" in input_str:
            tmp = await get_web_location(input_str)
            if tmp == input_str:
                raise Exception("无限重定向")
            input_str = tmp

        if "video/av" in input_str:
            m = _AV_RE.search(input_str)
            avid = m.group(1) if m else avid

        elif "video/bv" in input_str.lower():
            m = _BV_RE.search(input_str)
            avid = _get_aid_by_bv(m.group(1)) if m else avid

        elif "/cheese/" in input_str:
            ep_id = ""
            if "/ep" in input_str:
                m = _EP_RE.search(input_str)
                ep_id = m.group(1) if m else ""
            elif "/ss" in input_str:
                m = _SS_RE.search(input_str)
                ep_id = await _get_epid_by_ssid(m.group(1)) if m else ""
            avid = f"cheese:{ep_id}"

        elif "/ep" in input_str:
            m = _EP_RE.search(input_str)
            ep_id = m.group(1) if m else ""
            avid = f"ep:{ep_id}"

        elif "/ss" in input_str:
            m = _SS_RE.search(input_str)
            ep_id = await _get_ep_id_by_bangumi_ssid(m.group(1)) if m else ""
            avid = f"ep:{ep_id}"

        elif (
            "/medialist/" in input_str
            and "business_id=" in input_str
            and "business=space_collection" in input_str
        ):
            biz_id = get_query_string("business_id", input_str)
            avid = f"listBizId:{biz_id}"

        elif (
            "/medialist/" in input_str
            and "business_id=" in input_str
            and "business=space_series" in input_str
        ):
            biz_id = get_query_string("business_id", input_str)
            avid = f"seriesBizId:{biz_id}"

        elif "/channel/collectiondetail?sid=" in input_str:
            biz_id = get_query_string("sid", input_str)
            avid = f"listBizId:{biz_id}"

        elif "/channel/seriesdetail?sid=" in input_str:
            biz_id = get_query_string("sid", input_str)
            avid = f"seriesBizId:{biz_id}"

        elif "/space.bilibili.com/" in input_str and "/lists/" in input_str:
            list_type = get_query_string("type", input_str).lower()
            path_part = input_str.split("?")[0].split("#")[0]
            sid_part = path_part[path_part.rfind("/") + 1:]
            if list_type == "season":
                avid = f"listBizId:{sid_part}"
            elif list_type == "series":
                avid = f"seriesBizId:{sid_part}"
            else:
                # Unknown type – treat as collection
                avid = f"listBizId:{sid_part}"

        elif "/space.bilibili.com/" in input_str and "/favlist" in input_str:
            m = _UID_RE.search(input_str)
            mid = m.group(1) if m else ""
            fid = get_query_string("fid", input_str)
            avid = f"favId:{fid}:{mid}"

        elif "/space.bilibili.com/" in input_str:
            m = _UID_RE.search(input_str)
            mid = m.group(1) if m else ""
            avid = f"mid:{mid}"

        elif "ep_id=" in input_str:
            ep_id = get_query_string("ep_id", input_str)
            avid = f"ep:{ep_id}"

        elif _GLOBAL_EP_RE.search(input_str):
            m = _GLOBAL_EP_RE.search(input_str)
            ep_id = m.group(1) if m else ""
            avid = f"ep:{ep_id}"

        elif _BANGUMI_MD_RE.search(input_str):
            m = _BANGUMI_MD_RE.search(input_str)
            md_id = m.group(1) if m else ""
            ep_id = await _get_ep_id_by_md(md_id)
            avid = f"ep:{ep_id}"

        else:
            # Fallback: fetch page source and parse __INITIAL_STATE__
            web = await get_web_source(input_str)
            m = _STATE_RE.search(web)
            if m:
                state_json = json.loads(m.group(1))
                ep_id = str(state_json["epList"][0]["id"])
                avid = f"ep:{ep_id}"

    elif input_str.lower().startswith("bv"):
        avid = _get_aid_by_bv(input_str[3:])

    elif input_str.lower().startswith("av"):
        avid = input_str.lower()[2:]

    elif input_str.startswith("cheese/"):
        ep_id = ""
        if "/ep" in input_str:
            m = _EP_RE.search(input_str)
            ep_id = m.group(1) if m else ""
        elif "/ss" in input_str:
            m = _SS_RE.search(input_str)
            ep_id = await _get_epid_by_ssid(m.group(1)) if m else ""
        avid = f"cheese:{ep_id}"

    elif input_str.startswith("ep"):
        ep_id = input_str[2:]
        avid = f"ep:{ep_id}"

    elif input_str.startswith("ss"):
        ep_id = await _get_ep_id_by_bangumi_ssid(input_str[2:])
        avid = f"ep:{ep_id}"

    elif input_str.startswith("md"):
        m = _MD_RE.search(input_str)
        md_id = m.group(1) if m else ""
        ep_id = await _get_ep_id_by_md(md_id)
        avid = f"ep:{ep_id}"

    else:
        raise Exception("输入有误")

    return await _fix_avid(avid)


def format_file_size(size: float) -> str:
    """Format a byte count into a human-readable string."""
    if size < 0:
        raise ValueError("size must be >= 0")
    if size >= 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024 * 1024):.2f} GB"
    if size >= 1024 * 1024:
        return f"{size / (1024 * 1024):.2f} MB"
    if size >= 1024:
        return f"{size / 1024:.2f} KB"
    return f"{size} bytes"


def format_time(seconds: int, absolute: bool = False) -> str:
    """Format *seconds* into a time string.

    When *absolute* is True the output is ``HH:MM:SS``, otherwise
    ``Xh YYm ZZs`` (hours omitted when zero).
    """
    total_hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if absolute:
        return f"{total_hours:02d}:{minutes:02d}:{secs:02d}"
    if total_hours == 0:
        return f"{minutes:02d}m{secs:02d}s"
    return f"{total_hours}h{minutes:02d}m{secs:02d}s"


# ---------------------------------------------------------------------------
#  Private helpers – ID resolution
# ---------------------------------------------------------------------------


async def _fix_avid(avid: str) -> str:
    """If *avid* is a pure numeric AV id, check if it redirects to a bangumi
    episode and return ``ep:<epid>`` instead."""
    if not avid.isdigit():
        return avid
    api = f"https://www.bilibili.com/video/av{avid}/"
    location = await get_web_location(api)
    if "/ep" in location:
        m = _EP_RE.search(location)
        return f"ep:{m.group(1)}" if m else avid
    return avid


def _get_aid_by_bv(bv: str) -> str:
    """Convert a BV id (without the ``BV1`` prefix) to an AV id."""
    return str(bv_decode(bv))


async def _get_epid_by_ssid(ssid: str) -> str:
    """Get the first episode id from a paid-course (cheese) season id."""
    api = f"https://api.bilibili.com/pugv/view/web/season?season_id={ssid}"
    resp = await get_web_source(api)
    data = json.loads(resp)
    return str(data["data"]["episodes"][0]["id"])


async def _get_ep_id_by_bangumi_ssid(ss_id: str) -> str:
    """Get the first episode id from a bangumi season id."""
    api = f"https://{config.EPHOST}/pgc/view/web/season?season_id={ss_id}"
    resp = await get_web_source(api)
    data = json.loads(resp)
    return str(data["result"]["episodes"][0]["id"])


async def _get_ep_id_by_md(md_id: str) -> str:
    """Get the latest episode id from a media id (md...)."""
    # Strip leading 'md' if present
    numeric_id = md_id
    if md_id.startswith("md"):
        numeric_id = md_id[2:]
    api = f"https://api.bilibili.com/pgc/review/user?media_id={numeric_id}"
    resp = await get_web_source(api)
    data = json.loads(resp)
    return str(data["result"]["media"]["new_ep"]["id"])


# ---------------------------------------------------------------------------
#  File helpers
# ---------------------------------------------------------------------------


def combine_multiple_files(files: list[str], output_path: str) -> None:
    """Concatenate *files* into *output_path*.

    If only one file is given it is moved instead.
    """
    if not files:
        return
    if len(files) == 1:
        out_dir = os.path.dirname(output_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        shutil.move(files[0], output_path)
        return

    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    with open(output_path, "wb") as out_f:
        for path in files:
            if not path:
                continue
            with open(path, "rb") as in_f:
                shutil.copyfileobj(in_f, out_f)


def get_files(directory: str, ext: str) -> list[str]:
    """Return sorted list of files in *directory* matching *ext* (e.g. '.txt')."""
    result: list[str] = []
    if not os.path.isdir(directory):
        return result
    for entry in os.listdir(directory):
        full = os.path.join(directory, entry)
        if os.path.isfile(full) and os.path.splitext(entry)[1].upper() == ext.upper():
            result.append(full)
    result.sort()
    return result


def get_valid_filename(
    input_str: str, re_str: str = "_", filter_slash: bool = False
) -> str:
    """Remove characters that are invalid in filenames."""
    title = input_str
    for ch in _INVALID_CHARS:
        title = title.replace(ch, re_str)
    if filter_slash:
        title = title.replace("/", re_str).replace("\\", re_str)
    return title


def get_query_string(name: str, url: str) -> str:
    """Extract the value of query parameter *name* from *url*."""
    for m in _QUERY_RE.finditer(url):
        if m.group(2) == name:
            return m.group(3)
    return ""


# ---------------------------------------------------------------------------
#  Signing / auth helpers
# ---------------------------------------------------------------------------


def get_sign(params: str) -> str:
    """Return the MD5 signature for TV API requests."""
    to_encode = params + _APP_KEY
    return hashlib.md5(to_encode.encode("utf-8")).hexdigest()


def get_time_stamp(seconds: bool = True) -> str:
    """Return the current Unix timestamp as a string."""
    if seconds:
        return str(int(time.time()))
    return str(int(time.time() * 1000))


def get_random_string(length: int) -> str:
    """Generate a random alphanumeric string of *length* characters."""
    return "".join(random.choice(_RANDOM_CHARS) for _ in range(length))


def get_tv_login_params() -> dict[str, str]:
    """Generate the parameter dict for TV login QR-code requests."""
    now = time.strftime("%Y%m%d%H%M%S") + f"{int(time.time() * 1000) % 1000:03d}"
    device_id = get_random_string(20)
    buvid = get_random_string(37)
    fingerprint = now + get_random_string(45)

    params: dict[str, str] = {}
    params["appkey"] = "4409e2ce8ffd12b8"
    params["auth_code"] = ""
    params["bili_local_id"] = device_id
    params["build"] = "102801"
    params["buvid"] = buvid
    params["channel"] = "master"
    params["device"] = "OnePlus"
    params["device_id"] = device_id
    params["device_name"] = "OnePlus7TPro"
    params["device_platform"] = "Android10OnePlusHD1910"
    params["fingerprint"] = fingerprint
    params["guid"] = buvid
    params["local_fingerprint"] = fingerprint
    params["local_id"] = buvid
    params["mobi_app"] = "android_tv_yst"
    params["networkstate"] = "wifi"
    params["platform"] = "android"
    params["sys_ver"] = "29"
    params["ts"] = get_time_stamp(True)

    # Build query string and compute sign
    qs = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
    params["sign"] = get_sign(qs)
    return params


# ---------------------------------------------------------------------------
#  FFmpeg helpers
# ---------------------------------------------------------------------------


def check_ffmpeg_dovi() -> bool:
    """Return True if the installed ffmpeg supports Dolby Vision (libavutil >= 57.17)."""
    try:
        from bbdown.muxer import FFMPEG

        proc = subprocess.run(
            [FFMPEG, "-version"],
            capture_output=True,
            text=True,
        )
        info = proc.stdout + "\n" + proc.stderr
        m = _LIBAVUTIL_RE.search(info)
        if not m:
            return False
        major = int(m.group(1))
        minor = int(m.group(2))
        return (major == 57 and minor >= 17) or major > 57
    except Exception:
        return False


async def fetch_points(cid: str, aid: str) -> list[ViewPoint]:
    """Fetch chapter (view-point) info for a video."""
    points: list[ViewPoint] = []
    try:
        api = f"https://api.bilibili.com/x/player/wbi/v2?cid={cid}&aid={aid}"
        resp = await get_web_source(api)
        data = json.loads(resp)
        vp = data.get("data", {}).get("view_points")
        if vp:
            for pt in vp:
                points.append(
                    ViewPoint(
                        title=pt["content"],
                        start=int(pt["from"]),
                        end=int(pt["to"]),
                    )
                )
    except Exception:
        pass
    return points


def get_ffmpeg_meta_string(points: list[ViewPoint]) -> str:
    """Generate ffmpeg chapter metadata from *points*."""
    lines = [";FFMETADATA"]
    for p in points:
        time_base = 1000
        lines.append("[CHAPTER]")
        lines.append(f"TIMEBASE=1/{time_base}")
        lines.append(f"START={p.start * time_base}")
        lines.append(f"END={p.end * time_base}")
        lines.append(f"title={p.title}")
        lines.append("")
    return "\n".join(lines) + "\n"


def get_mp4box_meta_string(points: list[ViewPoint]) -> str:
    """Generate mp4box chapter metadata from *points*."""
    lines: list[str] = []
    for p in points:
        lines.append(f"{format_time(p.start, True)} {p.title}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
#  Miscellaneous
# ---------------------------------------------------------------------------


def find_executable(name: str) -> Optional[str]:
    """Locate an executable by *name* in CWD, APP_DIR, or PATH."""
    file_ext = ".exe" if os.name == "nt" else ""
    search_dirs = [os.getcwd()]
    # Also search in the directory where this package lives
    app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    search_dirs.append(app_dir)

    env_path = os.environ.get("PATH", "").split(os.pathsep)
    for d in search_dirs + env_path:
        candidate = os.path.join(d, name + file_ext)
        if os.path.isfile(candidate):
            return candidate
    return None


def r_sub_string(sub: str) -> str:
    """Extract the filename (without extension) from the last segment of a URL path."""
    sub = sub[sub.rfind("/") + 1:]
    return sub[: sub.rfind(".")]


def _get_mixin_key(orig: str) -> str:
    """Apply the WBI mixin-key enc-tab permutation to produce a 32-char key."""
    return "".join(orig[i] for i in _MIXIN_KEY_ENC_TAB)


async def check_login(cookie: str) -> bool:
    """Check login status via the nav API and extract the WBI signing key.

    Returns True if the user is logged in.
    """
    try:
        api = "https://api.bilibili.com/x/web-interface/nav"
        source = await get_web_source(api)
        data = json.loads(source)
        is_login = data["data"]["isLogin"]
        wbi_img = data["data"]["wbi_img"]
        img_key = r_sub_string(wbi_img["img_url"])
        sub_key = r_sub_string(wbi_img["sub_url"])
        config.WBI = _get_mixin_key(img_key + sub_key)
        log_debug("wbi: {0}", config.WBI)
        return bool(is_login)
    except Exception:
        return False
