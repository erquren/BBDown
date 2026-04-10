"""Global configuration ported from C# Config.cs."""

# For WEB
COOKIE: str = ""
# For APP/TV
TOKEN: str = ""
# Log level
DEBUG_LOG: bool = False
# BiliPlus Host
HOST: str = "api.bilibili.com"
# BiliPlus EP Host
EPHOST: str = "api.bilibili.com"
# Bili Tv Api Host
TVHOST: str = "api.snm0516.aisee.tv"
# BiliPlus Area
AREA: str = ""

WBI: str = ""

QUALITYS: dict[str, str] = {
    "127": "8K 超高清",
    "126": "杜比视界",
    "125": "HDR 真彩",
    "120": "4K 超清",
    "116": "1080P 高帧率",
    "112": "1080P 高码率",
    "100": "智能修复",
    "80": "1080P 高清",
    "74": "720P 高帧率",
    "64": "720P 高清",
    "48": "720P 高清",
    "32": "480P 清晰",
    "16": "360P 流畅",
    "5": "144P 流畅",
    "6": "240P 流畅",
}
