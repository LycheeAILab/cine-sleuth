#!/usr/bin/env python3
"""Regression tests for CineSleuth proxy preparation."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from prepare_video import render_chunk, probe_video, sha256_file


class RenderChunkTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg is required")
    def test_compact_proxy_keeps_audio_timing_and_original(self):
        ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
        for dimensions in ("1920x1080", "1080x1920", "240x160"):
            with self.subTest(dimensions=dimensions), tempfile.TemporaryDirectory(prefix="cine-compact-") as directory:
                source, output = Path(directory)/"original.mp4", Path(directory)/"proxy.mp4"
                subprocess.run([ffmpeg,"-v","error","-f","lavfi","-i",f"testsrc2=s={dimensions}:r=30:d=2","-f","lavfi","-i","sine=frequency=440:duration=2","-c:v","libx264","-preset","ultrafast","-crf","18","-c:a","aac",str(source)],check=True)
                original_hash=sha256_file(source)
                render_chunk(ffmpeg,source,output,0,2,480,"350k","64k")
                info=probe_video(output,ffprobe)
                self.assertLessEqual(max(info["width"],info["height"]),480)
                self.assertEqual(info["frame_rate"],25)
                self.assertEqual(info["video_codec"],"h264")
                self.assertEqual(info["audio_codec"],"aac")
                self.assertLess(abs(info["duration_seconds"]-2),0.1)
                self.assertEqual(sha256_file(source),original_hash)
                if dimensions=="240x160":self.assertEqual((info["width"],info["height"]),(240,160))
                else:self.assertLess(output.stat().st_size,source.stat().st_size)
                print(dimensions, '=>',info["width"],info["height"], 'bytes',source.stat().st_size,'=>',output.stat().st_size)

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg is required")
    def test_proxy_dimensions_remain_even_for_widescreen_source(self) -> None:
        ffmpeg = shutil.which("ffmpeg")
        ffprobe = shutil.which("ffprobe")
        assert ffmpeg and ffprobe

        with tempfile.TemporaryDirectory(prefix="cine-sleuth-proxy-") as directory:
            root = Path(directory)
            source = root / "source.mp4"
            output = root / "chunk.mp4"
            subprocess.run(
                [
                    ffmpeg,
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    "color=c=black:s=1264x708:r=25:d=0.2",
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    str(source),
                ],
                check=True,
            )

            render_chunk(ffmpeg, source, output, 0.0, 0.2, 540, "450k", "64k")
            probe = subprocess.run(
                [
                    ffprobe,
                    "-v",
                    "error",
                    "-select_streams",
                    "v:0",
                    "-show_entries",
                    "stream=width,height",
                    "-of",
                    "json",
                    str(output),
                ],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            stream = json.loads(probe.stdout)["streams"][0]
            self.assertEqual((stream["width"], stream["height"]), (540, 302))
            self.assertEqual(stream["width"] % 2, 0)
            self.assertEqual(stream["height"] % 2, 0)


if __name__ == "__main__":
    unittest.main()
