#!/usr/bin/env python3
"""Validate a CineSleuth installation without uploading media."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import sys


ROOT = Path(__file__).resolve().parents[1]
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()


def main() -> int:
    required = [
        ROOT / "SKILL.md",
        ROOT / "scripts" / "prepare_video.py",
        ROOT / "scripts" / "analyze_chunks.py",
        ROOT / "scripts" / "assemble_evidence.py",
        ROOT / "references" / "multimodal-segment-prompt.md",
        ROOT / "references" / "report-guide.md",
    ]
    checks = {
        "python": sys.version_info >= (3, 9),
        "ffmpeg": shutil.which("ffmpeg") is not None,
        "ffprobe": shutil.which("ffprobe") is not None,
        "package_files": all(path.is_file() for path in required),
    }
    runtime = {
        "api_key_configured": bool(os.environ.get("LYCHEE_API_KEY")),
        "model_configured": bool(os.environ.get("LYCHEE_MODEL")),
    }
    result = {"version": VERSION, "ok": all(checks.values()), "checks": checks, "runtime": runtime}
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

