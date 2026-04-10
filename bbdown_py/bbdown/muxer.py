"""Muxer utilities ported from C# BBDownMuxer.cs."""

from __future__ import annotations

import asyncio
import os
import platform
import shutil
import subprocess
import sys
from typing import List, Optional

from bbdown.core import config
from bbdown.core.entity.entity import AudioMaterial, Subtitle, ViewPoint
from bbdown.core.logger import log, log_debug
from bbdown.core.util.sub_util import get_subtitle_code

FFMPEG: str = "ffmpeg"
MP4BOX: str = "mp4box"


# --------------------------------------------------------------------------- #
#  Helpers                                                                     #
# --------------------------------------------------------------------------- #

def _run_exe(app: str, params: str) -> int:
    """Run an external process, streaming stderr to the console. Returns 0."""
    proc = subprocess.Popen(
        [app] + params.split(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.stderr:
        for line in proc.stderr:
            line = line.rstrip()
            if line:
                log(line)
    proc.wait()
    return 0


def _escape_string(s: str) -> str:
    """Escape quotes and backslashes for metadata values."""
    if not s:
        return s
    return s.replace('"', "'").replace("\\", "\\\\")


def _format_time(seconds: int, absolute: bool = False) -> str:
    """Format *seconds* into a time string."""
    total_hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if absolute:
        return f"{total_hours:02d}:{minutes:02d}:{secs:02d}"
    if total_hours == 0:
        return f"{minutes:02d}m{secs:02d}s"
    return f"{total_hours}h{minutes:02d}m{secs:02d}s"


def _get_ffmpeg_meta_string(points: List[ViewPoint]) -> str:
    """Generate an ffmpeg chapter metadata file string."""
    lines: list[str] = [";FFMETADATA"]
    for p in points:
        time_base = 1000
        lines.append("[CHAPTER]")
        lines.append(f"TIMEBASE=1/{time_base}")
        lines.append(f"START={p.start * time_base}")
        lines.append(f"END={p.end * time_base}")
        lines.append(f"title={p.title}")
        lines.append("")
    return "\n".join(lines) + "\n"


def _get_mp4box_meta_string(points: List[ViewPoint]) -> str:
    """Generate an mp4box chapter metadata file string."""
    lines: list[str] = []
    for p in points:
        lines.append(f"{_format_time(p.start, True)} {p.title}")
    return "\n".join(lines) + "\n"


def _get_files(directory: str, ext: str) -> list[str]:
    """Get sorted list of files in *directory* with extension *ext*."""
    result = [
        os.path.join(directory, f)
        for f in os.listdir(directory)
        if f.upper().endswith(ext.upper())
    ]
    result.sort()
    return result


def _combine_multiple_files_into_single_file(files: list[str], output_path: str) -> None:
    """Concatenate binary files into a single output file."""
    if not files:
        return
    if len(files) == 1:
        shutil.move(files[0], output_path)
        return
    out_dir = os.path.dirname(output_path)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)
    with open(output_path, "wb") as out_f:
        for fp in files:
            with open(fp, "rb") as in_f:
                shutil.copyfileobj(in_f, out_f)


# --------------------------------------------------------------------------- #
#  MP4Box muxing                                                               #
# --------------------------------------------------------------------------- #

def _mux_by_mp4box(
    url: str,
    video_path: str,
    audio_path: str,
    out_path: str,
    desc: str,
    title: str,
    author: str,
    episode_id: str,
    pic: str,
    lang: str,
    subs: Optional[List[Subtitle]],
    audio_only: bool,
    video_only: bool,
    points: Optional[List[ViewPoint]],
) -> int:
    input_arg = " -inter 500 -noprog "
    meta_arg = ""
    now_id = 0

    if video_path:
        track_id = "2" if (audio_only and not audio_path) else "1"
        input_arg += f' -add "{video_path}#trackID={track_id}:name=" '
        now_id += 1

    if audio_path:
        lang_val = lang if lang else "und"
        input_arg += f' -add "{audio_path}:lang={lang_val}" '
        now_id += 1

    if points:
        meta = _get_mp4box_meta_string(points)
        base_path = video_path if video_path else audio_path
        meta_file = os.path.join(os.path.dirname(base_path) or ".", "chapters")
        with open(meta_file, "w", encoding="utf-8") as f:
            f.write(meta)
        input_arg += f' -chap  "{meta_file}"  '

    if pic:
        meta_arg += f':cover="{pic}"'
    if episode_id:
        meta_arg += f':album="{title}":title="{episode_id}"'
    else:
        meta_arg += f':title="{title}"'
    meta_arg += f':sdesc="{desc}"'
    meta_arg += f':comment="{url}"'
    meta_arg += f':artist="{author}"'

    if subs:
        for i, sub in enumerate(subs):
            if sub.path and os.path.exists(sub.path):
                with open(sub.path, "r", encoding="utf-8") as f:
                    content = f.read()
                if content:
                    now_id += 1
                    code, display = get_subtitle_code(sub.lan)
                    input_arg += f' -add "{sub.path}#trackID=1:name=:hdlr=sbtl:lang={code}" '
                    input_arg += f' -udta {now_id}:type=name:str="{display}" '

    verbose = " -v " if config.DEBUG_LOG else ""
    itags = "" if not meta_arg else " -itags tool=" + meta_arg
    arguments = f'{verbose}{input_arg}{itags} -new -- "{out_path}"'
    log_debug("mp4box命令: {}", arguments)
    return _run_exe(MP4BOX, arguments)


# --------------------------------------------------------------------------- #
#  Main mux function (ffmpeg)                                                  #
# --------------------------------------------------------------------------- #

def mux_av(
    use_mp4box: bool,
    bvid: str,
    video_path: str,
    audio_path: str,
    audio_material: List[AudioMaterial],
    out_path: str,
    desc: str = "",
    title: str = "",
    author: str = "",
    episode_id: str = "",
    pic: str = "",
    lang: str = "",
    subs: Optional[List[Subtitle]] = None,
    audio_only: bool = False,
    video_only: bool = False,
    points: Optional[List[ViewPoint]] = None,
    pub_time: int = 0,
    simply_mux: bool = False,
    is_hevc: bool = False,
) -> int:
    if audio_only and audio_path:
        video_path = ""
    if video_only:
        audio_path = ""
    desc = _escape_string(desc)
    title = _escape_string(title)
    episode_id = _escape_string(episode_id)
    url = f"https://www.bilibili.com/video/{bvid}/"

    if use_mp4box:
        return _mux_by_mp4box(
            url, video_path, audio_path, out_path, desc, title, author,
            episode_id, pic, lang, subs, audio_only, video_only, points,
        )

    out_dir = os.path.dirname(out_path)
    if "/" in out_path and out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    # Build -i arguments
    input_arg = ""
    meta_arg = ""
    input_count = 0

    for p in [video_path, audio_path]:
        if p:
            input_count += 1
            input_arg += f'-i "{p}" '

    if audio_material:
        audio_count = 0
        meta_arg += '-metadata:s:a:0 title="原音频" '
        for am in audio_material:
            input_count += 1
            audio_count += 1
            input_arg += f'-i "{am.path}" '
            if am.title and am.title.strip():
                meta_arg += f'-metadata:s:a:{audio_count} title="{am.title}" '
            if am.person_name and am.person_name.strip():
                meta_arg += f'-metadata:s:a:{audio_count} artist="{am.person_name}" '

    if pic:
        input_count += 1
        input_arg += f'-i "{pic}" '

    if subs:
        for i, sub in enumerate(subs):
            if sub.path and os.path.exists(sub.path):
                with open(sub.path, "r", encoding="utf-8") as f:
                    content = f.read()
                if content:
                    input_count += 1
                    input_arg += f'-i "{sub.path}" '
                    code, display = get_subtitle_code(sub.lan)
                    meta_arg += f'-metadata:s:s:{i} title="{display}" -metadata:s:s:{i} language={code} '

    if pic:
        vid_disp = "0" if audio_only else "1"
        meta_arg += f"-disposition:v:{vid_disp} attached_pic "

    if points:
        meta = _get_ffmpeg_meta_string(points)
        base_path = video_path if video_path else audio_path
        meta_file = os.path.join(os.path.dirname(base_path) or ".", "chapters")
        with open(meta_file, "w", encoding="utf-8") as f:
            f.write(meta)
        input_arg += f'-i "{meta_file}" -map_chapters {input_count} '

    input_arg += " ".join(f"-map {i}" for i in range(input_count)) + " "

    # Build final arguments
    log_level = "verbose" if config.DEBUG_LOG else "warning"
    args = f"-loglevel {log_level} -y "
    args += input_arg
    args += meta_arg
    if not simply_mux:
        effective_title = episode_id if episode_id else title
        args += f'-metadata title="{effective_title}" '
        args += f'-metadata comment="{url}" '
        if lang:
            args += f"-metadata:s:a:0 language={lang} "
        if desc and desc.strip():
            args += f'-metadata description="{desc}" '
        if author:
            args += f'-metadata artist="{author}" '
        if episode_id:
            args += f'-metadata album="{title}" '
        if pub_time != 0:
            from datetime import datetime, timezone
            creation_time = datetime.fromtimestamp(pub_time, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            args += f'-metadata creation_time="{creation_time}" '

    args += "-c:v copy -c:a copy "
    if audio_only and not audio_path:
        args += "-vn "
    if subs:
        args += "-c:s mov_text "
    # Fix macOS HEVC hvc1 tag
    if platform.system() == "Darwin" and is_hevc:
        args += "-tag:v:0 hvc1 "
    args += f'-movflags faststart -strict unofficial -strict -2 -f mp4 -- "{out_path}"'

    log_debug("ffmpeg命令: {}", args)
    return _run_exe(FFMPEG, args)


# --------------------------------------------------------------------------- #
#  FLV merging                                                                 #
# --------------------------------------------------------------------------- #

def merge_flv(files: list[str], out_path: str) -> None:
    """Merge multiple FLV files into a single output file."""
    if len(files) == 1:
        shutil.move(files[0], out_path)
    else:
        for file in files:
            dir_name = os.path.dirname(file) or "."
            tmp_file = os.path.join(dir_name, os.path.splitext(os.path.basename(file))[0] + ".ts")
            arguments = f'-loglevel warning -y -i "{file}" -map 0 -c copy -f mpegts -bsf:v h264_mp4toannexb "{tmp_file}"'
            log_debug("ffmpeg命令: {}", arguments)
            _run_exe("ffmpeg", arguments)
            os.remove(file)
        ts_files = _get_files(os.path.dirname(files[0]) or ".", ".ts")
        _combine_multiple_files_into_single_file(ts_files, out_path)
        for f in ts_files:
            os.remove(f)
