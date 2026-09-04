#!/usr/bin/env python3
"""Publish the final CineSleuth Markdown report and structured evidence to LycheeAILab."""

from __future__ import annotations

import argparse
import json
import os
import random
import urllib.error
import urllib.request
from pathlib import Path

from lab_auth import DEFAULT_BASE_URL, authorized_token


def add_file(body: bytearray, boundary: str, field: str, path: Path, media_type: str) -> None:
    body.extend(f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"; filename="{path.name}"\r\nContent-Type: {media_type}\r\n\r\n'.encode("utf-8"))
    body.extend(path.read_bytes())
    body.extend(b"\r\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--base-url", default=os.environ.get("LYCHEE_LAB_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--force-login", action="store_true")
    args = parser.parse_args()

    manifest_path = args.manifest.expanduser().resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    job_id = (manifest.get("lab_task") or {}).get("job_id")
    if not isinstance(job_id, str):
        raise SystemExit("Manifest has no LycheeAILab job. Run analyze_chunks.py first.")
    report = args.report.expanduser().resolve()
    evidence = args.evidence.expanduser().resolve()
    if not report.is_file() or report.suffix.lower() != ".md":
        raise SystemExit("--report must point to a Markdown file")
    if not evidence.is_file() or evidence.suffix.lower() != ".json":
        raise SystemExit("--evidence must point to a JSON file")
    json.loads(evidence.read_text(encoding="utf-8"))

    token = authorized_token(args.base_url, args.force_login)
    boundary = f"----CineSleuthResult{random.getrandbits(96):024x}"
    body = bytearray()
    add_file(body, boundary, "report", report, "text/markdown; charset=utf-8")
    add_file(body, boundary, "evidence", evidence, "application/json; charset=utf-8")
    body.extend(f"--{boundary}--\r\n".encode("ascii"))
    request = urllib.request.Request(
        f"{args.base_url.rstrip('/')}/api/cine-sleuth/jobs/{job_id}/result",
        data=bytes(body),
        headers={"Authorization": f"Bearer {token}", "Content-Type": f"multipart/form-data; boundary={boundary}", "User-Agent": "CineSleuth-Skill/1.0.4"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"LycheeAILab result publishing returned HTTP {exc.code}: {detail[:600]}") from exc
    manifest["lab_task"]["status"] = result.get("status", "completed")
    temporary = manifest_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(manifest_path)
    print(json.dumps({"jobId": job_id, "status": result.get("status"), "outputs": [item.get("type") for item in result.get("outputs", [])]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
