#!/usr/bin/env python3
"""Prepare speech-aware proxy chunks for CineSleuth."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Iterable


def run(command: list[str], *, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=True,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
        encoding="utf-8",
        errors="replace",
    )


def require_binary(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise SystemExit(f"Required executable not found on PATH: {name}")
    return path


def parse_rate(value: str | None) -> float | None:
    if not value or value == "0/0":
        return None
    numerator, denominator = value.split("/", 1)
    denominator_value = float(denominator)
    return float(numerator) / denominator_value if denominator_value else None


def probe_video(path: Path, ffprobe: str) -> dict:
    completed = run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration,size,bit_rate:stream=index,codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels",
            "-of",
            "json",
            str(path),
        ],
        capture=True,
    )
    data = json.loads(completed.stdout)
    video = next((stream for stream in data.get("streams", []) if stream.get("codec_type") == "video"), None)
    audio = next((stream for stream in data.get("streams", []) if stream.get("codec_type") == "audio"), None)
    if not video:
        raise SystemExit("Input contains no video stream.")
    return {
        "duration_seconds": float(data["format"]["duration"]),
        "size_bytes": int(data["format"].get("size", 0)),
        "bit_rate": int(data["format"].get("bit_rate", 0)),
        "video_codec": video.get("codec_name"),
        "width": video.get("width"),
        "height": video.get("height"),
        "frame_rate": parse_rate(video.get("r_frame_rate")),
        "has_audio": audio is not None,
        "audio_codec": audio.get("codec_name") if audio else None,
        "sample_rate": int(audio["sample_rate"]) if audio and audio.get("sample_rate") else None,
        "channels": audio.get("channels") if audio else None,
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def ffmpeg_silence_candidates(
    path: Path, ffmpeg: str, duration: float, noise_db: float, min_silence: float
) -> list[float]:
    completed = subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-nostats",
            "-i",
            str(path),
            "-af",
            f"silencedetect=noise={noise_db}dB:d={min_silence}",
            "-f",
            "null",
            "-",
        ],
        text=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        errors="replace",
    )
    starts = [float(value) for value in re.findall(r"silence_start:\s*([0-9.]+)", completed.stderr)]
    ends = [float(value) for value in re.findall(r"silence_end:\s*([0-9.]+)", completed.stderr)]
    candidates: list[float] = []
    for index, start in enumerate(starts):
        end = ends[index] if index < len(ends) else duration
        if end > start:
            candidates.append((start + end) / 2.0)
    return candidates


def silero_candidates(path: Path, ffmpeg: str, duration: float, min_silence: float) -> list[float]:
    try:
        from silero_vad import get_speech_timestamps, load_silero_vad, read_audio
    except ImportError as exc:
        raise RuntimeError("silero-vad is not installed") from exc

    with tempfile.TemporaryDirectory(prefix="cine-sleuth-vad-") as temp_dir:
        wav_path = Path(temp_dir) / "audio.wav"
        run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(path),
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                str(wav_path),
            ]
        )
        waveform = read_audio(str(wav_path), sampling_rate=16000)
        model = load_silero_vad()
        speech = get_speech_timestamps(waveform, model, sampling_rate=16000, return_seconds=True)

    candidates: list[float] = []
    cursor = 0.0
    for interval in speech:
        start = float(interval["start"])
        if start - cursor >= min_silence:
            candidates.append((cursor + start) / 2.0)
        cursor = float(interval["end"])
    if duration - cursor >= min_silence:
        candidates.append((cursor + duration) / 2.0)
    return candidates


def shot_candidates(path: Path, ffmpeg: str, threshold: float) -> list[float]:
    completed = subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-i",
            str(path),
            "-vf",
            f"select='gt(scene,{threshold})',showinfo",
            "-an",
            "-f",
            "null",
            "-",
        ],
        text=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        errors="replace",
    )
    return [
        float(value)
        for value in re.findall(r"pts_time:([0-9.]+)", completed.stderr)
        if float(value) > 0.15
    ]


def unique_candidates(values: Iterable[float]) -> list[float]:
    result: list[float] = []
    for value in sorted(values):
        if not result or abs(value - result[-1]) >= 0.08:
            result.append(value)
    return result


def choose_core_ranges(
    duration: float,
    silence_points: list[float],
    shot_points: list[float],
    target: float,
    minimum: float,
    maximum: float,
) -> list[tuple[float, float, str]]:
    if not (0 < minimum <= target <= maximum):
        raise SystemExit("Expected 0 < min-duration <= target-duration <= max-duration.")

    ranges: list[tuple[float, float, str]] = []
    start = 0.0
    while duration - start > maximum:
        lower = start + minimum
        upper = min(start + maximum, duration - minimum)
        desired = start + target
        candidates: list[tuple[float, str, float]] = []
        for point in silence_points:
            if lower <= point <= upper:
                candidates.append((point, "silence", abs(point - desired)))
        for point in shot_points:
            if lower <= point <= upper:
                candidates.append((point, "shot", abs(point - desired) + 8.0))

        if candidates:
            end, reason, _ = min(candidates, key=lambda item: item[2])
        else:
            end = min(desired, upper)
            reason = "forced"
        ranges.append((start, end, reason))
        start = end
    ranges.append((start, duration, "end"))
    return ranges


def render_chunk(
    ffmpeg: str,
    source: Path,
    output: Path,
    start: float,
    end: float,
    width: int,
    video_bitrate: str,
    audio_bitrate: str,
) -> None:
    duration = max(0.001, end - start)
    run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            f"{start:.3f}",
            "-i",
            str(source),
            "-t",
            f"{duration:.3f}",
            "-map",
            "0:v:0",
            "-map",
            "0:a:0?",
            "-vf",
            f"scale={width}:-2:force_original_aspect_ratio=decrease",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-b:v",
            video_bitrate,
            "-maxrate",
            video_bitrate,
            "-bufsize",
            "1M",
            "-c:a",
            "aac",
            "-b:a",
            audio_bitrate,
            "-movflags",
            "+faststart",
            str(output),
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--vad", choices=("auto", "silero", "silence"), default="auto")
    parser.add_argument("--target-duration", type=float, default=90.0)
    parser.add_argument("--min-duration", type=float, default=45.0)
    parser.add_argument("--max-duration", type=float, default=120.0)
    parser.add_argument("--overlap", type=float, default=3.0)
    parser.add_argument("--min-silence", type=float, default=0.55)
    parser.add_argument("--silence-noise-db", type=float, default=-35.0)
    parser.add_argument("--scene-threshold", type=float, default=0.30)
    parser.add_argument("--proxy-width", type=int, default=540)
    parser.add_argument("--video-bitrate", default="450k")
    parser.add_argument("--audio-bitrate", default="64k")
    args = parser.parse_args()

    source = args.video.expanduser().resolve()
    if not source.is_file():
        raise SystemExit(f"Video not found: {source}")
    output_dir = args.output_dir.expanduser().resolve()
    chunks_dir = output_dir / "chunks"
    chunks_dir.mkdir(parents=True, exist_ok=True)

    ffmpeg = require_binary("ffmpeg")
    ffprobe = require_binary("ffprobe")
    metadata = probe_video(source, ffprobe)
    duration = metadata["duration_seconds"]

    vad_backend = "none"
    vad_warning = None
    silence_points: list[float] = []
    if metadata["has_audio"]:
        if args.vad in ("auto", "silero"):
            try:
                silence_points = silero_candidates(source, ffmpeg, duration, args.min_silence)
                vad_backend = "silero"
            except Exception as exc:  # optional backend must not break auto mode
                if args.vad == "silero":
                    raise SystemExit(f"Silero VAD failed: {exc}") from exc
                vad_warning = str(exc)
        if vad_backend == "none":
            silence_points = ffmpeg_silence_candidates(
                source, ffmpeg, duration, args.silence_noise_db, args.min_silence
            )
            vad_backend = "ffmpeg-silencedetect"

    shots = shot_candidates(source, ffmpeg, args.scene_threshold)
    silence_points = unique_candidates(silence_points)
    shots = unique_candidates(shots)
    core_ranges = choose_core_ranges(
        duration,
        silence_points,
        shots,
        args.target_duration,
        args.min_duration,
        args.max_duration,
    )

    chunks = []
    for index, (core_start, core_end, boundary_reason) in enumerate(core_ranges, start=1):
        start = max(0.0, core_start - (args.overlap if index > 1 else 0.0))
        end = min(duration, core_end + (args.overlap if index < len(core_ranges) else 0.0))
        output = chunks_dir / f"chunk-{index:03d}.mp4"
        render_chunk(
            ffmpeg,
            source,
            output,
            start,
            end,
            args.proxy_width,
            args.video_bitrate,
            args.audio_bitrate,
        )
        chunks.append(
            {
                "chunk_id": f"chunk-{index:03d}",
                "path": str(output),
                "source_start_seconds": round(start, 3),
                "source_end_seconds": round(end, 3),
                "duration_seconds": round(end - start, 3),
                "core_start_seconds": round(core_start, 3),
                "core_end_seconds": round(core_end, 3),
                "overlap_before_seconds": round(core_start - start, 3),
                "overlap_after_seconds": round(end - core_end, 3),
                "boundary_reason": boundary_reason,
            }
        )

    source_sha256 = sha256_file(source)
    client_request_id = "cine-1.0.1-" + hashlib.sha256(f"cine-sleuth:1.0.1:evidence-v2:{source_sha256}".encode("utf-8")).hexdigest()[:48]
    manifest = {
        "schema_version": 1,
        "client_request_id": client_request_id,
        "source": {
            "path": str(source),
            "sha256": source_sha256,
            **metadata,
        },
        "segmentation": {
            "vad_backend": vad_backend,
            "vad_warning": vad_warning,
            "target_duration_seconds": args.target_duration,
            "min_duration_seconds": args.min_duration,
            "max_duration_seconds": args.max_duration,
            "overlap_seconds": args.overlap,
            "silence_candidate_count": len(silence_points),
            "shot_candidate_count": len(shots),
        },
        "chunks": chunks,
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"manifest": str(manifest_path), "chunks": len(chunks), "vad": vad_backend}, ensure_ascii=False))


if __name__ == "__main__":
    main()
