#!/usr/bin/env python3
"""Validate Codex and WorkBuddy distribution contracts offline."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.1.0"
ARCHIVE = ROOT / "dist" / f"cine-sleuth-workbuddy-{VERSION}.zip"


def require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def main() -> int:
    marketplace = json.loads((ROOT / ".agents/plugins/marketplace.json").read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "plugins/cine-sleuth/.codex-plugin/plugin.json").read_text(encoding="utf-8"))
    require(marketplace["plugins"][0]["name"] == "cine-sleuth", "Marketplace plugin name mismatch")
    require(manifest["version"] == VERSION, "Codex manifest version mismatch")
    require(ARCHIVE.is_file(), "WorkBuddy archive has not been built")

    checksum_line = (ROOT / "dist/SHA256SUMS").read_text(encoding="utf-8").strip().split()
    require(checksum_line[0] == sha256(ARCHIVE.read_bytes()).hexdigest(), "WorkBuddy checksum mismatch")
    require(checksum_line[1] == ARCHIVE.name, "Checksum filename mismatch")

    with zipfile.ZipFile(ARCHIVE) as archive:
        names = set(archive.namelist())
        required = {
            "cine-sleuth/SKILL.md",
            "cine-sleuth/VERSION",
            "cine-sleuth/scripts/doctor.py",
            "cine-sleuth/scripts/prepare_video.py",
            "cine-sleuth/scripts/analyze_chunks.py",
            "cine-sleuth/scripts/assemble_evidence.py",
            "cine-sleuth/references/multimodal-segment-prompt.md",
            "cine-sleuth/references/report-guide.md",
        }
        require(required <= names, f"WorkBuddy archive missing: {sorted(required - names)}")
        require(not any("agents/" in name for name in names), "WorkBuddy archive contains Codex metadata")
        require(not any("__pycache__" in name or name.endswith(".pyc") for name in names), "Archive contains cache files")
        skill = archive.read("cine-sleuth/SKILL.md").decode("utf-8")
        require("${CODEBUDDY_SKILL_DIR}" in skill, "WorkBuddy Skill directory variable missing")
        require(archive.read("cine-sleuth/VERSION").decode("utf-8").strip() == VERSION, "VERSION mismatch")

    print("Distribution OK: Codex Plugin plus self-contained WorkBuddy Skill package.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

