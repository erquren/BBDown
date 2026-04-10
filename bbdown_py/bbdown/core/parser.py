"""Parser module - extracts video/audio tracks from Bilibili API responses."""

import hashlib
import json
import re
import time

from bbdown.core import config
from bbdown.core.logger import log, log_debug, log_warn
from bbdown.core.util.http_util import get_web_source
from bbdown.core.entity.entity import Video, Audio, ViewPoint, AudioMaterialInfo
from bbdown.core.entity.parsed_result import ParsedResult
from bbdown.core import app_helper


def wbi_sign(api: str) -> str:
    """Add WBI signature to API params."""
    md5_hash = hashlib.md5((api + config.WBI).encode('utf-8')).hexdigest()
    return f"{api}&w_rid={md5_hash}"


def _get_time_stamp(seconds: bool = True) -> str:
    """Get current timestamp."""
    ts = int(time.time()) if seconds else int(time.time() * 1000)
    return str(ts)


def _get_sign(params: str, is_bili_plus: bool) -> str:
    """Calculate API sign."""
    secret = "acd495b248ec528c2eed1e862d393126" if is_bili_plus else "59b43e04ad6965f34319062b478f83dd"
    return hashlib.md5((params + secret).encode('utf-8')).hexdigest()


def _get_video_codec(code: str) -> str:
    """Convert codec ID to name."""
    return {"13": "AV1", "12": "HEVC", "7": "AVC"}.get(code, "UNKNOWN")


def _get_max_qn() -> str:
    """Get maximum quality number."""
    return next(iter(config.QUALITYS.keys()))


_player_json_re = re.compile(r"window\.__playinfo__=([\s\S]*?)<\/script>")
_base_url_re = re.compile(r"http.*:\d+")


async def _get_play_json(encoding: str, aid_ori: str, aid: str, cid: str, ep_id: str,
                          tv_api: bool, intl: bool, app_api: bool, qn: str = "0") -> str:
    """Get play JSON from various APIs."""
    log_debug(f"aid={aid},cid={cid},epId={ep_id},tvApi={tv_api},IntlApi={intl},appApi={app_api},qn={qn}")

    if intl:
        return await _get_play_json_intl(aid, cid, ep_id, qn)

    cheese = aid_ori.startswith("cheese:")
    bangumi = cheese or aid_ori.startswith("ep:")
    log_debug(f"bangumi={bangumi},cheese={cheese}")

    if app_api:
        return await app_helper.do_req(aid, cid, ep_id, qn, bangumi, encoding, config.TOKEN)

    if tv_api:
        prefix = (f"{config.TVHOST}/pgc/player/api/playurltv" if bangumi
                  else f"{config.TVHOST}/x/tv/playurl")
    else:
        prefix = (f"{config.HOST}/pgc/player/web/v2/playurl" if bangumi
                  else "api.bilibili.com/x/player/wbi/playurl")
    prefix = f"https://{prefix}?"

    if tv_api:
        api_parts = []
        if config.TOKEN:
            api_parts.append(f"access_key={config.TOKEN}&")
        api_parts.append(f"appkey=4409e2ce8ffd12b8&build=106500&cid={cid}&device=android")
        if bangumi:
            api_parts.append(f"&ep_id={ep_id}&expire=0")
        api_parts.append(f"&fnval=4048&fnver=0&fourk=1&mid=0&mobi_app=android_tv_yst")
        api_parts.append(f"&object_id={aid}&platform=android&playurl_type=1&qn={qn}&ts={_get_time_stamp(True)}")
        api_builder = "".join(api_parts)
        api = f"{prefix}{api_builder}&sign={_get_sign(api_builder, False)}"
    else:
        api_parts = [f"support_multi_audio=true&from_client=BROWSER&avid={aid}&cid={cid}&fnval=4048&fnver=0&fourk=1"]
        if config.AREA:
            api_parts.append(f"&access_key={config.TOKEN}&area={config.AREA}")
        api_parts.append(f"&otype=json&qn={qn}")
        if bangumi:
            api_parts.append(f"&module=bangumi&ep_id={ep_id}&session=")
        if not config.COOKIE:
            api_parts.append("&try_look=1")
        api_parts.append(f"&wts={_get_time_stamp(True)}")
        api_builder = "".join(api_parts)
        api = prefix + (api_builder if bangumi else wbi_sign(api_builder))

    if cheese:
        api = api.replace("/pgc/", "/pugv/")

    web_json = await get_web_source(api)
    if "\"大会员专享限制\"" in web_json:
        log("此视频需要大会员，您大概率需要登录一个有大会员的账号才可以下载，尝试从网页源码解析")
        web_url = f"https://www.bilibili.com/bangumi/play/ep{ep_id}"
        web_source = await get_web_source(web_url)
        m = _player_json_re.search(web_source)
        if m:
            web_json = m.group(1)
    return web_json


