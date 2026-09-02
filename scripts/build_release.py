#!/usr/bin/env python3
"""Build deterministic CineSleuth WorkBuddy release assets."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import shutil
import zipfile


ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "plugins" / "cine-sleuth" / "skills" / "cine-sleuth"
WORKBUDDY_SKILL = ROOT / "workbuddy" / "cine-sleuth" / "SKILL.md"
MANIFEST = ROOT / "plugins" / "cine-sleuth" / ".codex-plugin" / "plugin.json"
DIST = ROOT / "dist"
ZIP_TIMESTAMP = (2026, 9, 2, 0, 0, 0)


def copy_workbuddy_stage(stage: Path) -> None:
    target = stage / "cine-sleuth"
    shutil.copytree(
        CANONICAL,
        target,
        ignore=shutil.ignore_patterns("agents", "__pycache__", "test_*.py", "*.pyc"),
    )
    shutil.copy2(WORKBUDDY_SKILL, target / "SKILL.md")


def deterministic_zip(source: Path, output: Path) -> None:
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(source.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(source).as_posix()
            info = zipfile.ZipInfo(relative, ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default=None)
    args = parser.parse_args()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    version = args.version or manifest["version"]
    if version != manifest["version"]:
        raise SystemExit(f"version mismatch: requested {version}, manifest has {manifest['version']}")

    stage = DIST / "workbuddy-stage"
    if stage.exists():
        shutil.rmtree(stage)
    DIST.mkdir(exist_ok=True)
    copy_workbuddy_stage(stage)

    output = DIST / f"cine-sleuth-workbuddy-{version}.zip"
    if output.exists():
        output.unlink()
    deterministic_zip(stage, output)
    digest = sha256(output.read_bytes()).hexdigest()
    (DIST / "SHA256SUMS").write_text(f"{digest}  {output.name}\n", encoding="utf-8", newline="\n")
    print(output)
    print(f"sha256 {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

