"""Danmaku (bullet comment) utilities ported from C# DanmakuUtil.cs."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Optional

from bbdown.core.logger import log, log_debug

# ---------- constants ----------
MONITOR_WIDTH = 1920
MONITOR_HEIGHT = 1080
FONT_SIZE = 40
MOVE_SPEND_TIME = 8.00
TOP_SPEND_TIME = 4.00
PROTECT_LENGTH = 50

POS_MOVE = 1
POS_TOP = 2
POS_BOTTOM = 3


# ---------- helpers ----------
def _compute_time(second: float) -> str:
    """Format *second* to ``h:mm:ss.ff`` (e.g. ``0:01:23.45``)."""
    hour = int(second) // 3600
    minute = (int(second) - hour * 3600) // 60
    second -= hour * 3600 + minute * 60
    return f"{hour}:{minute:02d}:{second:05.2f}"


# ---------- DanmakuItem ----------
class DanmakuItem:
    """One danmaku entry parsed from the XML ``<d>`` element."""

    __slots__ = (
        "content",
        "start_time",
        "second",
        "end_time",
        "danmaku_mode",
        "font_size",
        "color",
        "timestamp",
    )

    def __init__(self, attrs: list[str], content: str) -> None:
        mode_str = attrs[1]
        if mode_str == "4":
            self.danmaku_mode = POS_BOTTOM
        elif mode_str == "5":
            self.danmaku_mode = POS_TOP
        else:
            self.danmaku_mode = POS_MOVE

        self.start_time = ""
        self.second: float = 0.0
        self.end_time = ""
        try:
            sec = float(attrs[0])
            self.second = sec
            self.start_time = _compute_time(sec)
            duration = MOVE_SPEND_TIME if self.danmaku_mode == POS_MOVE else TOP_SPEND_TIME
            self.end_time = _compute_time(sec + duration)
        except (ValueError, IndexError) as exc:
            log(str(exc))

        self.font_size = attrs[2]

        self.color = ""
        try:
            color_d = int(attrs[3])
            self.color = f"{color_d:06X}"
        except (ValueError, IndexError) as exc:
            log(str(exc))

        self.timestamp = attrs[4]
        self.content = content


# ---------- PositionController ----------
class PositionController:
    """Track available vertical positions for each danmaku type."""

    def __init__(self) -> None:
        self.max_line = MONITOR_HEIGHT * PROTECT_LENGTH // FONT_SIZE // 100
        self.move_queue: list[float] = [0.0] * self.max_line
        self.top_queue: list[float] = [0.0] * self.max_line
        self.bottom_queue: list[float] = [0.0] * self.max_line

    def update_position(self, mode: int, time: float, length: int) -> int:
        """Return the Y-pixel offset for the danmaku, or ``-1`` if no space."""
        if mode == POS_BOTTOM:
            queue = self.bottom_queue
        elif mode == POS_TOP:
            queue = self.top_queue
        else:
            queue = self.move_queue

        display_time = TOP_SPEND_TIME
        if mode not in (POS_TOP, POS_BOTTOM):
            display_time = MOVE_SPEND_TIME * (length + 5) * FONT_SIZE / (
                MONITOR_WIDTH + length * MOVE_SPEND_TIME
            )

        for i in range(self.max_line):
            if time >= queue[i]:
                queue[i] = time + display_time
                return i * FONT_SIZE
        return -1


# ---------- parse XML ----------
def parse_xml(xml_path: str) -> Optional[list[DanmakuItem]]:
    """Parse an XML danmaku file and return a list of :class:`DanmakuItem`."""
    try:
        tree = ET.parse(xml_path)
    except Exception as exc:
        log_debug(f"解析字幕xml时出现异常: {exc}")
        return None

    root = tree.getroot()
    if root.tag != "i":
        return None

    danmakus: list[DanmakuItem] = []
    for d_elem in root.findall("d"):
        attr = d_elem.get("p")
        if attr is None:
            continue
        parts = attr.split(",")
        if len(parts) >= 8:
            danmakus.append(DanmakuItem(parts, d_elem.text or ""))
    return danmakus


# ---------- save as ASS ----------
async def save_as_ass(danmakus: list[DanmakuItem], output_path: str) -> None:
    """Write danmaku list to an ASS subtitle file."""
    lines: list[str] = []

    # ASS header
    lines.append("[Script Info]")
    lines.append("Script Updated By: BBDown(https://github.com/nilaoda/BBDown)")
    lines.append("ScriptType: v4.00+")
    lines.append(f"PlayResX: {MONITOR_WIDTH}")
    lines.append(f"PlayResY: {MONITOR_HEIGHT}")
    lines.append(f"Aspect Ratio: {MONITOR_WIDTH}:{MONITOR_HEIGHT}")
    lines.append("Collisions: Normal")
    lines.append("WrapStyle: 2")
    lines.append("ScaledBorderAndShadow: yes")
    lines.append("YCbCr Matrix: TV.601")
    lines.append("[V4+ Styles]")
    lines.append(
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding"
    )
    lines.append(
        f"Style: BBDOWN_Style, 黑体, {FONT_SIZE}, &H00FFFFFF, &H00FFFFFF, "
        "&H00000000, &H00000000, 0, 0, 0, 0, 100, 100, 0.00, 0.00, 1, 2, 0, 7, 0, 0, 0, 0"
    )
    lines.append("[Events]")
    lines.append(
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"
    )

    controller = PositionController()
    danmakus.sort(key=lambda d: d.second)

    for danmaku in danmakus:
        height = controller.update_position(
            danmaku.danmaku_mode, danmaku.second, len(danmaku.content)
        )
        if height == -1:
            continue

        if danmaku.danmaku_mode == POS_BOTTOM:
            effect = (
                f"\\an8\\pos({MONITOR_WIDTH // 2}, "
                f"{MONITOR_HEIGHT - FONT_SIZE - height})"
            )
        elif danmaku.danmaku_mode == POS_TOP:
            effect = f"\\an8\\pos({MONITOR_WIDTH // 2}, {height})"
        else:
            effect = (
                f"\\move({MONITOR_WIDTH}, {height}, "
                f"{-len(danmaku.content) * FONT_SIZE}, {height})"
            )

        if danmaku.color != "FFFFFF":
            effect += f"\\c&{danmaku.color}&"

        lines.append(
            f"Dialogue: 2,{danmaku.start_time},{danmaku.end_time},"
            f"BBDOWN_Style,,0000,0000,0000,,{{{effect}}}{danmaku.content}"
        )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
