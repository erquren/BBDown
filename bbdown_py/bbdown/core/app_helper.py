"""gRPC-based App API helper, ported from C# AppHelper.cs.

Handles protobuf request construction, gRPC framing, header generation, and
conversion of PlayViewReply protobuf responses to JSON (matching the web API
structure so the parser can handle both uniformly).
"""

import base64
import gzip
import json
import struct
from typing import Any

from bbdown.core import config
from bbdown.core.logger import log_debug, log_warn
from bbdown.core.util.http_util import get_post_response
from bbdown.core.proto.payload.playviewreq_pb2 import PlayViewReq
from bbdown.core.proto.response.playviewreply_pb2 import PlayViewReply
from bbdown.core.proto.header.device_pb2 import Device
from bbdown.core.proto.header.fawkesreq_pb2 import FawkesReq
from bbdown.core.proto.header.locale_pb2 import Locale
from bbdown.core.proto.header.metadata_pb2 import Metadata as MetadataPb
from bbdown.core.proto.header.network_pb2 import Network

# ---------------------------------------------------------------------------
# Constants (mirror C# AppHelper statics)
# ---------------------------------------------------------------------------
API = "https://grpc.biliapi.net/bilibili.app.playurl.v1.PlayURL/PlayView"
API2 = "https://app.bilibili.com/bilibili.pgc.gateway.player.v2.PlayURL/PlayView"

_DALVIK_VER = "2.1.0"
_OS_VER = "11"
_BRAND = "M2012K11AC"
_MODEL = "Build/RKQ1.200826.002"
_APP_VER = "7.32.0"
_BUILD = 7320200  # newer build to get dubbing info
_CHANNEL = "xiaomi_cn_tv.danmaku.bili_zm20200902"
_NETWORK_TYPE = Network.TYPE.Value("WIFI")  # 1
_NETWORK_OID = "46007"
_CRONET = "1.36.1"
_BUVID = ""
_MOBI_APP = "android"
_APP_KEY = "android64"
_SESSION_ID = "dedf8669"
_PLATFORM = "android"
_ENV = "prod"
_APP_ID = 1
_REGION = "CN"
_LANGUAGE = "zh"


# ---------------------------------------------------------------------------
# Codec mapping
# ---------------------------------------------------------------------------

def _get_video_code_type(code: str) -> int:
    """Map encoding string to PlayViewReq.CodeType enum value."""
    mapping = {
        "AVC": PlayViewReq.CodeType.Value("CODE264"),
        "HEVC": PlayViewReq.CodeType.Value("CODE265"),
        "AV1": PlayViewReq.CodeType.Value("CODEAV1"),
    }
    return mapping.get(code, PlayViewReq.CodeType.Value("CODE265"))


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def do_req(aid: str, cid: str, ep_id: str, qn: str,
                 bangumi: bool, encoding: str, appkey: str = "") -> str:
    """Send gRPC request and return a JSON string (protobuf -> JSON)."""
    headers = _get_header(appkey)
    log_debug("App-Req-Headers: {}", json.dumps(headers, ensure_ascii=False))

    if bangumi:
        if encoding and encoding != "HEVC":
            log_warn("APP的番剧不支持 HEVC 以外的编码")
        body = _get_payload(int(ep_id), int(cid), int(qn),
                            PlayViewReq.CodeType.Value("CODE265"))
        data = await get_post_response(API2, body, headers)
    else:
        body = _get_payload(int(aid), int(cid), int(qn),
                            _get_video_code_type(encoding))
        data = await get_post_response(API, body, headers)

    resp = PlayViewReply()
    resp.ParseFromString(read_message(data))

    log_debug("PlayViewReplyPlain: {}", str(resp)[:500])
    return _convert_to_dash_json(resp)


# ---------------------------------------------------------------------------
# Convert protobuf to DASH-like JSON
# ---------------------------------------------------------------------------

