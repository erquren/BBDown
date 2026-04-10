"""MyOption dataclass ported from C# MyOption.cs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class MyOption:
    url: str = ""
    use_tv_api: bool = False
    use_app_api: bool = False
    use_intl_api: bool = False
    use_mp4box: bool = False
    encoding_priority: Optional[str] = None
    dfn_priority: Optional[str] = None
    only_show_info: bool = False
    show_all: bool = False
    use_aria2c: bool = False
    interactive: bool = False
    hide_streams: bool = False
    multi_thread: bool = True
    simply_mux: bool = False
    video_only: bool = False
    audio_only: bool = False
    danmaku_only: bool = False
    cover_only: bool = False
    sub_only: bool = False
    debug: bool = False
    skip_mux: bool = False
    skip_subtitle: bool = False
    skip_cover: bool = False
    force_http: bool = True
    download_danmaku: bool = False
    download_danmaku_formats: Optional[str] = None
    skip_ai: bool = True
    video_ascending: bool = False
    audio_ascending: bool = False
    allow_pcdn: bool = False
    force_replace_host: bool = True
    save_archives_to_file: bool = False
    file_pattern: str = ""
    multi_file_pattern: str = ""
    select_page: str = ""
    language: str = ""
    user_agent: str = ""
    cookie: str = ""
    access_token: str = ""
    aria2c_args: str = ""
    work_dir: str = ""
    ffmpeg_path: str = ""
    mp4box_path: str = ""
    aria2c_path: str = ""
    upos_host: str = ""
    delay_per_page: str = "0"
    host: str = "api.bilibili.com"
    ep_host: str = "api.bilibili.com"
    tv_host: str = "api.snm0516.aisee.tv"
    area: str = ""
    config_file: Optional[str] = None
    # Legacy compatibility fields
    aria2c_proxy: str = ""
    only_hevc: bool = False
    only_avc: bool = False
    only_av1: bool = False
    add_dfn_subfix: bool = False
    no_padding_page_num: bool = False
    bandwith_ascending: bool = False
