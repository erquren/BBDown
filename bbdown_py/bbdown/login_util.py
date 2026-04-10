"""Login utilities ported from C# BBDownLoginUtil.cs."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import random
import string
import sys
import time
from datetime import datetime
from typing import Optional
from urllib.parse import parse_qs, urlparse

import httpx

from bbdown.core import config
from bbdown.core.logger import log, log_color, log_error

try:
    import qrcode
except ImportError:  # pragma: no cover
    qrcode = None  # type: ignore[assignment]


# --------------------------------------------------------------------------- #
#  QR code helpers                                                             #
# --------------------------------------------------------------------------- #

def _print_qrcode(url: str) -> None:
    """Print a QR code to the terminal using the qrcode library."""
    if qrcode is None:
        log("qrcode库不可用, 无法在终端显示二维码, 请扫描 qrcode.png")
        return
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_Q)
    qr.add_data(url)
    qr.make(fit=True)
    # Print using Unicode block characters (like the C# ConsoleQRCode)
    matrix = qr.get_matrix()
    for row in matrix:
        line = ""
        for cell in row:
            line += "██" if cell else "  "
        print(line)


def _save_qrcode_png(url: str) -> None:
    """Save a QR code as PNG image."""
    if qrcode is None:
        return
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_Q)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img.save("qrcode.png")


# --------------------------------------------------------------------------- #
#  URL query string helpers                                                    #
# --------------------------------------------------------------------------- #

def _get_query_string(name: str, url: str) -> str:
    """Extract a query parameter from a URL."""
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    values = params.get(name, [])
    return values[0] if values else ""


# --------------------------------------------------------------------------- #
#  TV login helpers                                                            #
# --------------------------------------------------------------------------- #

def _get_random_string(length: int) -> str:
    chars = string.ascii_letters.replace("I", "").replace("O", "") + "_" + string.digits
    return "".join(random.choice(chars) for _ in range(length))


def _get_timestamp(seconds: bool = True) -> str:
    if seconds:
        return str(int(time.time()))
    return str(int(time.time() * 1000))


def _get_sign(params_str: str) -> str:
    to_encode = params_str + "59b43e04ad6965f34319062b478f83dd"
    return hashlib.md5(to_encode.encode("utf-8")).hexdigest()


def _to_query_string(params: dict[str, str]) -> str:
    from urllib.parse import urlencode
    return urlencode(params)


def _get_tv_login_params() -> dict[str, str]:
    now = datetime.now()
    device_id = _get_random_string(20)
    buvid = _get_random_string(37)
    fingerprint = now.strftime("%Y%m%d%H%M%S%f")[:17] + _get_random_string(45)

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
    params["ts"] = _get_timestamp(True)
    params["sign"] = _get_sign(_to_query_string(params))
    return params


# --------------------------------------------------------------------------- #
#  Login status polling                                                        #
# --------------------------------------------------------------------------- #

async def _get_login_status(qrcode_key: str) -> str:
    """Poll the web login status endpoint."""
    query_url = (
        f"https://passport.bilibili.com/x/passport-login/web/qrcode/poll"
        f"?qrcode_key={qrcode_key}&source=main-fe-header"
    )
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0), verify=False) as client:
        resp = await client.get(query_url)
        resp.raise_for_status()
        return resp.text


# --------------------------------------------------------------------------- #
#  Web QR code login                                                           #
# --------------------------------------------------------------------------- #

async def login_web(app_dir: str = ".") -> None:
    """Web QR code login flow."""
    try:
        log("获取登录地址...")
        login_url = "https://passport.bilibili.com/x/passport-login/web/qrcode/generate?source=main-fe-header"
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0), verify=False) as client:
            resp = await client.get(login_url)
            resp.raise_for_status()
            data = json.loads(resp.text)

        url = data["data"]["url"]
        qrcode_key = _get_query_string("qrcode_key", url)

        flag = False
        log("生成二维码...")
        _save_qrcode_png(url)
        log("生成二维码成功: qrcode.png, 请打开并扫描, 或扫描打印的二维码")
        _print_qrcode(url)

        while True:
            await asyncio.sleep(1)
            w = await _get_login_status(qrcode_key)
            result = json.loads(w)
            code = result["data"]["code"]

            if code == 86038:
                log_color("二维码已过期, 请重新执行登录指令.")
                break
            elif code == 86101:
                # Waiting for scan
                continue
            elif code == 86090:
                # Scanned, waiting for confirmation
                if not flag:
                    log("扫码成功, 请确认...")
                    flag = True
            else:
                cc = result["data"]["url"]
                sessdata = _get_query_string("SESSDATA", cc)
                log(f"登录成功: SESSDATA={sessdata}")
                # Export cookie, escape commas
                query_part = cc[cc.index("?") + 1:]
                cookie_data = query_part.replace("&", ";").replace(",", "%2C")
                cookie_path = os.path.join(app_dir, "BBDown.data")
                with open(cookie_path, "w", encoding="utf-8") as f:
                    f.write(cookie_data)
                if os.path.exists("qrcode.png"):
                    os.remove("qrcode.png")
                break
    except Exception as e:
        log_error(str(e))


# --------------------------------------------------------------------------- #
#  TV QR code login                                                            #
# --------------------------------------------------------------------------- #

async def login_tv(app_dir: str = ".") -> None:
    """TV QR code login flow."""
    try:
        login_url = "https://passport.snm0516.aisee.tv/x/passport-tv-login/qrcode/auth_code"
        poll_url = "https://passport.bilibili.com/x/passport-tv-login/qrcode/poll"
        params = _get_tv_login_params()

        log("获取登录地址...")
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0), verify=False) as client:
            resp = await client.post(login_url, data=params)
            resp.raise_for_status()
            web = resp.text

        data = json.loads(web)
        url = data["data"]["url"]
        auth_code = data["data"]["auth_code"]

        log("生成二维码...")
        _save_qrcode_png(url)
        log("生成二维码成功: qrcode.png, 请打开并扫描, 或扫描打印的二维码")
        _print_qrcode(url)

        params["auth_code"] = auth_code
        params["ts"] = _get_timestamp(True)
        if "sign" in params:
            del params["sign"]
        params["sign"] = _get_sign(_to_query_string(params))

        while True:
            await asyncio.sleep(1)
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0), verify=False) as client:
                resp = await client.post(poll_url, data=params)
                resp.raise_for_status()
                web = resp.text

            result = json.loads(web)
            code = str(result["code"])

            if code == "86038":
                log_color("二维码已过期, 请重新执行登录指令.")
                break
            elif code == "86039":
                # Waiting for scan
                continue
            else:
                access_token = result["data"]["access_token"]
                log(f"登录成功: AccessToken={access_token}")
                # Export cookie
                cookie_path = os.path.join(app_dir, "BBDownTV.data")
                with open(cookie_path, "w", encoding="utf-8") as f:
                    f.write(f"access_token={access_token}")
                if os.path.exists("qrcode.png"):
                    os.remove("qrcode.png")
                break
    except Exception as e:
        log_error(str(e))
