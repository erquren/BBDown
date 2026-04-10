"""Enums ported from C# BBDownEnums.cs."""

from enum import Enum


class DanmakuFormat(Enum):
    XML = "xml"
    ASS = "ass"


DEFAULT_FORMATS = [DanmakuFormat.XML, DanmakuFormat.ASS]
ALL_FORMAT_NAMES = [f.value for f in DanmakuFormat]


def from_format_name(name: str) -> DanmakuFormat:
    lower = name.lower()
    if lower in ALL_FORMAT_NAMES:
        return DanmakuFormat(lower)
    return DanmakuFormat.XML
