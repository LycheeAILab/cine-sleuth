#!/usr/bin/env python3
"""Illustrate the host Agent's final report with source-accurate segment first frames.

This local-only step never reads/writes cloud model results or calls an analysis API.
"""

from __future__ import annotations

import argparse
import base64
from bisect import bisect_left
import html
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from prepare_video import probe_video, require_binary, sha256_file


MARKER = re.compile(r"\{\{frame:([A-Za-z0-9_-]+)\}\}")


def validate_segments(items: object, duration: float) -> list[dict]:
    if not isinstance(items, list) or not 1 <= len(items) <= 500:
        raise ValueError("segments must contain 1 to 500 final report segments, not technical chunks")
    result, seen = [], set()
    previous = -1.0
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Each segment must be an object")
        identifier = str(item.get("id", ""))
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", identifier) or identifier in seen:
            raise ValueError("Each segment needs a unique safe id")
        start, end = float(item["start_seconds"]), float(item["end_seconds"])
        if not (math.isfinite(start) and math.isfinite(end)
                and 0 <= start < end <= duration + 0.001 and start >= previous):
            raise ValueError(f"Invalid or unordered source timeline for {identifier}")
        result.append({"id": identifier, "start_seconds": start, "end_seconds": end,
                       "title": str(item.get("title", identifier))})
        previous = start
        seen.add(identifier)
    return result


def frame_times(video: Path) -> list[float]:
    completed = subprocess.run(
        [require_binary("ffprobe"), "-v", "error", "-select_streams", "v:0",
         "-show_frames", "-show_entries", "frame=best_effort_timestamp_time:format=start_time", "-of", "json", str(video)],
        capture_output=True, text=True, encoding="utf-8", check=True, timeout=180,
    )
    payload = json.loads(completed.stdout)
    decoded = payload["frames"]
    if any("best_effort_timestamp_time" not in frame for frame in decoded):
        raise ValueError("Missing source frame timestamp; cannot safely select by frame index")
    values = [float(frame["best_effort_timestamp_time"]) for frame in decoded]
    if not values or any(not math.isfinite(value) for value in values):
        raise ValueError("Source has no usable frame timestamps")
    origin = float(payload.get("format", {}).get("start_time", values[0]))
    values = [value - origin for value in values]
    if values != sorted(values):
        raise ValueError("Source frame timestamps are not ordered")
    return values


def build(video: Path, segments_path: Path, report_path: Path, output: Path) -> dict:
    import markdown

    video, output = video.resolve(), output.resolve()
    metadata = probe_video(video, require_binary("ffprobe"))
    duration = metadata["duration_seconds"]
    if not 0 < duration <= 300:
        raise ValueError("Source must be no longer than 5 minutes")
    source_data = json.loads(segments_path.read_text(encoding="utf-8"))
    segments = validate_segments(source_data["segments"], duration)
    source_hash = sha256_file(video)
    if source_data.get("source_sha256") != source_hash:
        raise ValueError("segments.json source_sha256 does not match the original video")
    report = report_path.read_text(encoding="utf-8")
    markers = MARKER.findall(report)
    ids = [item["id"] for item in segments]
    if sorted(markers) != sorted(ids):
        raise ValueError("Report must contain exactly one {{frame:ID}} marker for every segment")
    if output.exists() and any(output.iterdir()):
        raise ValueError("Output directory must be empty; use a new directory to preserve existing reports")
    times = frame_times(video)
    selections = []
    for segment in segments:
        index = bisect_left(times, segment["start_seconds"] - 1e-7)
        if index >= len(times) or times[index] >= segment["end_seconds"]:
            raise ValueError(f"No source frame in segment {segment['id']}; check its boundaries")
        selections.append(index)
    frames_dir = output / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    # Decode the source once even when there are hundreds of segments.
    unique_indices = sorted(set(selections))
    expression = "+".join(f"eq(n\\,{index})" for index in unique_indices)
    with tempfile.TemporaryDirectory(prefix="cine-frames-") as temporary:
        subprocess.run(
            [require_binary("ffmpeg"), "-v", "error", "-nostdin", "-i", str(video),
             "-vf", f"select='{expression}',scale='min(960,iw)':-2",
             "-frames:v", str(len(unique_indices)), "-fps_mode", "vfr", "-q:v", "2",
             str(Path(temporary) / "%06d.jpg")],
            check=True, capture_output=True, timeout=180,
        )
        for segment, index in zip(segments, selections):
            source_frame = Path(temporary) / f"{unique_indices.index(index) + 1:06d}.jpg"
            if not source_frame.is_file() or not source_frame.stat().st_size:
                raise ValueError(f"No first frame produced for {segment['id']}")
            shutil.copy2(source_frame, frames_dir / f"{segment['id']}.jpg")
    frames = []
    plain_report = MARKER.sub("", report)
    for segment, index in zip(segments, selections):
        filename = f"frames/{segment['id']}.jpg"
        destination = output / filename
        if not destination.is_file() or not destination.stat().st_size:
            raise ValueError(f"No first frame produced for {segment['id']}")
        frame = {**segment, "frame_seconds": times[index], "frame_index": index, "image": filename}
        frames.append(frame)
        stamp = f"{times[index]:.3f}s"
        report = report.replace("{{frame:" + segment["id"] + "}}",
                                f"![{segment['id']} · {stamp}]({filename})\n\n"
                                f"*{segment['id']} · 原片首帧 {stamp}*")
    # Raw HTML from source material is displayed as text, never trusted markup.
    body = markdown.markdown(html.escape(report, quote=False), extensions=["tables", "fenced_code"])
    for frame in frames:
        encoded = base64.b64encode((output / frame["image"]).read_bytes()).decode("ascii")
        body = body.replace('src="' + frame["image"] + '"', 'src="data:image/jpeg;base64,' + encoded + '"')
    document = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>CineSleuth · 图文拉片报告</title><style>
body{margin:0;background:#f4f4f2;color:#202124;font:16px/1.8 system-ui,sans-serif}
main{max-width:980px;margin:40px auto;padding:48px;background:white;border-radius:16px}
h1,h2,h3{line-height:1.35}h1{font-size:34px}h2{margin-top:48px;border-top:1px solid #ddd;padding-top:24px}
img{display:block;max-width:100%;max-height:520px;object-fit:contain;border-radius:8px;margin:20px 0}
table{display:block;overflow:auto;border-collapse:collapse;width:100%}td,th{border:1px solid #ddd;padding:10px;text-align:left}
pre{padding:16px;background:#f6f6f6;overflow:auto}a{color:#344b72}em{color:#62666c}
@media(max-width:640px){main{padding:20px;margin:0;border-radius:0}h1{font-size:28px}}
@media print{body{background:white}main{margin:0;padding:0}img{break-inside:avoid}}
</style><main>''' + body + "</main></html>"
    (output / "report.md").write_text(report, encoding="utf-8")
    (output / "report-text.md").write_text(plain_report, encoding="utf-8")
    (output / "report.html").write_text(document, encoding="utf-8")
    payload = {"source_sha256": source_hash, "frame_policy": "first decoded frame at or after segment start",
               "segments": frames}
    (output / "frames.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"report": str(output / "report.html"), "markdown": str(output / "report.md"), "segments": len(frames)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--segments", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(build(args.video, args.segments, args.report, args.output_dir), ensure_ascii=False))
    except (ValueError, KeyError, OSError, subprocess.SubprocessError) as exc:
        raise SystemExit(f"Visual report failed: {exc}") from exc


if __name__ == "__main__":
    main()
