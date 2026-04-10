"""ParsedResult dataclass ported from C# ParsedResult.cs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from bbdown.core.entity.entity import Video, Audio, AudioMaterialInfo, ViewPoint


@dataclass
class ParsedResult:
    web_json_string: str = ""
    video_tracks: List[Video] = field(default_factory=list)
    audio_tracks: List[Audio] = field(default_factory=list)
    background_audio_tracks: List[Audio] = field(default_factory=list)
    role_audio_list: List[AudioMaterialInfo] = field(default_factory=list)
    extra_points: List[ViewPoint] = field(default_factory=list)
    # ⬇⬇⬇⬇⬇ FOR FLV ⬇⬇⬇⬇⬇
    clips: List[str] = field(default_factory=list)
    dfns: List[str] = field(default_factory=list)
