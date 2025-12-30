from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, cast


class MediaProbeError(RuntimeError):
    pass


def ffprobe(path: Path) -> dict[str, Any]:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise MediaProbeError(proc.stderr.strip() or "ffprobe_failed")
    try:
        return cast(dict[str, Any], json.loads(proc.stdout))
    except json.JSONDecodeError as e:
        raise MediaProbeError("ffprobe_invalid_json") from e