def _convert_to_dash_json(resp: PlayViewReply) -> str:
    """Convert a PlayViewReply protobuf into the same JSON structure as the web API."""
    videos: list[dict[str, Any]] = []
    audios: list[dict[str, Any]] = []
    clips: list[dict[str, Any]] = []

    vi = resp.videoInfo
    timelength = vi.timelength
    duration_s = timelength // 1000 if timelength else 1

    # Video streams
    for item in vi.streamList:
        dv = item.dashVideo
        if dv and dv.baseUrl:
            bandwidth = int(dv.size * 8 // duration_s) if duration_s else 0
            videos.append({
                "id": item.streamInfo.quality,
                "base_url": dv.baseUrl,
                "backup_url": list(dv.backupUrl),
                "bandwidth": bandwidth,
                "codecid": dv.codecid,
            })

    # Audio streams
    for item in vi.dashAudio:
        audios.append({
            "id": item.id,
            "base_url": item.baseUrl,
            "backup_url": list(item.backupUrl),
            "bandwidth": item.bandwidth,
            "codecs": "M4A",
        })

    # Hi-Res (FLAC)
    if vi.HasField("flac") and vi.flac.HasField("audio"):
        fa = vi.flac.audio
        audios.append({
            "id": fa.id,
            "base_url": fa.baseUrl,
            "backup_url": list(fa.backupUrl),
            "bandwidth": fa.bandwidth,
            "codecs": "FLAC",
        })

    # Dolby
    if vi.HasField("dolby") and vi.dolby.HasField("audio"):
        da = vi.dolby.audio
        audios.append({
            "id": da.id,
            "base_url": da.baseUrl,
            "backup_url": list(da.backupUrl),
            "bandwidth": da.bandwidth,
            "codecs": "E-AC-3",
        })

    # Clip info (OP/ED markers)
    if resp.HasField("business"):
        for clip in resp.business.clipInfo:
            clips.append({
                "start": clip.start,
                "end": clip.end,
                "toastText": clip.toastText,
            })

    # Dubbing info
    background_audios: list[dict[str, Any]] = []
    roles: list[dict[str, Any]] = []

    if (resp.HasField("playExtInfo")
            and resp.playExtInfo.HasField("playDubbingInfo")
            and resp.playExtInfo.playDubbingInfo.HasField("backgroundAudio")):
        dub_info = resp.playExtInfo.playDubbingInfo

        for item in dub_info.backgroundAudio.audio:
            background_audios.append({
                "id": item.id,
                "base_url": item.baseUrl,
                "backup_url": list(item.backupUrl),
                "bandwidth": item.bandwidth,
                "codecs": "M4A",
            })

        for role_proto in dub_info.roleAudioList:
            for material in role_proto.audioMaterialList:
                role_audios: list[dict[str, Any]] = []
                for item in material.audio:
                    role_audios.append({
                        "id": item.id,
                        "base_url": item.baseUrl,
                        "backup_url": list(item.backupUrl),
                        "bandwidth": item.bandwidth,
                        "codecs": "M4A",
                    })
                roles.append({
                    "audio_id": material.audioId,
                    "title": material.title if material.title else material.audioId,
                    "person_name": material.personName if material.personName else (material.edition or ""),
                    "audio": role_audios,
                })

    result: dict[str, Any] = {
        "code": 0,
        "message": "0",
        "ttl": 1,
        "data": {
            "timelength": timelength,
            "dash": {
                "video": videos,
                "audio": audios,
            },
            "clip_info_list": clips,
        },
        "dubbing_info": {
            "background_audio": background_audios,
            "role_audio_list": roles,
        },
    }

    return json.dumps(result, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Payload construction
# ---------------------------------------------------------------------------

def _get_payload(aid: int, cid: int, qn: int, codec: int) -> bytes:
    """Build a gRPC-framed PlayViewReq payload."""
    req = PlayViewReq()
    req.epId = aid
    req.cid = cid
    req.qn = 127
    req.fnval = 4048
    req.fourk = True
    req.spmid = "main.ugc-video-detail.0.0"
    req.fromSpmid = "main.my-history.0.0"
    req.preferCodecType = codec
    req.download = 0   # 0: play, 1: flv download, 2: dash download
    req.forceHost = 2  # 0: allow IP, 1: http, 2: https

    log_debug("PayLoadPlain: {}", str(req)[:500])
    return pack_message(req.SerializeToString())


# ---------------------------------------------------------------------------
# Header generation
# ---------------------------------------------------------------------------

def _get_header(appkey: str) -> dict[str, str]:
    """Build gRPC request headers."""
    return {
        "Host": "grpc.biliapi.net",
        "user-agent": (
            f"Dalvik/{_DALVIK_VER} (Linux; U; Android {_OS_VER}; {_BRAND} {_MODEL}) "
            f"{_APP_VER} os/android model/{_BRAND} mobi_app/android build/{_BUILD} "
            f"channel/{_CHANNEL} innerVer/{_BUILD} osVer/{_OS_VER} network/2 "
            f"grpc-java-cronet/{_CRONET}"
        ),
        "te": "trailers",
        "x-bili-fawkes-req-bin": _generate_fawkes_req_bin(),
        "x-bili-metadata-bin": _generate_metadata_bin(appkey),
        "authorization": f"identify_v1 {config.TOKEN}",
        "x-bili-device-bin": _generate_device_bin(),
        "x-bili-network-bin": _generate_network_bin(),
        "x-bili-restriction-bin": "",
        "x-bili-locale-bin": _generate_locale_bin(),
        "x-bili-exps-bin": "",
        "grpc-encoding": "gzip",
        "grpc-accept-encoding": "identity,gzip",
        "grpc-timeout": "17996161u",
    }


def _generate_locale_bin() -> str:
    obj = Locale()
    locale_ids = Locale.LocaleIds()
    locale_ids.language = _LANGUAGE
    locale_ids.region = _REGION
    obj.cLocale.CopyFrom(locale_ids)
    return base64.b64encode(obj.SerializeToString()).decode()


def _generate_network_bin() -> str:
    obj = Network()
    obj.type = _NETWORK_TYPE
    obj.oid = _NETWORK_OID
    return base64.b64encode(obj.SerializeToString()).decode()


def _generate_device_bin() -> str:
    obj = Device()
    obj.appId = _APP_ID
    obj.build = _BUILD
    obj.buvid = _BUVID
    obj.mobiApp = _MOBI_APP
    obj.platform = _PLATFORM
    obj.channel = _CHANNEL
    obj.brand = _BRAND
    obj.model = _MODEL
    obj.osver = _OS_VER
    return base64.b64encode(obj.SerializeToString()).decode()


def _generate_metadata_bin(appkey: str) -> str:
    obj = MetadataPb()
    obj.accessKey = appkey
    obj.mobiApp = _MOBI_APP
    obj.build = _BUILD
    obj.channel = _CHANNEL
    obj.buvid = _BUVID
    obj.platform = _PLATFORM
    return base64.b64encode(obj.SerializeToString()).decode()


def _generate_fawkes_req_bin() -> str:
    obj = FawkesReq()
    obj.appkey = _APP_KEY
    obj.env = _ENV
    obj.sessionId = _SESSION_ID
    return base64.b64encode(obj.SerializeToString()).decode()


# ---------------------------------------------------------------------------
# gRPC message framing
# ---------------------------------------------------------------------------

def read_message(data: bytes) -> bytes:
    """Read a gRPC framed response: parse 5-byte header, decompress if needed."""
    flag = data[0]
    size = struct.unpack(">I", data[1:5])[0]
    if flag == 1:
        return _gzip_decompress(data[5:])
    return data[5: 5 + size]


def pack_message(data: bytes) -> bytes:
    """Add gRPC framing header: 1-byte compressed flag + 4-byte big-endian length + gzip body."""
    compressed = _gzip_compress(data)
    header = struct.pack(">BI", 1, len(compressed))
    return header + compressed


def _gzip_compress(data: bytes) -> bytes:
    return gzip.compress(data)


def _gzip_decompress(data: bytes) -> bytes:
    return gzip.decompress(data)
