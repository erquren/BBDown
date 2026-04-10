"""Command-line interface ported from C# CommandLineInvoker.cs using click."""

from __future__ import annotations

import asyncio
from typing import Callable, Awaitable

import click

from bbdown.my_option import MyOption


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("url")
# --- API mode options ---
@click.option("--use-tv-api", "-tv", is_flag=True, default=False,
              help="使用TV端解析模式")
@click.option("--use-app-api", "-app", is_flag=True, default=False,
              help="使用APP端解析模式")
@click.option("--use-intl-api", "-intl", is_flag=True, default=False,
              help="使用国际版(东南亚视频)解析模式")
# --- Muxing options ---
@click.option("--use-mp4box", is_flag=True, default=False,
              help="使用MP4Box来混流")
@click.option("--encoding-priority", "-e", type=str, default=None,
              help='视频及音频编码的选择优先级, 用逗号分割 例: "hevc,av1,avc,flac,eac3,m4a"')
@click.option("--dfn-priority", "-q", type=str, default=None,
              help='画质优先级,用逗号分隔 例: "8K 超高清, 1080P 高码率, HDR 真彩, 杜比视界"')
# --- Display / interaction ---
@click.option("--only-show-info", "-info", is_flag=True, default=False,
              help="仅解析而不进行下载")
@click.option("--hide-streams", "-hs", is_flag=True, default=False,
              help="不要显示所有可用音视频流")
@click.option("--interactive", "-ia", is_flag=True, default=False,
              help="交互式选择清晰度")
@click.option("--show-all", is_flag=True, default=False,
              help="展示所有分P标题")
# --- Download options ---
@click.option("--use-aria2c", "-aria2", is_flag=True, default=False,
              help="调用aria2c进行下载(你需要自行准备好二进制可执行文件)")
@click.option("--aria2c-args", type=str, default=None,
              help='调用aria2c的附加参数(默认参数包含"-x16 -s16 -j16 -k 5M", 使用时注意字符串转义)')
@click.option("--multi-thread/--no-multi-thread", "-mt/", default=True,
              help="使用多线程下载(默认开启)")
@click.option("--select-page", "-p", type=str, default=None,
              help="选择指定分p或分p范围: (-p 8 或 -p 1,2 或 -p 3-5 或 -p ALL 或 -p LAST)")
# --- Mux options ---
@click.option("--simply-mux", is_flag=True, default=False,
              help="精简混流，不增加描述、作者等信息")
# --- Download-only modes ---
@click.option("--audio-only", is_flag=True, default=False,
              help="仅下载音频")
@click.option("--video-only", is_flag=True, default=False,
              help="仅下载视频")
@click.option("--danmaku-only", is_flag=True, default=False,
              help="仅下载弹幕")
@click.option("--cover-only", is_flag=True, default=False,
              help="仅下载封面")
@click.option("--sub-only", is_flag=True, default=False,
              help="仅下载字幕")
# --- Debug ---
@click.option("--debug", is_flag=True, default=False,
              help="输出调试日志")
# --- Skip options ---
@click.option("--skip-mux", is_flag=True, default=False,
              help="跳过混流步骤")
@click.option("--skip-subtitle", is_flag=True, default=False,
              help="跳过字幕下载")
@click.option("--skip-cover", is_flag=True, default=False,
              help="跳过封面下载")
# --- Protocol ---
@click.option("--force-http/--no-force-http", default=True,
              help="下载音视频时强制使用HTTP协议替换HTTPS(默认开启)")
# --- Danmaku ---
@click.option("--download-danmaku", "-dd", is_flag=True, default=False,
              help="下载弹幕")
@click.option("--download-danmaku-formats", "-ddf", type=str, default=None,
              help="指定需下载的弹幕格式, 用逗号分隔, 可选 ass/xml/protobuf")
# --- AI subtitles ---
@click.option("--skip-ai/--no-skip-ai", default=True,
              help="跳过AI字幕下载(默认开启)")
# --- Sorting ---
@click.option("--video-ascending", is_flag=True, default=False,
              help="视频升序(最小体积优先)")
@click.option("--audio-ascending", is_flag=True, default=False,
              help="音频升序(最小体积优先)")
