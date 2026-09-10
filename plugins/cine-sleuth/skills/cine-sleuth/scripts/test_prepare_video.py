#!/usr/bin/env python3
"""Regression tests for CineSleuth proxy preparation."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from prepare_video import render_chunk


class RenderChunkTests(unittest.TestCase):
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
