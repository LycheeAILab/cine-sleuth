#!/usr/bin/env python3
"""Convert chunk-local CineSleuth evidence to a global source timeline."""

from __future__ import annotations

import argparse
import difflib
import json
import re
from pathlib import Path


TIMED_COLLECTIONS = ("transcript", "shots", "scene_candidates", "audio_events")


def parse_timecode(value: object) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    parts = str(value).strip().split(":")
    try:
        if len(parts) == 2:
            return float(parts[0]) * 60 + float(parts[1])
        if len(parts) == 3:
            return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
        return float(parts[0])
    except (ValueError, IndexError):
        return None


def format_timecode(seconds: float) -> str:
    seconds = max(0.0, seconds)
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    remainder = seconds % 60
    if hours:
        return f"{hours:02d}:{minutes:02d}:{remainder:06.3f}"
    return f"{minutes:02d}:{remainder:06.3f}"


def globalize_item(item: dict, chunk: dict) -> dict:
    result = dict(item)
    result["source_chunk_id"] = chunk["chunk_id"]
    offset = float(chunk["source_start_seconds"])
    for key in ("start", "end", "time"):
        local = parse_timecode(item.get(key))
        if local is not None:
            result[f"local_{key}"] = item.get(key)
            result[f"global_{key}_seconds"] = round(offset + local, 3)
            result[f"global_{key}"] = format_timecode(offset + local)
    return result


def normalized_text(value: object) -> str:
    return re.sub(r"[\W_]+", "", str(value or "").lower(), flags=re.UNICODE)


def intervals_overlap(left: dict, right: dict) -> bool:
    left_start = left.get("global_start_seconds")
    left_end = left.get("global_end_seconds")
    right_start = right.get("global_start_seconds")
    right_end = right.get("global_end_seconds")
    if None in (left_start, left_end, right_start, right_end):
        return False
    return min(left_end, right_end) - max(left_start, right_start) >= -0.25


def deduplicate_transcript(items: list[dict]) -> list[dict]:
    ordered = sorted(items, key=lambda item: item.get("global_start_seconds", float("inf")))
    merged: list[dict] = []
    for item in ordered:
        text = normalized_text(item.get("text"))
        duplicate_index = None
        for index in range(max(0, len(merged) - 4), len(merged)):
            candidate = merged[index]
            candidate_text = normalized_text(candidate.get("text"))
            similarity = difflib.SequenceMatcher(None, text, candidate_text).ratio() if text and candidate_text else 0.0
            if intervals_overlap(item, candidate) and (
                similarity >= 0.82 or (text and candidate_text and (text in candidate_text or candidate_text in text))
            ):
                duplicate_index = index
                break
        if duplicate_index is None:
            copy = dict(item)
            copy["source_chunk_ids"] = [copy.pop("source_chunk_id")]
            merged.append(copy)
            continue

        candidate = merged[duplicate_index]
        candidate["source_chunk_ids"] = sorted(
            set(candidate.get("source_chunk_ids", [])) | {item["source_chunk_id"]}
        )
        if len(str(item.get("text", ""))) > len(str(candidate.get("text", ""))):
            for key in ("text", "speaker", "delivery", "subtitle_text", "confidence"):
                if item.get(key) not in (None, ""):
                    candidate[key] = item[key]
        starts = [value for value in (candidate.get("global_start_seconds"), item.get("global_start_seconds")) if value is not None]
        ends = [value for value in (candidate.get("global_end_seconds"), item.get("global_end_seconds")) if value is not None]
        if starts:
            candidate["global_start_seconds"] = min(starts)
            candidate["global_start"] = format_timecode(min(starts))
        if ends:
            candidate["global_end_seconds"] = max(ends)
            candidate["global_end"] = format_timecode(max(ends))
    return merged


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--results-dir", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    manifest_path = args.manifest.expanduser().resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    results_dir = (args.results_dir or manifest_path.parent / "results").expanduser().resolve()

    assembled = {
        "schema_version": 2,
        "source": manifest["source"],
        "segmentation": manifest["segmentation"],
        "chunk_status": [],
        "transcript": [],
        "shot_evidence": [],
        "scene_candidates": [],
        "audio_events": [],
        "uncertain_items": [],
    }
    missing = []
    for chunk in manifest["chunks"]:
        result_path = results_dir / f"{chunk['chunk_id']}.json"
        if not result_path.is_file():
            missing.append(chunk["chunk_id"])
            assembled["chunk_status"].append({"chunk_id": chunk["chunk_id"], "status": "missing"})
            continue
        evidence = json.loads(result_path.read_text(encoding="utf-8"))
        assembled["chunk_status"].append(
            {
                "chunk_id": chunk["chunk_id"],
                "status": "available",
                "source_start_seconds": chunk["source_start_seconds"],
                "source_end_seconds": chunk["source_end_seconds"],
                "boundary_flags": evidence.get("chunk", {}),
            }
        )
        for collection in TIMED_COLLECTIONS:
            target = "shot_evidence" if collection == "shots" else collection
            assembled[target].extend(
                globalize_item(item, chunk) for item in evidence.get(collection, []) if isinstance(item, dict)
            )
        assembled["uncertain_items"].extend(
            globalize_item(item, chunk) for item in evidence.get("uncertain_items", []) if isinstance(item, dict)
        )

    assembled["transcript"] = deduplicate_transcript(assembled["transcript"])
    assembled["missing_chunks"] = missing
    for key in ("shot_evidence", "scene_candidates", "audio_events", "uncertain_items"):
        assembled[key].sort(
            key=lambda item: item.get("global_start_seconds", item.get("global_time_seconds", float("inf")))
        )

    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(assembled, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(output),
                "transcript_items": len(assembled["transcript"]),
                "shot_evidence_items": len(assembled["shot_evidence"]),
                "scene_candidates": len(assembled["scene_candidates"]),
                "missing_chunks": missing,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
