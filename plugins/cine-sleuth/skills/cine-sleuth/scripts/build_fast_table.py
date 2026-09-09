#!/usr/bin/env python3
"""Build a table-only CineSleuth report directly from assembled cloud evidence."""

from __future__ import annotations

import argparse
import difflib
import json
from pathlib import Path
import re
import tempfile

from build_visual_report import build


TEXT_KEYS = ("text", "description", "observation", "item", "reason", "content", "label", "name", "type", "position", "style", "value")
META_KEYS = {"id", "start", "end", "global_start_seconds", "global_end_seconds", "confidence", "source_chunk_id", "shot_ids", "transcript_ids"}
ZH_TERMS = (
    ("extreme close-up", "大特写"), ("medium close-up", "中近景"), ("medium long shot", "中全景"),
    ("bird's-eye view", "俯瞰"), ("eye-level", "平视"), ("close-up", "特写"),
    ("medium shot", "中景"), ("wide shot", "远景"), ("long shot", "远景"), ("full shot", "全景"),
    ("low angle", "仰拍"), ("high angle", "俯拍"), ("handheld", "手持摄影"),
    ("tracking shot", "跟拍"), ("static shot", "固定镜头"), ("static", "固定"),
    ("zoom in", "推近"), ("zoom out", "拉远"), ("fade in", "淡入"), ("fade out", "淡出"),
    ("dissolve", "叠化"), ("hard cut", "硬切"), ("cut", "切换"), ("pan", "横摇"), ("tilt", "俯仰摇镜"),
    ("sound effect", "音效"), ("ambient sound", "环境声"), ("background music", "背景音乐"),
    ("silence", "静音"), ("music", "音乐"),
)


def text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return "；".join(dict.fromkeys(item for entry in value if (item := text(entry))))
    if isinstance(value, dict):
        preferred = [text(value[key]) for key in TEXT_KEYS if key in value and text(value[key])]
        if preferred:
            return "，".join(dict.fromkeys(preferred))
        return "，".join(dict.fromkeys(item for key, entry in value.items() if key not in META_KEYS and (item := text(entry))))
    return str(value).strip()


def chinese(value: object) -> str:
    result = text(value)
    for source, target in ZH_TERMS:
        result = re.sub(re.escape(source), target, result, flags=re.IGNORECASE)
    return result


def similar(left: dict, right: dict) -> bool:
    if left.get("source_chunk_id") == right.get("source_chunk_id"):
        return False
    a0, a1 = left.get("global_start_seconds"), left.get("global_end_seconds")
    b0, b1 = right.get("global_start_seconds"), right.get("global_end_seconds")
    if None in (a0, a1, b0, b1):
        return False
    overlap = min(a1, b1) - max(a0, b0)
    shorter = min(a1 - a0, b1 - b0)
    if shorter <= 0 or overlap / shorter < 0.8:
        return False
    left_visual = re.sub(r"\W+", "", text(left.get("visuals")))
    right_visual = re.sub(r"\W+", "", text(right.get("visuals")))
    return bool(left_visual and right_visual and difflib.SequenceMatcher(None, left_visual, right_visual).ratio() >= 0.6)


def deduplicate(shots: list[dict]) -> list[dict]:
    result: list[dict] = []
    for shot in sorted(shots, key=lambda item: item.get("global_start_seconds", float("inf"))):
        duplicate = next((item for item in reversed(result[-3:]) if similar(item, shot)), None)
        if duplicate is None:
            result.append(dict(shot))
            continue
        duplicate["global_start_seconds"] = min(duplicate["global_start_seconds"], shot["global_start_seconds"])
        duplicate["global_end_seconds"] = max(duplicate["global_end_seconds"], shot["global_end_seconds"])
        for key in ("visuals", "characters_actions", "sound", "video_generation_prompt"):
            if len(text(shot.get(key))) > len(text(duplicate.get(key))):
                duplicate[key] = shot[key]
    return result


def overlaps(item: dict, start: float, end: float) -> bool:
    return item.get("global_start_seconds", float("inf")) < end and item.get("global_end_seconds", -1) > start


def joined(values: list[str], fallback: str = "无") -> str:
    unique = []
    for value in values:
        value = text(value)
        if value and value not in unique:
            unique.append(value)
    return "；".join(unique) or fallback


def fast_segments(evidence: dict) -> list[dict]:
    shots = deduplicate(evidence.get("shot_evidence", []))
    transcript = evidence.get("transcript", [])
    audio = evidence.get("audio_events", [])
    segments = []
    for index, shot in enumerate(shots, 1):
        start, end = shot.get("global_start_seconds"), shot.get("global_end_seconds")
        if not isinstance(start, (int, float)) or not isinstance(end, (int, float)) or end <= start:
            raise ValueError("Shot evidence contains an invalid global time range")
        lines = []
        for item in transcript:
            if overlaps(item, start, end):
                spoken = text(item.get("text"))
                subtitle = text(item.get("subtitle_text"))
                speaker = text(item.get("speaker")) or "说话人未确定"
                if spoken:
                    lines.append(f"{speaker}：{spoken}")
                if subtitle and subtitle != spoken:
                    lines.append(f"字幕：{subtitle}")
        events = [item for item in audio if overlaps(item, start, end)]
        music = [chinese(item.get("description")) for item in events if item.get("type") == "music"]
        effects = [item.get("description") for item in events if item.get("type") != "music"]
        observations = joined([chinese(shot.get("observed_facts")), chinese(shot.get("interpretations"))], "快速表格模式：未生成扩展分析")
        visual = joined([chinese(shot.get("visuals")), chinese(shot.get("characters_actions")), chinese(shot.get("camera_angle"))])
        title_source = text(shot.get("on_screen_text")) or text(shot.get("visuals")) or f"镜头 {index}"
        segments.append({
            "id": f"seg-{index:03d}", "start_seconds": start, "end_seconds": end,
            "title": title_source[:40], "shot_size": chinese(shot.get("shot_size")) or "未标注",
            "motion_effects": joined([chinese(shot.get("transition_in")), chinese(shot.get("camera_movement"))]),
            "visuals": visual, "dialogue_subtitle": joined(lines), "bgm": joined(music),
            "sound_effects": joined([chinese(item) for item in effects] + [chinese(shot.get("sound"))]),
            "on_screen_text": text(shot.get("on_screen_text")) or "无", "analysis": observations,
            "video_generation_prompt": chinese(shot.get("video_generation_prompt")) or "未生成",
        })
    if not segments:
        raise ValueError("Evidence contains no usable shots")
    return segments


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--title", default="CineSleuth 极速拉片表")
    args = parser.parse_args()
    evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
    if evidence.get("missing_chunks"):
        raise SystemExit("Fast table failed: evidence has missing chunks")
    segments = fast_segments(evidence)
    with tempfile.TemporaryDirectory(prefix="cine-fast-table-") as temporary:
        work = Path(temporary)
        segments_path, report_path = work / "segments.json", work / "report-draft.md"
        segments_path.write_text(json.dumps({"source_sha256": evidence["source"]["sha256"], "table_only": True, "segments": segments}, ensure_ascii=False, indent=2), encoding="utf-8")
        report_path.write_text("# " + args.title + "\n\n仅输出逐镜证据表，不生成额外长文总结。\n\n" + "\n\n".join(f"## {item['id']}\n\n{{{{frame:{item['id']}}}}}" for item in segments), encoding="utf-8")
        result = build(args.video, segments_path, report_path, args.output_dir)
    result["mode"] = "fast-table"
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
