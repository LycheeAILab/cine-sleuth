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
TABLE_FIELDS = (
    "shot_size", "motion_effects", "visuals", "dialogue_subtitle",
    "bgm", "sound_effects", "on_screen_text", "analysis",
    "video_generation_prompt",
)


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
        segment = {"id": identifier, "start_seconds": start, "end_seconds": end,
                   "title": str(item.get("title", identifier))}
        for field in TABLE_FIELDS:
            value = item.get(field, "")
            if value is not None and not isinstance(value, (str, int, float)):
                raise ValueError(f"{field} must be plain text for {identifier}")
            segment[field] = str(value or "").strip()
        result.append(segment)
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


def format_time(seconds: float) -> str:
    milliseconds = round(seconds * 1000)
    minutes, remainder = divmod(milliseconds, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{minutes:02d}:{secs:02d}.{millis:03d}"


def cell(value: object, fallback: str = "—") -> str:
    text = str(value or "").strip() or fallback
    return html.escape(text).replace("\n", "<br>")


def shot_table(frames: list[dict], output: Path) -> str:
    rows = []
    for frame in frames:
        encoded = base64.b64encode((output / frame["image"]).read_bytes()).decode("ascii")
        time_range = f"{format_time(frame['start_seconds'])}<br><span>— {format_time(frame['end_seconds'])}</span>"
        analysis = cell(frame.get("analysis"), cell(frame.get("title")))
        prompt = cell(frame.get("video_generation_prompt"))
        rows.append(f'''<tr>
<td class="frame"><img src="data:image/jpeg;base64,{encoded}" alt="{cell(frame['title'])}" loading="lazy"><b>{cell(frame['title'])}</b></td>
<td class="time"><code>{time_range}</code></td>
<td>{cell(frame.get('shot_size'))}</td>
<td class="motion">{cell(frame.get('motion_effects'))}</td>
<td>{cell(frame.get('visuals'), analysis)}</td>
<td class="speech">{cell(frame.get('dialogue_subtitle'))}</td>
<td class="music">{cell(frame.get('bgm'))}</td>
<td>{cell(frame.get('sound_effects'))}</td>
<td class="textfx">{cell(frame.get('on_screen_text'))}</td>
<td class="prompt"><details><summary>展开</summary><p>{analysis}</p><strong>视频生成提示词</strong><p>{prompt}</p></details></td>
</tr>''')
    return '''<section class="shot-section"><div class="section-heading"><div><span class="eyebrow">SHOT BY SHOT</span><h2>逐镜拉片表</h2></div><div class="legend"><i class="speech-dot"></i>口播字幕 <i class="music-dot"></i>BGM <i class="motion-dot"></i>运动特效 <i class="text-dot"></i>画面花字</div></div>
<div class="table-wrap"><table class="shot-table"><thead><tr><th>帧</th><th>时间</th><th>景别</th><th>运动特效</th><th>画面</th><th>口播字幕</th><th>BGM</th><th>音效</th><th>画面花字</th><th>分析 / 提示词</th></tr></thead><tbody>''' + "".join(rows) + "</tbody></table></div></section>"


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
    # HTML leads with a dense shot table. Markdown remains the portable illustrated package.
    body = markdown.markdown(html.escape(plain_report, quote=False), extensions=["tables", "fenced_code"])
    table = shot_table(frames, output)
    document = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>CineSleuth · 图文拉片报告</title><style>
*{box-sizing:border-box}body{margin:0;background:#eef2f1;color:#20262b;font:14px/1.65 Inter,"PingFang SC","Microsoft YaHei",system-ui,sans-serif}
header{padding:42px 5vw 28px;background:#122129;color:#fff}header b{color:#8ad7c1;letter-spacing:.16em}header h1{margin:8px 0 4px;font-size:clamp(28px,4vw,48px);line-height:1.15}header p{margin:0;color:#b9c7cc}
main{width:min(1800px,96vw);margin:24px auto 56px}.shot-section,.narrative{background:#fff;border:1px solid #dce3e1;border-radius:14px;box-shadow:0 12px 35px #17302b12;overflow:hidden}.narrative{max-width:980px;margin:28px auto 0;padding:42px}
.section-heading{display:flex;align-items:end;justify-content:space-between;gap:24px;padding:22px 26px 16px}.section-heading h2{margin:2px 0 0;font-size:24px}.eyebrow{color:#24866e;font-size:11px;font-weight:800;letter-spacing:.18em}.legend{color:#657278;font-size:12px;white-space:nowrap}.legend i{display:inline-block;width:4px;height:14px;margin:0 5px 0 14px;vertical-align:-2px;border-radius:2px}.speech-dot{background:#1ca7d8}.music-dot{background:#9b50ba}.motion-dot{background:#61a74e}.text-dot{background:#e3a41e}
.table-wrap{overflow:auto;border-top:1px solid #dce3e1}.shot-table{width:100%;min-width:1480px;border-collapse:separate;border-spacing:0;table-layout:fixed}.shot-table th{position:sticky;top:0;z-index:1;background:#23343d;color:#fff;padding:11px 10px;text-align:left;font-size:12px;letter-spacing:.04em}.shot-table td{padding:10px;vertical-align:top;border-right:1px solid #e1e6e4;border-bottom:1px solid #e1e6e4;white-space:pre-wrap;overflow-wrap:anywhere}.shot-table tbody tr:nth-child(even) td{background:#fafbf9}.shot-table th:nth-child(1){width:170px}.shot-table th:nth-child(2){width:125px}.shot-table th:nth-child(3){width:85px}.shot-table th:nth-child(4){width:145px}.shot-table th:nth-child(5){width:210px}.shot-table th:nth-child(6){width:190px}.shot-table th:nth-child(7){width:150px}.shot-table th:nth-child(8){width:150px}.shot-table th:nth-child(9){width:180px}.shot-table th:nth-child(10){width:190px}
.shot-table td.motion{background:#f1f8ec!important;border-left:3px solid #61a74e}.shot-table td.speech{background:#edf8fc!important;border-left:3px solid #1ca7d8}.shot-table td.music{background:#f7eef9!important;border-left:3px solid #9b50ba}.shot-table td.textfx{background:#fff8df!important;border-left:3px solid #e3a41e}.frame img{display:block;width:150px;aspect-ratio:16/9;object-fit:cover;border-radius:7px;background:#111;margin:0 0 7px}.frame b{font-size:12px}.time code{font:11px/1.55 ui-monospace,SFMono-Regular,Consolas,monospace;white-space:nowrap;color:#34434a}.time span{color:#829097}.prompt summary{cursor:pointer;color:#247f69;font-weight:700}.prompt p{margin:7px 0}.prompt strong{font-size:12px}
.narrative h1,.narrative h2,.narrative h3{line-height:1.35}.narrative h1{font-size:34px}.narrative h2{margin-top:42px;border-top:1px solid #ddd;padding-top:22px}.narrative table{display:block;overflow:auto;border-collapse:collapse;width:100%}.narrative td,.narrative th{border:1px solid #ddd;padding:10px;text-align:left}.narrative pre{padding:16px;background:#f6f6f6;overflow:auto}
@media(max-width:720px){header{padding:28px 18px 22px}main{width:100%;margin:0}.shot-section,.narrative{border-radius:0;border-left:0;border-right:0}.section-heading{display:block;padding:18px}.legend{margin-top:10px;white-space:normal}.narrative{padding:22px}.shot-table{min-width:1320px}}
@media print{body{background:#fff}header{padding:18px 0;color:#111;background:#fff}main{width:100%;margin:0}.shot-section,.narrative{box-shadow:none;border:0}.table-wrap{overflow:visible}.shot-table{min-width:0;font-size:8px}.shot-table th,.shot-table td{padding:4px}.frame img{width:100px}.prompt details{display:block}.narrative{padding:20px 0}@page{size:A3 landscape;margin:8mm}}
</style><header><b>CINESLEUTH</b><h1>逐镜图文拉片</h1><p>原片首帧 · 全局时间码 · 视听语言与画面文字</p></header><main>''' + table + '<article class="narrative">' + body + "</article></main></html>"
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
