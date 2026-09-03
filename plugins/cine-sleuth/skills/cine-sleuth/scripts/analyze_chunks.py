#!/usr/bin/env python3
"""Send CineSleuth proxy chunks to a multimodal service and cache evidence."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import random
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from lab_auth import DEFAULT_BASE_URL, authorized_token
from lab_video import complete_task, ensure_original_uploaded


def render_prompt(template: str, manifest: dict, chunk: dict) -> str:
    values = {
        "CHUNK_ID": chunk["chunk_id"],
        "GLOBAL_OFFSET_SECONDS": chunk["source_start_seconds"],
        "CHUNK_DURATION_SECONDS": chunk["duration_seconds"],
        "TOTAL_DURATION_SECONDS": manifest["source"]["duration_seconds"],
        "OVERLAP_BEFORE_SECONDS": chunk["overlap_before_seconds"],
        "OVERLAP_AFTER_SECONDS": chunk["overlap_after_seconds"],
    }
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace("{{" + key + "}}", str(value))
    return rendered


def extract_prompt(markdown: str) -> str:
    match = re.search(r"```text\s*(.*?)\s*```", markdown, re.DOTALL)
    return match.group(1) if match else markdown


def extract_json_text(response: dict) -> str:
    try:
        parts = response["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"Analysis response contains no candidate: {json.dumps(response, ensure_ascii=False)[:1000]}") from exc
    text = "\n".join(part.get("text", "") for part in parts if isinstance(part, dict)).strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    if not text:
        raise RuntimeError("Analysis service returned an empty candidate.")
    return text


def request_chunk(
    token: str,
    base_url: str,
    job_id: str,
    chunk_key: str,
    prompt: str,
    video_path: Path,
    timeout: float,
) -> dict:
    boundary = f"----CineSleuth{random.getrandbits(96):024x}"
    video_data = video_path.read_bytes()
    body = bytearray()
    body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"jobId\"\r\n\r\n{job_id}\r\n".encode("utf-8"))
    body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"chunkKey\"\r\n\r\n{chunk_key}\r\n".encode("utf-8"))
    body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"prompt\"\r\n\r\n{prompt}\r\n".encode("utf-8"))
    body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"video\"; filename=\"{video_path.name}\"\r\nContent-Type: video/mp4\r\n\r\n".encode("utf-8"))
    body.extend(video_data)
    body.extend(f"\r\n--{boundary}--\r\n".encode("ascii"))
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/cine-sleuth/analyze",
        data=bytes(body),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": "CineSleuth-Skill/1.0.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        if exc.code == 409 and "still processing" in body:
            return wait_for_chunk(token, base_url, job_id, chunk_key, timeout)
        raise RuntimeError(f"Analysis service HTTP {exc.code}: {body[:1000]}") from exc
    if not body.strip():
        raise RuntimeError("Analysis service returned an empty HTTP response.")
    return json.loads(extract_json_text(json.loads(body)))


def wait_for_chunk(token: str, base_url: str, job_id: str, chunk_key: str, timeout: float) -> dict:
    deadline = time.monotonic() + timeout
    encoded_key = urllib.parse.quote(chunk_key, safe="")
    url = f"{base_url.rstrip('/')}/api/cine-sleuth/jobs/{job_id}/chunks/{encoded_key}"
    while time.monotonic() < deadline:
        request = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {token}", "User-Agent": "CineSleuth-Skill/1.0.0"},
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                state = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Analysis status HTTP {exc.code}: {body[:1000]}") from exc
        if state.get("status") == "completed" and isinstance(state.get("result"), dict):
            return state["result"]
        if state.get("status") == "failed":
            raise RuntimeError(f"Analysis service failed: {state.get('errorMessage') or 'unknown error'}")
        time.sleep(3.0)
    raise TimeoutError("Analysis is still processing on LycheeAILab; rerun the command to resume without resubmitting it.")


def analyze_one(
    manifest: dict,
    chunk: dict,
    prompt_template: str,
    results_dir: Path,
    token: str,
    base_url: str,
    job_id: str,
    retries: int,
    timeout: float,
    force: bool,
) -> dict:
    output = results_dir / f"{chunk['chunk_id']}.json"
    if output.exists() and not force:
        json.loads(output.read_text(encoding="utf-8"))
        return {"chunk_id": chunk["chunk_id"], "status": "cached", "output": str(output)}

    prompt = render_prompt(prompt_template, manifest, chunk)
    video_path = Path(chunk["path"])
    if not video_path.is_file():
        raise RuntimeError(f"Chunk file not found: {video_path}")

    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            evidence = request_chunk(token, base_url, job_id, chunk["chunk_id"], prompt, video_path, timeout)
            evidence.setdefault("_cine_sleuth", {})
            evidence["_cine_sleuth"].update(
                {
                    "chunk_id": chunk["chunk_id"],
                    "source_start_seconds": chunk["source_start_seconds"],
                    "source_end_seconds": chunk["source_end_seconds"],
                    "service": "lychee-video-understanding",
                }
            )
            temporary = output.with_suffix(".json.tmp")
            temporary.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
            temporary.replace(output)
            return {"chunk_id": chunk["chunk_id"], "status": "analyzed", "output": str(output)}
        except Exception as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(min(12.0, (2**attempt) + random.random()))
    raise RuntimeError(f"{chunk['chunk_id']} failed after {retries + 1} attempts: {last_error}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--results-dir", type=Path)
    parser.add_argument("--prompt", type=Path)
    parser.add_argument("--base-url", default=os.environ.get("LYCHEE_LAB_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--force-login", action="store_true")
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--timeout", type=float, default=360.0)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    token = authorized_token(args.base_url, args.force_login)
    manifest_path = args.manifest.expanduser().resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    job_id = ensure_original_uploaded(manifest_path, manifest, token, args.base_url)
    results_dir = (args.results_dir or manifest_path.parent / "results").expanduser().resolve()
    results_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = args.prompt or Path(__file__).resolve().parent.parent / "references" / "multimodal-segment-prompt.md"
    prompt_template = extract_prompt(prompt_path.read_text(encoding="utf-8"))

    completed = []
    failures = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.jobs)) as executor:
        future_map = {
            executor.submit(
                analyze_one,
                manifest,
                chunk,
                prompt_template,
                results_dir,
                token,
                args.base_url,
                job_id,
                max(0, args.retries),
                args.timeout,
                args.force,
            ): chunk["chunk_id"]
            for chunk in manifest["chunks"]
        }
        for future in concurrent.futures.as_completed(future_map):
            chunk_id = future_map[future]
            try:
                result = future.result()
                completed.append(result)
                print(json.dumps(result, ensure_ascii=False), flush=True)
            except Exception as exc:
                failure = {"chunk_id": chunk_id, "status": "failed", "error": str(exc)}
                failures.append(failure)
                print(json.dumps(failure, ensure_ascii=False), flush=True)

    summary = {"completed": len(completed), "failed": len(failures), "results_dir": str(results_dir)}
    print(json.dumps(summary, ensure_ascii=False))
    if failures:
        raise SystemExit(1)
    completion = complete_task(args.base_url, token, job_id)
    print(json.dumps(completion, ensure_ascii=False))


if __name__ == "__main__":
    main()
