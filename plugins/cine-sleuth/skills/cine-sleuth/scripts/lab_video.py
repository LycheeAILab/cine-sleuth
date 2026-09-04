#!/usr/bin/env python3
"""Register, upload, and complete CineSleuth video-understanding tasks."""

from __future__ import annotations

import http.client
import json
import mimetypes
from pathlib import Path
from urllib.parse import urlsplit
import urllib.error
import urllib.request


def api_json(base_url: str, token: str, path: str, method: str = "GET", payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else (b"" if method == "POST" else None)
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "CineSleuth-Skill/1.0.3",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"LycheeAILab task API returned HTTP {exc.code}: {body[:600]}") from exc


def stream_put(url: str, source: Path, media_type: str, timeout: float = 900.0) -> None:
    target = urlsplit(url)
    if target.scheme != "https" or not target.hostname or not target.hostname.endswith(".myqcloud.com"):
        raise RuntimeError("LycheeAILab returned an invalid COS upload URL")
    connection = http.client.HTTPSConnection(target.hostname, target.port or 443, timeout=timeout)
    request_path = target.path + (f"?{target.query}" if target.query else "")
    try:
        connection.putrequest("PUT", request_path)
        connection.putheader("Content-Type", media_type)
        connection.putheader("Content-Length", str(source.stat().st_size))
        connection.endheaders()
        with source.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                connection.send(block)
        response = connection.getresponse()
        response.read()
        if not 200 <= response.status < 300:
            raise RuntimeError(f"COS upload returned HTTP {response.status}")
    finally:
        connection.close()


def write_manifest(path: Path, manifest: dict) -> None:
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def ensure_original_uploaded(manifest_path: Path, manifest: dict, token: str, base_url: str) -> str:
    source = Path(manifest["source"]["path"])
    if not source.is_file():
        raise RuntimeError(f"Original video is unavailable: {source}")
    task = manifest.get("lab_task") if isinstance(manifest.get("lab_task"), dict) else {}
    job_id = task.get("job_id")
    job = None
    if isinstance(job_id, str):
        try:
            job = api_json(base_url, token, f"/api/cine-sleuth/jobs/{job_id}")
        except RuntimeError as exc:
            if "HTTP 404" not in str(exc):
                raise
            job_id = None

    if not job_id:
        media_type = mimetypes.guess_type(source.name)[0] or "video/mp4"
        job = api_json(base_url, token, "/api/cine-sleuth/jobs", "POST", {
            "fileName": source.name,
            "mediaType": media_type,
            "sizeBytes": source.stat().st_size,
            "durationSeconds": manifest["source"].get("duration_seconds"),
            "checksumSha256": manifest["source"].get("sha256"),
            "clientRequestId": manifest.get("client_request_id"),
            "chunkCount": len(manifest["chunks"]),
        })
        job_id = job["jobId"]
        manifest["lab_task"] = {"job_id": job_id, "original_upload": "pending"}
        write_manifest(manifest_path, manifest)

    if job["originalVideo"]["status"] != "ready":
        upload = job.get("upload")
        if not upload or upload.get("method") != "PUT" or not upload.get("url"):
            raise RuntimeError("LycheeAILab did not provide a resumable original-video upload URL")
        stream_put(upload["url"], source, job["originalVideo"]["mediaType"])
        job = api_json(base_url, token, f"/api/cine-sleuth/jobs/{job_id}/upload-complete", "POST")
    manifest["lab_task"] = {"job_id": job_id, "original_upload": "ready", "status": job.get("status", "queued"), "reused": bool(job.get("reused"))}
    write_manifest(manifest_path, manifest)
    return job_id


def complete_task(base_url: str, token: str, job_id: str) -> dict:
    return api_json(base_url, token, f"/api/cine-sleuth/jobs/{job_id}/complete", "POST")


def result_metadata(base_url: str, token: str, job_id: str) -> dict:
    return api_json(base_url, token, f"/api/cine-sleuth/jobs/{job_id}/result")


def restore_result(base_url: str, token: str, job_id: str, output_dir: Path) -> list[str]:
    result = result_metadata(base_url, token, job_id)
    restored: list[str] = []
    names = {"cine_sleuth_report": "report.md", "cine_sleuth_evidence": "evidence.json"}
    for item in result.get("outputs", []):
        name = names.get(item.get("type"))
        target_url = item.get("url")
        if not name or not isinstance(target_url, str):
            continue
        parsed = urlsplit(target_url)
        if parsed.scheme != "https" or not parsed.hostname or not parsed.hostname.endswith(".myqcloud.com"):
            raise RuntimeError("LycheeAILab returned an invalid COS result URL")
        with urllib.request.urlopen(target_url, timeout=120) as response:
            (output_dir / name).write_bytes(response.read())
        restored.append(name)
    if set(restored) != set(names.values()):
        raise RuntimeError("Completed task does not contain both report.md and evidence.json")
    return restored
