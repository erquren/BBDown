"""Download utilities ported from C# BBDownDownloadUtil.cs."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from typing import Callable, Optional, List

import httpx

from bbdown.core import config
from bbdown.core.entity.entity import Clip
from bbdown.core.logger import log_debug
from bbdown.progress_bar import ProgressBar
from bbdown import aria2c


@dataclass
class DownloadConfig:
    use_aria2c: bool = False
    aria2c_args: str = ""
    force_http: bool = False
    multi_thread: bool = False
    related_task: object | None = None


# --------------------------------------------------------------------------- #
#  Internal helpers                                                            #
# --------------------------------------------------------------------------- #

async def _range_download_to_tmp(
    id_: int,
    url: str,
    tmp_name: str,
    from_pos: int,
    to_pos: Optional[int],
    on_progress: Callable[[int, int, int], None],
    fail_on_range_not_supported: bool = False,
) -> None:
    """Download a byte range to a temporary file with resume support."""
    last_modified: Optional[str] = None
    if os.path.exists(tmp_name):
        import email.utils, datetime
        mtime = os.path.getmtime(tmp_name)
        last_modified = email.utils.formatdate(mtime, usegmt=True)

    mode = "ab" if os.path.exists(tmp_name) else "wb"
    file_pos: int = os.path.getsize(tmp_name) if os.path.exists(tmp_name) else 0

    if to_pos is not None and to_pos > 0 and file_pos == to_pos - from_pos + 1:
        # Already fully downloaded – report progress and skip
        on_progress(id_, file_pos, file_pos)
        return

    downloaded_bytes = from_pos + file_pos

    headers: dict[str, str] = {
        "User-Agent": "Mozilla/5.0",
        "Cookie": config.COOKIE,
    }
    if "platform=android_tv_yst" not in url and "platform=android" not in url:
        headers["Referer"] = "https://www.bilibili.com"
    headers["Range"] = f"bytes={downloaded_bytes}-" + (str(to_pos) if to_pos is not None else "")
    if last_modified is not None:
        headers["If-Range"] = last_modified

    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0), verify=False) as client:
        async with client.stream("GET", url, headers=headers) as response:
            response.raise_for_status()

            if response.status_code == 200:
                # Server doesn't support range requests
                if fail_on_range_not_supported and (downloaded_bytes > 0 or to_pos is not None):
                    raise NotImplementedError("Range request is not supported.")
                downloaded_bytes = 0
                file_pos = 0
                mode = "wb"

            content_length = response.headers.get("content-length")
            total_bytes = downloaded_bytes + (int(content_length) if content_length else (2**63 - 1 - downloaded_bytes))

            block_size = 1048576 // 4  # 256 KB

            with open(tmp_name, mode) as f:
                async for chunk in response.aiter_bytes(block_size):
                    if not chunk:
                        break
                    f.write(chunk)
                    f.flush()
                    downloaded_bytes += len(chunk)
                    on_progress(id_, downloaded_bytes - from_pos, total_bytes)

    # Verify downloaded size
    if content_length is not None and int(content_length) != os.path.getsize(tmp_name):
        raise Exception("Retry...")


async def download_file(url: str, path: str, config_: DownloadConfig) -> None:
    """Download a file with single-thread and retry support."""
    if not url:
        return
    if config_.force_http:
        url = _replace_url(url)
    log_debug("Start downloading: {}", url)

    des_dir = os.path.dirname(path)
    if des_dir and not os.path.exists(des_dir):
        os.makedirs(des_dir, exist_ok=True)

    if config_.use_aria2c:
        await aria2c.download_file_by_aria2c(url, path, config_.aria2c_args)
        if os.path.exists(path + ".aria2") or not os.path.exists(path):
            raise Exception("aria2下载可能存在错误")
        print()
        return

    retry = 0
    tmp_name = os.path.join(des_dir or ".", os.path.splitext(os.path.basename(path))[0] + ".tmp")
    while True:
        try:
            with ProgressBar(config_.related_task) as progress:
                await _range_download_to_tmp(
                    0, url, tmp_name, 0, None,
                    lambda _id, downloaded, total: progress.report(downloaded / total if total else 0, downloaded),
                )
            # Move tmp to final path
            if os.path.exists(path):
                os.remove(path)
            os.rename(tmp_name, path)
            return
        except Exception:
            retry += 1
            if retry == 3:
                raise


async def multi_thread_download_file(url: str, path: str, config_: DownloadConfig) -> None:
    """Download a file using multiple threads (asyncio.gather)."""
    if config_.force_http:
        url = _replace_url(url)
    log_debug("Start downloading: {}", url)

    if config_.use_aria2c:
        await aria2c.download_file_by_aria2c(url, path, config_.aria2c_args)
        if os.path.exists(path + ".aria2") or not os.path.exists(path):
            raise Exception("aria2下载可能存在错误")
        print()
        return

    file_size = await _get_file_size(url)
    log_debug("文件大小：{} bytes", file_size)

    # Already downloaded – skip
    if os.path.exists(path) and os.path.getsize(path) == file_size:
        log_debug("文件已下载过, 跳过下载")
        return

    all_clips = _get_all_clips(url, file_size)
    total = len(all_clips)
    log_debug("分段数量：{}", total)

    clip_progress: dict[int, int] = {c.index: 0 for c in all_clips}
    lock = asyncio.Lock()

    progress = ProgressBar(config_.related_task)
    progress.report(0)

    async def _download_clip(clip: Clip) -> None:
        retry = 0
        ext = ".vclip" if os.path.splitext(path)[1].endswith(".mp4") else ".aclip"
        tmp = os.path.join(
            os.path.dirname(path) or ".",
            f"{clip.index:05d}_{os.path.splitext(os.path.basename(path))[0]}{ext}",
        )

        while True:
            try:
                def _on_progress(index: int, downloaded: int, _total: int) -> None:
                    clip_progress[index] = downloaded
                    total_downloaded = sum(clip_progress.values())
                    progress.report(total_downloaded / file_size if file_size else 0, total_downloaded)

                await _range_download_to_tmp(
                    clip.index, url, tmp,
                    clip.from_pos,
                    None if clip.to_pos == -1 else clip.to_pos,
                    _on_progress,
                    True,
                )
                return
            except NotImplementedError:
                retry += 1
                if retry == 3:
                    raise Exception("服务器可能并不支持多线程下载, 请使用 --multi-thread false 关闭多线程")
            except Exception:
                retry += 1
                if retry == 3:
                    raise Exception(f"Failed to download clip {clip.index}")

    try:
        await asyncio.gather(*[_download_clip(clip) for clip in all_clips])
    finally:
        progress.dispose()


# --------------------------------------------------------------------------- #
#  Clip splitting logic                                                        #
# --------------------------------------------------------------------------- #

def _get_all_clips(url: str, file_size: int) -> List[Clip]:
    """Split a file into 20 MB clips for parallel downloading."""
    clips: List[Clip] = []
    index = 0
    counter = 0
    per_size = 20 * 1024 * 1024

    remaining = file_size
    while remaining > 0:
        c = Clip(index=index, from_pos=counter, to_pos=counter + per_size)
        if remaining - per_size > 0:
            remaining -= per_size
            counter += per_size + 1
            index += 1
            clips.append(c)
        else:
            c.to_pos = -1
            clips.append(c)
            break
    return clips


async def _get_file_size(url: str) -> int:
    """Send a streaming GET and read Content-Length to determine file size."""
    headers: dict[str, str] = {
        "User-Agent": "Mozilla/5.0",
        "Cookie": config.COOKIE,
    }
    if "platform=android_tv_yst" not in url and "platform=android" not in url:
        headers["Referer"] = "https://www.bilibili.com"

    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0), verify=False) as client:
        async with client.stream("GET", url, headers=headers) as response:
            response.raise_for_status()
            content_length = response.headers.get("content-length")
            return int(content_length) if content_length else 0


def _replace_url(url: str) -> str:
    """Force HTTPS URLs to HTTP, except for mcdn domains."""
    if ".mcdn.bilivideo.cn:" in url:
        log_debug("对[*.mcdn.bilivideo.cn:xxx]域名不做处理")
        return url
    log_debug("将https更改为http")
    return url.replace("https:", "http:")
