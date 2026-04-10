"""Logger functions ported from C# Logger.cs."""

import sys
from datetime import datetime

import bbdown.core.config as config

# ANSI color codes
_RED = "\033[31m"
_CYAN = "\033[36m"
_DARK_YELLOW = "\033[33m"
_DARK_GRAY = "\033[90m"
_RESET = "\033[0m"

_TIME_FMT = "%Y-%m-%d %H:%M:%S"
_PADDING = " " * 28


def _timestamp() -> str:
    now = datetime.now()
    return now.strftime(f"[{_TIME_FMT}.") + f"{now.microsecond // 1000:03d}]"


def log(text: object, enter: bool = True) -> None:
    sys.stdout.write(f"{_timestamp()} - {text}")
    if enter:
        sys.stdout.write("\n")
    sys.stdout.flush()


def log_error(text: object) -> None:
    sys.stdout.write(f"{_timestamp()} - {_RED}{text}{_RESET}\n")
    sys.stdout.flush()


def log_color(text: object, time: bool = True) -> None:
    if time:
        sys.stdout.write(f"{_timestamp()} - {_CYAN}{text}{_RESET}\n")
    else:
        sys.stdout.write(f"{_PADDING}{_CYAN}{text}{_RESET}\n")
    sys.stdout.flush()


def log_warn(text: object, time: bool = True) -> None:
    if time:
        sys.stdout.write(f"{_timestamp()} - {_DARK_YELLOW}{text}{_RESET}\n")
    else:
        sys.stdout.write(f"{_PADDING}{_DARK_YELLOW}{text}{_RESET}\n")
    sys.stdout.flush()


def log_debug(to_format: str, *args: object) -> None:
    if config.DEBUG_LOG:
        if args:
            msg = to_format.format(*args).strip()
        else:
            msg = to_format
        sys.stdout.write(f"{_DARK_GRAY}{_timestamp()} - {msg}{_RESET}\n")
        sys.stdout.flush()
