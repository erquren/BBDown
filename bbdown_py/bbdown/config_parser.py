"""Configuration file parser ported from C# BBDownConfigParser.cs."""

from __future__ import annotations

import os
from typing import List

from bbdown.core.logger import log, log_debug, log_error


def handle_config(args: list[str], app_dir: str) -> list[str]:
    """Load and merge a config file with command-line *args*.

    Config file values are only applied when the corresponding option is not
    already present on the command line (command-line takes priority).

    Parameters
    ----------
    args:
        The original command-line argument list.
    app_dir:
        The application directory used to locate the default config file.

    Returns
    -------
    list[str]
        The merged argument list.
    """
    try:
        # Determine config file path
        config_path: str | None = None
        if "--config-file" in args:
            idx = args.index("--config-file")
            if idx + 1 < len(args):
                config_path = args[idx + 1]
        if config_path is None:
            config_path = os.path.join(app_dir, "BBDown.config")

        if os.path.exists(config_path):
            log(f"加载配置文件: {config_path}")

            with open(config_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            config_args: list[str] = []
            for raw_line in lines:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("-") and " " in line:
                    space_idx = line.index(" ")
                    key = line[:space_idx].strip()
                    val = line[space_idx:].strip().strip('"')
                    if key:
                        config_args.append(key)
                    if val:
                        config_args.append(val)
                else:
                    config_args.append(line.strip('"'))

            # Merge: command-line args take priority
            new_args = list(args)
            i = 0
            while i < len(config_args):
                opt = config_args[i]
                if opt.startswith("-"):
                    # Check if option is already present in new_args
                    if opt not in new_args:
                        new_args.append(opt)
                        # If next token is a value (not another option), add it
                        if (
                            i + 1 < len(config_args)
                            and not config_args[i + 1].startswith("-")
                        ):
                            new_args.append(config_args[i + 1])
                            i += 1
                    else:
                        # Skip value if the option is already present
                        if (
                            i + 1 < len(config_args)
                            and not config_args[i + 1].startswith("-")
                        ):
                            i += 1
                else:
                    # Bare value (e.g. the URL argument) – only add if not
                    # already present
                    if opt not in new_args:
                        new_args.append(opt)
                i += 1

            log_debug("新的命令行参数: " + " ".join(new_args))
            return new_args
    except Exception:
        log_error("配置文件读取异常，忽略")

    return args
