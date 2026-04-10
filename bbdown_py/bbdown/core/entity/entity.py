"""Entity dataclasses ported from C# Entity.cs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List

from bbdown.core.util.bv_converter import encode as bv_encode


@dataclass
class ViewPoint:
    title: str
    start: int
    end: int


@dataclass
class Page:
    index: int
    aid: str
    cid: str
    epid: str
    title: str
    dur: int
    res: str
    pub_time: int
    cover: Optional[str] = None
    desc: Optional[str] = None
    owner_name: Optional[str] = None
    owner_mid: Optional[str] = None
    points: List[ViewPoint] = field(default_factory=list)

    @property
    def bvid(self) -> str:
        return bv_encode(int(self.aid))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Page):
            return NotImplemented
        return self.aid == other.aid and self.cid == other.cid and self.epid == other.epid

    def __hash__(self) -> int:
        return hash((self.aid, self.cid, self.epid))


@dataclass
class Video:
    id: str
    dfn: str
    base_url: str
    codecs: str
    bandwith: int
    dur: int
    res: Optional[str] = None
    fps: Optional[str] = None
    size: float = 0.0

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Video):
            return NotImplemented
        return (
            self.id == other.id
            and self.dfn == other.dfn
            and self.res == other.res
            and self.fps == other.fps
            and self.codecs == other.codecs
            and self.bandwith == other.bandwith
            and self.dur == other.dur
        )

    def __hash__(self) -> int:
        return hash((self.id, self.dfn, self.res, self.fps, self.codecs, self.bandwith, self.dur))


@dataclass
class Audio:
    id: str
    dfn: str
    base_url: str
    codecs: str
    bandwith: int
    dur: int

    @property
    def short_codecs(self) -> str:
        """E-AC-3 => EAC3"""
        return self.codecs.upper().replace("-", "")

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Audio):
            return NotImplemented
        return (
            self.id == other.id
            and self.dfn == other.dfn
            and self.codecs == other.codecs
            and self.bandwith == other.bandwith
            and self.dur == other.dur
        )

    def __hash__(self) -> int:
        return hash((self.id, self.dfn, self.codecs, self.bandwith, self.dur))


@dataclass
class Subtitle:
    lan: str
    url: str
    path: str


@dataclass
class Clip:
    index: int
    from_pos: int
    to_pos: int


@dataclass
class AudioMaterial:
    title: str
    person_name: str
    path: str

    @classmethod
    def from_info(cls, info: AudioMaterialInfo) -> AudioMaterial:
        return cls(title=info.title, person_name=info.person_name, path=info.path)


@dataclass
class AudioMaterialInfo:
    title: str
    person_name: str
    path: str
    audio: List[Audio] = field(default_factory=list)