# --- Network ---
@click.option("--allow-pcdn", is_flag=True, default=False,
              help="不替换PCDN域名, 仅在正常情况与--upos-host均无法下载时使用")
@click.option("--language", type=str, default=None,
              help="设置混流的音频语言(代码), 如chi, jpn等")
@click.option("--user-agent", "-ua", type=str, default=None,
              help="指定user-agent, 否则使用随机user-agent")
@click.option("--cookie", "-c", type=str, default=None,
              help="设置字符串cookie用以下载网页接口的会员内容")
@click.option("--access-token", "-token", type=str, default=None,
              help="设置access_token用以下载TV/APP接口的会员内容")
# --- Paths ---
@click.option("--work-dir", type=str, default=None,
              help="设置程序的工作目录")
@click.option("--ffmpeg-path", type=str, default=None,
              help="设置ffmpeg的路径")
@click.option("--mp4box-path", type=str, default=None,
              help="设置mp4box的路径")
@click.option("--aria2c-path", type=str, default=None,
              help="设置aria2c的路径")
@click.option("--upos-host", type=str, default=None,
              help="自定义upos服务器")
# --- Host / replace ---
@click.option("--force-replace-host/--no-force-replace-host", default=True,
              help="强制替换下载服务器host(默认开启)")
@click.option("--save-archives-to-file", is_flag=True, default=False,
              help="将下载过的视频记录到本地文件中, 用于后续跳过下载同个视频")
@click.option("--delay-per-page", type=str, default=None,
              help="设置下载合集分P之间的下载间隔时间(单位: 秒, 默认无间隔)")
# --- File patterns ---
@click.option("--file-pattern", "-F", type=str, default=None,
              help="使用内置变量自定义单P存储文件名")
@click.option("--multi-file-pattern", "-M", type=str, default=None,
              help="使用内置变量自定义多P存储文件名")
# --- BiliPlus ---
@click.option("--host", type=str, default=None,
              help="指定BiliPlus host")
@click.option("--ep-host", type=str, default=None,
              help="指定BiliPlus EP host")
@click.option("--tv-host", type=str, default=None,
              help="自定义tv端接口请求Host(用于代理api.snm0516.aisee.tv)")
@click.option("--area", type=str, default=None,
              help="(hk|tw|th) 使用BiliPlus时必选, 指定BiliPlus area")
# --- Config ---
@click.option("--config-file", type=str, default=None,
              help="读取指定的BBDown本地配置文件(默认为: BBDown.config)")
# --- Hidden legacy options ---
@click.option("--aria2c-proxy", type=str, default=None, hidden=True,
              help="调用aria2c进行下载时的代理地址配置")
@click.option("--only-hevc", "-hevc", is_flag=True, default=False, hidden=True,
              help="只下载hevc编码")
@click.option("--only-avc", "-avc", is_flag=True, default=False, hidden=True,
              help="只下载avc编码")
@click.option("--only-av1", "-av1", is_flag=True, default=False, hidden=True,
              help="只下载av1编码")
@click.option("--add-dfn-subfix", is_flag=True, default=False, hidden=True,
              help="为文件加入清晰度后缀, 如XXX[1080P 高码率]")
@click.option("--no-padding-page-num", is_flag=True, default=False, hidden=True,
              help="不给分P序号补零")
@click.option("--bandwith-ascending", is_flag=True, default=False, hidden=True,
              help="比特率升序(最小体积优先)")
