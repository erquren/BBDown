"""Aria2c download helper, ported from C# BBDownAria2c.cs."""

from __future__ import annotations

import asyncio
import os

from bbdown.core import config

ARIA2C: str = "aria2c"


async def run_command(command: str, args: str) -> int:
    """Run an external command and return its exit code."""
    proc = await asyncio.create_subprocess_exec(
        command, *args.split(),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.wait()
    return proc.returncode or 0


async def download_file_by_aria2c(url: str, path: str, extra_args: str) -> None:
    """Download a file using aria2c."""
    header_args = ""
    if "platform=android_tv_yst" not in url and "platform=android" not in url:
        header_args += ' --header="Referer: https://www.bilibili.com"'
    header_args += ' --header="User-Agent: Mozilla/5.0"'
    header_args += f' --header="Cookie: {config.COOKIE}"'
    dirname = os.path.dirname(path)
    basename = os.path.basename(path)
    await run_command(
        ARIA2C,
        f'--auto-file-renaming=false --download-result=hide --allow-overwrite=true '
        f'--console-log-level=warn -x16 -s16 -j16 -k5M {header_args} {extra_args} '
        f'"{url}" -d "{dirname}" -o "{basename}"',
    )
