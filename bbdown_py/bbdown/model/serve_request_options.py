"""ServeRequestOptions ported from C# ServeRequestOptions.cs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from bbdown.my_option import MyOption


@dataclass
class ServeRequestOptions(MyOption):
    """Extends MyOption with a callback webhook for task completion."""
    callback_webhook: Optional[str] = None
