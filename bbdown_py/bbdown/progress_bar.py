"""Progress bar for download display, ported from C# ProgressBar.cs."""

from __future__ import annotations

import sys
import threading
import time
from typing import Optional


def _format_file_size(size: float) -> str:
    if size < 0:
        raise ValueError("size must be non-negative")
    if size >= 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024 * 1024):.2f} GB"
    if size >= 1024 * 1024:
        return f"{size / (1024 * 1024):.2f} MB"
    if size >= 1024:
        return f"{size / 1024:.2f} KB"
    return f"{size:.0f} bytes"


class ProgressBar:
    """A console progress bar with speed calculation and animation."""

    _BLOCK_COUNT = 40
    _ANIMATION = "|/-\\"
    _ANIMATION_INTERVAL = 1.0 / 8
    _SPEED_CALC_INTERVAL = 1.0

    def __init__(self, related_task: object | None = None) -> None:
        self._current_progress: float = 0.0
        self._current_text: str = ""
        self._disposed: bool = False
        self._animation_index: int = 0

        # Speed calculation state
        self._last_downloaded_bytes: int = 0
        self._downloaded_bytes: int = 0
        self._speed_string: str = ""

        self._related_task = related_task
        self._lock = threading.Lock()

        self._animation_timer: Optional[threading.Timer] = None
        self._speed_timer: Optional[threading.Timer] = None

        if not _is_output_redirected() or self._related_task is not None:
            self._reset_animation_timer()
            self._reset_speed_timer()

    # -- Public API --------------------------------------------------------- #

    def report(self, value: float, bytes_count: int = 0) -> None:
        """Update progress *value* (0..1) and optionally *bytes_count*."""
        value = max(0.0, min(1.0, value))
        with self._lock:
            self._current_progress = value
            if bytes_count:
                self._downloaded_bytes = bytes_count

    # -- Timer callbacks ---------------------------------------------------- #

    def _speed_timer_handler(self) -> None:
        with self._lock:
            if self._disposed:
                return
            if self._downloaded_bytes > 0 and self._downloaded_bytes - self._last_downloaded_bytes > 0:
                delta = self._downloaded_bytes - self._last_downloaded_bytes
                self._speed_string = " - " + _format_file_size(delta) + "/s"
                self._last_downloaded_bytes = self._downloaded_bytes
                if self._related_task is not None:
                    try:
                        self._related_task.download_speed = delta  # type: ignore[attr-defined]
                        self._related_task.total_downloaded_bytes += delta  # type: ignore[attr-defined]
                    except AttributeError:
                        pass
            self._reset_speed_timer()

    def _animation_timer_handler(self) -> None:
        with self._lock:
            if self._disposed:
                return
            progress_block_count = int(self._current_progress * self._BLOCK_COUNT)
            percent = self._current_progress * 100
            anim_char = self._ANIMATION[self._animation_index % len(self._ANIMATION)]
            self._animation_index += 1
            text = (
                f"                            "
                f"[{'#' * progress_block_count}{'-' * (self._BLOCK_COUNT - progress_block_count)}] "
                f"{percent:6.2f}% {anim_char}{self._speed_string}"
            )
            self._update_text(text)
            if self._related_task is not None:
                try:
                    self._related_task.progress = self._current_progress  # type: ignore[attr-defined]
                except AttributeError:
                    pass
            self._reset_animation_timer()

    # -- Internal helpers --------------------------------------------------- #

    def _update_text(self, text: str) -> None:
        if _is_output_redirected():
            return
        # Find common prefix length
        common_prefix_length = 0
        common_length = min(len(self._current_text), len(text))
        while common_prefix_length < common_length and text[common_prefix_length] == self._current_text[common_prefix_length]:
            common_prefix_length += 1
        # Backtrack to first differing character
        output = "\b" * (len(self._current_text) - common_prefix_length)
        # Output new suffix
        output += text[common_prefix_length:]
        # If new text is shorter, blank and backtrack overlap
        overlap_count = len(self._current_text) - len(text)
        if overlap_count > 0:
            output += " " * overlap_count
            output += "\b" * overlap_count
        sys.stdout.write(output)
        sys.stdout.flush()
        self._current_text = text

    def _reset_animation_timer(self) -> None:
        self._animation_timer = threading.Timer(self._ANIMATION_INTERVAL, self._animation_timer_handler)
        self._animation_timer.daemon = True
        self._animation_timer.start()

    def _reset_speed_timer(self) -> None:
        self._speed_timer = threading.Timer(self._SPEED_CALC_INTERVAL, self._speed_timer_handler)
        self._speed_timer.daemon = True
        self._speed_timer.start()

    # -- Context manager / cleanup ------------------------------------------ #

    def dispose(self) -> None:
        with self._lock:
            self._disposed = True
            self._update_text("")
        if self._animation_timer is not None:
            self._animation_timer.cancel()
        if self._speed_timer is not None:
            self._speed_timer.cancel()

    def __enter__(self) -> "ProgressBar":
        return self

    def __exit__(self, *_args: object) -> None:
        self.dispose()


def _is_output_redirected() -> bool:
    try:
        return not sys.stdout.isatty()
    except AttributeError:
        return True
