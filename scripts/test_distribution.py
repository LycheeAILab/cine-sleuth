#!/usr/bin/env python3
"""Validate Codex and WorkBuddy distribution contracts offline."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
VERSION = "2.0.0"
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
            "cine-sleuth/scripts/lab_auth.py",
            "cine-sleuth/scripts/lab_video.py",
            "cine-sleuth/scripts/assemble_evidence.py",
            "cine-sleuth/scripts/publish_result.py",
            "cine-sleuth/scripts/prepare_video_source.py",
            "cine-sleuth/scripts/build_visual_report.py",
            "cine-sleuth/scripts/douk_downloader/download.py",
            "cine-sleuth/scripts/douk_downloader/a_bogus.py",
            "cine-sleuth/scripts/douk_downloader/LICENSE",
            "cine-sleuth/scripts/douk_downloader/NOTICE.md",
            "cine-sleuth/requirements.txt",
            "cine-sleuth/references/visual-delivery.md",
            "cine-sleuth/references/multimodal-segment-prompt.md",
            "cine-sleuth/references/report-guide.md",
            "cine-sleuth/references/cloud-processing.md",
        }
        require(required <= names, f"WorkBuddy archive missing: {sorted(required - names)}")
        require(not any("agents/" in name for name in names), "WorkBuddy archive contains Codex metadata")
        require(not any("__pycache__" in name or name.endswith(".pyc") for name in names), "Archive contains cache files")
        skill = archive.read("cine-sleuth/SKILL.md").decode("utf-8")
        require("${CODEBUDDY_SKILL_DIR}" in skill, "WorkBuddy Skill directory variable missing")
        require(archive.read("cine-sleuth/VERSION").decode("utf-8").strip() == VERSION, "VERSION mismatch")
        require("LYCHEE_API_KEY" not in skill and "LYCHEE_MODEL" not in skill, "Skill still asks for provider credentials")
        require("video-generation prompt" in skill.lower(), "WorkBuddy Skill omits per-shot generation prompts")
        require("build_visual_report.py" in skill and "prepare_video_source.py" in skill,
                "WorkBuddy instructions omit 2.0 workflow steps")
        for name in names:
            if name.endswith("/") or name == "cine-sleuth/SKILL.md":
                continue
            canonical = ROOT / "plugins/cine-sleuth/skills" / name
            require(canonical.read_bytes() == archive.read(name), f"Canonical/WorkBuddy drift: {name}")
        prompt = archive.read("cine-sleuth/references/multimodal-segment-prompt.md").decode("utf-8")
        require('"video_generation_prompt"' in prompt, "Evidence schema omits per-shot generation prompts")
        require('"media_fingerprint"' in prompt, "Evidence schema omits media visibility verification")
        provider_name = "gemi" + "ni"
        require(provider_name not in skill.lower(), "WorkBuddy Skill exposes an underlying provider name")

    public_guidance = "\n".join(
        (ROOT / name).read_text(encoding="utf-8")
        for name in ("README.md", "INSTALL.md", "WORKBUDDY_INSTALL.md")
    )
    require(provider_name not in public_guidance.lower(), "Installation guidance exposes an underlying provider name")
    prepare_source = (ROOT / "plugins/cine-sleuth/skills/cine-sleuth/scripts/prepare_video.py").read_text(encoding="utf-8")
    require("duration > 300.0" in prepare_source, "Five-minute source duration limit is missing")

    print("Distribution OK: Codex Plugin plus self-contained WorkBuddy Skill package.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
