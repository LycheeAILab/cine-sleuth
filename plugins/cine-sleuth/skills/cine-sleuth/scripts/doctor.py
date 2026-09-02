#!/usr/bin/env python3
"""Validate a CineSleuth installation without uploading media."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import sys

from lab_auth import DEFAULT_BASE_URL, load_token, validate_token


ROOT = Path(__file__).resolve().parents[1]
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()


def main() -> int:
    required = [
        ROOT / "SKILL.md",
        ROOT / "scripts" / "prepare_video.py",
        ROOT / "scripts" / "analyze_chunks.py",
        ROOT / "scripts" / "lab_auth.py",
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
    token = load_token()
    authenticated = bool(token and validate_token(token, os.environ.get("LYCHEE_LAB_BASE_URL", DEFAULT_BASE_URL)))
    installed = all(checks.values())
    result = {
        "version": VERSION,
        "installed": installed,
        "authenticated": authenticated,
        "runtime_ready": authenticated,
        "ok": installed,
        "checks": checks,
    }
    print(json.dumps(result, ensure_ascii=False))
    return 0 if installed else 1


if __name__ == "__main__":
    raise SystemExit(main())