@click.pass_context
def main(
    ctx: click.Context,
    url: str,
    use_tv_api: bool,
    use_app_api: bool,
    use_intl_api: bool,
    use_mp4box: bool,
    encoding_priority: str | None,
    dfn_priority: str | None,
    only_show_info: bool,
    hide_streams: bool,
    interactive: bool,
    show_all: bool,
    use_aria2c: bool,
    aria2c_args: str | None,
    multi_thread: bool,
    select_page: str | None,
    simply_mux: bool,
    audio_only: bool,
    video_only: bool,
    danmaku_only: bool,
    cover_only: bool,
    sub_only: bool,
    debug: bool,
    skip_mux: bool,
    skip_subtitle: bool,
    skip_cover: bool,
    force_http: bool,
    download_danmaku: bool,
    download_danmaku_formats: str | None,
    skip_ai: bool,
    video_ascending: bool,
    audio_ascending: bool,
    allow_pcdn: bool,
    language: str | None,
    user_agent: str | None,
    cookie: str | None,
    access_token: str | None,
    work_dir: str | None,
    ffmpeg_path: str | None,
    mp4box_path: str | None,
    aria2c_path: str | None,
    upos_host: str | None,
    force_replace_host: bool,
    save_archives_to_file: bool,
    delay_per_page: str | None,
    file_pattern: str | None,
    multi_file_pattern: str | None,
    host: str | None,
    ep_host: str | None,
    tv_host: str | None,
    area: str | None,
    config_file: str | None,
    aria2c_proxy: str | None,
    only_hevc: bool,
    only_avc: bool,
    only_av1: bool,
    add_dfn_subfix: bool,
    no_padding_page_num: bool,
    bandwith_ascending: bool,
) -> None:
    """BBDown是一个免费且便捷高效的哔哩哔哩下载/解析软件."""
    option = MyOption(
        url=url,
        use_tv_api=use_tv_api,
        use_app_api=use_app_api,
        use_intl_api=use_intl_api,
        use_mp4box=use_mp4box,
        encoding_priority=encoding_priority or None,
        dfn_priority=dfn_priority or None,
        only_show_info=only_show_info,
        show_all=show_all,
        use_aria2c=use_aria2c,
        interactive=interactive,
        hide_streams=hide_streams,
        multi_thread=multi_thread,
        simply_mux=simply_mux,
        video_only=video_only,
        audio_only=audio_only,
        danmaku_only=danmaku_only,
        cover_only=cover_only,
        sub_only=sub_only,
        debug=debug,
        skip_mux=skip_mux,
        skip_subtitle=skip_subtitle,
        skip_cover=skip_cover,
        force_http=force_http,
        download_danmaku=download_danmaku,
        download_danmaku_formats=download_danmaku_formats or None,
        skip_ai=skip_ai,
        video_ascending=video_ascending,
        audio_ascending=audio_ascending,
        allow_pcdn=allow_pcdn,
        force_replace_host=force_replace_host,
        save_archives_to_file=save_archives_to_file,
        file_pattern=file_pattern or "",
        multi_file_pattern=multi_file_pattern or "",
        select_page=select_page or "",
        language=language or "",
        user_agent=user_agent or "",
        cookie=cookie or "",
        access_token=access_token or "",
        aria2c_args=aria2c_args or "",
        work_dir=work_dir or "",
        ffmpeg_path=ffmpeg_path or "",
        mp4box_path=mp4box_path or "",
        aria2c_path=aria2c_path or "",
        upos_host=upos_host or "",
        delay_per_page=delay_per_page or "0",
        host=host or "api.bilibili.com",
        ep_host=ep_host or "api.bilibili.com",
        tv_host=tv_host or "api.snm0516.aisee.tv",
        area=area or "",
        config_file=config_file,
        # Legacy
        aria2c_proxy=aria2c_proxy or "",
        only_hevc=only_hevc,
        only_avc=only_avc,
        only_av1=only_av1,
        add_dfn_subfix=add_dfn_subfix,
        no_padding_page_num=no_padding_page_num,
        bandwith_ascending=bandwith_ascending,
    )

    action: Callable[[MyOption], Awaitable[None]] = ctx.obj["action"]
    asyncio.run(action(option))


def get_root_command(
    action: Callable[[MyOption], Awaitable[None]],
) -> click.Command:
    """Return the configured click command with the given *action* callback.

    The *action* is stored in ``ctx.obj`` and invoked by the ``main`` command
    handler.

    Usage::

        cmd = get_root_command(my_async_handler)
        cmd(standalone_mode=False, obj={"action": my_async_handler})
    """
    # Attach the action via click's obj mechanism; callers should invoke
    # main(standalone_mode=True/False, obj={"action": action})
    return main


# ---------------------------------------------------------------------------
#  Convenience: allow running ``python -m bbdown.cli`` for quick testing.
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    async def _noop(option: MyOption) -> None:
        print(option)

    main(standalone_mode=True, obj={"action": _noop})