async def _get_play_json_intl(aid: str, cid: str, ep_id: str, qn: str, code: str = "0") -> str:
    """Get play JSON from international API."""
    is_bili_plus = config.HOST != "api.bilibili.com"
    api = f"https://{config.HOST if is_bili_plus else 'api.biliintl.com'}/intl/gateway/v2/ogv/playurl?"

    params = []
    if config.TOKEN:
        params.append(f"access_key={config.TOKEN}&")
    params.append(f"aid={aid}")
    if is_bili_plus:
        area = config.AREA if config.AREA else "th"
        params.append(f"&appkey=7d089525d3611b1c&area={area}")
    params.append(f"&cid={cid}&ep_id={ep_id}&platform=android&prefer_code_type={code}&qn={qn}")
    if is_bili_plus:
        params.append(f"&ts={_get_time_stamp(True)}")
    params.append("&s_locale=zh_SG")
    param = "".join(params)
    if is_bili_plus:
        api += f"{param}&sign={_get_sign(param, True)}"
    else:
        api += param

    return await get_web_source(api)


async def extract_tracks(aid_ori: str, aid: str, cid: str, ep_id: str,
                         tv_api: bool, intl_api: bool, app_api: bool,
                         encoding: str, qn: str = "0") -> ParsedResult:
    """Extract video and audio tracks from API response."""
    intl_code = "0"
    result = ParsedResult()

    result.web_json_string = await _get_play_json(encoding, aid_ori, aid, cid, ep_id, tv_api, intl_api, app_api, qn)
    log_debug(result.web_json_string[:200] if result.web_json_string else "")

    # Parse JSON
    data = json.loads(result.web_json_string)

    # intl interface
    if "\"stream_list\"" in result.web_json_string:
        video_info = data["data"]["video_info"]
        p_dur = video_info["timelength"] // 1000
        audio_list = video_info.get("dash_audio", [])

        for stream in video_info.get("stream_list", []):
            dash_video = stream.get("dash_video")
            if dash_video and dash_video.get("base_url", ""):
                video_id = str(stream["stream_info"]["quality"])
                url_list = [dash_video["base_url"]] + dash_video.get("backup_url", [])
                v = Video(
                    dur=p_dur, id=video_id, dfn=config.QUALITYS.get(video_id, video_id),
                    bandwith=int(dash_video.get("bandwidth", 0)) // 1000,
                    base_url=next((u for u in url_list if not _base_url_re.search(u)), url_list[0]),
                    codecs=_get_video_codec(str(dash_video.get("codecid", ""))),
                    size=float(dash_video.get("size", 0))
                )
                if v not in result.video_tracks:
                    result.video_tracks.append(v)

        for node in audio_list:
            url_list = [node["base_url"]] + node.get("backup_url", [])
            a = Audio(
                id=str(node["id"]), dfn=str(node["id"]), dur=p_dur,
                bandwith=int(node.get("bandwidth", 0)) // 1000,
                base_url=next((u for u in url_list if not _base_url_re.search(u)), url_list[0]),
                codecs="M4A"
            )
            if a not in result.audio_tracks:
                result.audio_tracks.append(a)

        if intl_code == "0":
            intl_code = "1"
            result.web_json_string = await _get_play_json_intl(aid, cid, ep_id, qn, intl_code)
            data = json.loads(result.web_json_string)
            # Parse again for the second codec type
            video_info = data["data"]["video_info"]
            for stream in video_info.get("stream_list", []):
                dash_video = stream.get("dash_video")
                if dash_video and dash_video.get("base_url", ""):
                    video_id = str(stream["stream_info"]["quality"])
                    url_list = [dash_video["base_url"]] + dash_video.get("backup_url", [])
                    v = Video(
                        dur=p_dur, id=video_id, dfn=config.QUALITYS.get(video_id, video_id),
                        bandwith=int(dash_video.get("bandwidth", 0)) // 1000,
                        base_url=next((u for u in url_list if not _base_url_re.search(u)), url_list[0]),
                        codecs=_get_video_codec(str(dash_video.get("codecid", ""))),
                        size=float(dash_video.get("size", 0))
                    )
                    if v not in result.video_tracks:
                        result.video_tracks.append(v)

        return result

    # Determine data node
    node_name = None
    if '"result":{' in result.web_json_string:
        node_name = "result"
        if '"video_info":{' in result.web_json_string:
            node_name = "video_info"
    elif '"data":{' in result.web_json_string:
        node_name = "data"

    if node_name is None:
        root = data
    elif node_name == "video_info":
        root = data["result"]["video_info"]
    else:
        root = data[node_name]

    bangumi = aid_ori.startswith("ep:")

    if '"dash":{' in result.web_json_string:  # DASH
        audio = None
        video = None
        background_audio = None
        role_audio = None
        p_dur = 0

        try:
            p_dur = root["dash"]["duration"]
        except (KeyError, TypeError):
            pass
        try:
            p_dur = root["timelength"] // 1000
        except (KeyError, TypeError):
            pass

        # Re-parse for higher quality
        re_parse = False
        for _pass in range(2):
            if re_parse:
                result.web_json_string = await _get_play_json(encoding, aid_ori, aid, cid, ep_id, tv_api, intl_api, app_api, _get_max_qn())
                data = json.loads(result.web_json_string)
                if node_name is None:
                    root = data
                elif node_name == "video_info":
                    root = data["result"]["video_info"]
                else:
                    root = data[node_name]

            try:
                video = root["dash"].get("video", [])
            except (KeyError, TypeError):
                video = None
            try:
                audio = root["dash"].get("audio", [])
            except (KeyError, TypeError):
                audio = None

            if app_api and bangumi:
                try:
                    background_audio = data.get("dubbing_info", {}).get("background_audio", [])
                except (KeyError, TypeError):
                    pass
                try:
                    role_audio = data.get("dubbing_info", {}).get("role_audio_list", [])
                except (KeyError, TypeError):
                    pass

            # Handle Dolby audio
            try:
                if audio is not None and not tv_api:
                    dolby = root["dash"].get("dolby")
                    if dolby and "audio" in dolby:
                        db = dolby["audio"]
                        if isinstance(db, list):
                            audio.extend(db)
                        elif isinstance(db, dict):
                            audio.append(db)
            except Exception:
                pass

            # Handle Hi-Res
            try:
                if audio is not None and not tv_api:
                    hi_res = root["dash"].get("flac")
                    if hi_res and "audio" in hi_res:
                        db = hi_res["audio"]
                        if db is not None:
                            if isinstance(db, dict):
                                audio.append(db)
                            elif isinstance(db, list):
                                audio.extend(db)
            except Exception:
                pass

            if video:
                for node in video:
                    url_list = [node["base_url"]]
                    backup = node.get("backup_url")
                    if backup and isinstance(backup, list):
                        url_list.extend(backup)
                    video_id = str(node["id"])
                    v = Video(
                        dur=p_dur, id=video_id,
                        dfn=config.QUALITYS.get(video_id, video_id),
                        bandwith=int(node.get("bandwidth", 0)) // 1000,
                        base_url=next((u for u in url_list if not _base_url_re.search(u)), url_list[0]),
                        codecs=_get_video_codec(str(node.get("codecid", ""))),
                        size=float(node.get("size", 0))
                    )
                    if not tv_api and not app_api:
                        v.res = f'{node.get("width", "")}x{node.get("height", "")}'
                        v.fps = str(node.get("frame_rate", ""))
                    if v not in result.video_tracks:
                        result.video_tracks.append(v)

            # Request higher quality on first pass (non-app)
            if not re_parse and not app_api:
                re_parse = True
            else:
                break

        if audio:
            for node in audio:
                url_list = [node["base_url"]]
                backup = node.get("backup_url")
                if backup and isinstance(backup, list):
                    url_list.extend(backup)
                audio_id = str(node["id"])
                codecs = node.get("codecs", "")
                codecs_map = {"mp4a.40.2": "M4A", "mp4a.40.5": "M4A", "ec-3": "E-AC-3", "fLaC": "FLAC"}
                codecs = codecs_map.get(codecs, codecs)
                result.audio_tracks.append(Audio(
                    id=audio_id, dfn=audio_id, dur=p_dur,
                    bandwith=int(node.get("bandwidth", 0)) // 1000,
                    base_url=next((u for u in url_list if not _base_url_re.search(u)), url_list[0]),
                    codecs=codecs
                ))

        if background_audio and role_audio:
            for node in background_audio:
                audio_id = str(node["id"])
                url_list = [node["base_url"]] + node.get("backup_url", [])
                result.background_audio_tracks.append(Audio(
                    id=audio_id, dfn=audio_id, dur=p_dur,
                    bandwith=int(node.get("bandwidth", 0)) // 1000,
                    base_url=next((u for u in url_list if not _base_url_re.search(u)), url_list[0]),
                    codecs=node.get("codecs", "")
                ))
            for role in role_audio:
                role_audio_tracks = []
                for node in role.get("audio", []):
                    audio_id = str(node["id"])
                    url_list = [node["base_url"]] + node.get("backup_url", [])
                    role_audio_tracks.append(Audio(
                        id=audio_id, dfn=audio_id, dur=p_dur,
                        bandwith=int(node.get("bandwidth", 0)) // 1000,
                        base_url=next((u for u in url_list if not _base_url_re.search(u)), url_list[0]),
                        codecs=node.get("codecs", "")
                    ))
                result.role_audio_list.append(AudioMaterialInfo(
                    title=role.get("title", ""),
                    person_name=role.get("person_name", ""),
                    path=f"{aid}/{aid}.{cid}.{role.get('audio_id', '')}.m4a",
                    audio=role_audio_tracks
                ))

    elif '"durl":[' in result.web_json_string:  # FLV
        result.web_json_string = await _get_play_json(encoding, aid_ori, aid, cid, ep_id, tv_api, intl_api, app_api, _get_max_qn())
        data = json.loads(result.web_json_string)
        if node_name is None:
            root = data
        elif node_name == "video_info":
            root = data["result"]["video_info"]
        else:
            root = data[node_name]

        quality = str(root["quality"])
        video_codecid = str(root["video_codecid"])
        size = 0.0
        length = 0.0

        for node in root["durl"]:
            result.clips.append(node["url"])
            size += float(node["size"])
            length += float(node["length"])

        # Available qualities
        if "qn_extras" in root:
            for node in root["qn_extras"]:
                result.dfns.append(str(node["qn"]))
        elif "accept_quality" in root:
            for node in root["accept_quality"]:
                qn_str = str(node)
                if qn_str:
                    result.dfns.append(qn_str)

        v = Video(
            id=quality, dfn=config.QUALITYS.get(quality, quality),
            base_url="", codecs=_get_video_codec(video_codecid),
            dur=int(length) // 1000, size=size
        )
        if v not in result.video_tracks:
            result.video_tracks.append(v)

    # Bangumi clip info -> segments
    if bangumi:
        clip_list = root.get("clip_info_list", [])
        if clip_list:
            for clip in clip_list:
                result.extra_points.append(ViewPoint(
                    title=clip.get("toastText", "").replace("即将跳过", ""),
                    start=clip.get("start", 0),
                    end=clip.get("end", 0)
                ))
            result.extra_points.sort(key=lambda p: p.start)
            new_points = []
            last_end = 0
            for point in result.extra_points:
                if last_end < point.start:
                    new_points.append(ViewPoint(title="正片", start=last_end, end=point.start))
                new_points.append(point)
                last_end = point.end
            result.extra_points = new_points

    return result
