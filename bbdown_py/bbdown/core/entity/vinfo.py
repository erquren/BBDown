"""VInfo dataclass ported from C# VInfo.cs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List

from bbdown.core.entity.entity import Page


@dataclass
class VInfo:
    """Video information."""
    title: str
    desc: str
    pic: str
    pub_time: int
    is_bangumi: bool = False
    is_cheese: bool = False
    is_bangumi_end: bool = False
    index: Optional[str] = None
    pages_info: List[Page] = field(default_factory=list)
    is_stein_gate: bool = False
