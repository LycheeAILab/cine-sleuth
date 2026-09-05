"""Offline tests: real FFmpeg frames, host-authored reports, and mocked link download."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import build_visual_report as visual
import prepare_video_source as source
from prepare_video import sha256_file


class LinkTests(unittest.TestCase):
    def test_share_and_host_validation(self):
        self.assertEqual(source.authorized_url("分享 https://v.douyin.com/abcd/。"), "https://v.douyin.com/abcd/")
        for url in ("http://douyin.com/video/1", "https://douyin.com.evil.example/video/1",
                    "https://127.0.0.1/x", "https://name:pass@douyin.com/x", "https://douyin.com:80/x"):
            with self.assertRaises(source.SourceError):
                source.authorized_url(url)

    def test_fallback_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "source.mp4"
            with patch.object(source, "download_with_douk_direct", side_effect=source.SourceError("blocked")), \
                    patch.object(source, "download_with_ytdlp", return_value=output) as fallback:
                video, engine = source.download_douyin("分享 https://v.douyin.com/abcd/。", output)
                self.assertEqual((video, engine), (output, "yt-dlp"))
                fallback.assert_called_once_with("https://v.douyin.com/abcd/", output)
            output.touch()
            with self.assertRaises(source.SourceError):
                source.download_douyin("https://v.douyin.com/abcd/", output)

    def test_five_minute_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            video = Path(directory) / "video.mp4"
            video.write_bytes(b"fixture")
            with patch.object(source, "probe_video", return_value={"duration_seconds": 301}):
                with self.assertRaises(source.SourceError):
                    source.validate_video(video)


class VisualTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="cine-visual-test-")
        cls.root = Path(cls.temp.name)
        cls.video = cls.root / "竖屏 source.mp4"
        # Three colors at different frame rates exercise VFR frame-index selection.
        subprocess.run([
            "ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=red:s=180x320:r=10:d=1",
            "-f", "lavfi", "-i", "color=c=green:s=180x320:r=20:d=1",
            "-f", "lavfi", "-i", "color=c=blue:s=180x320:r=5:d=1",
            "-filter_complex", "[0:v][1:v][2:v]concat=n=3:v=1:a=0[v]", "-map", "[v]",
            "-fps_mode", "vfr", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(cls.video)
        ], check=True, capture_output=True)
        cls.segments = cls.root / "segments.json"
        cls.data = {"source_sha256": sha256_file(cls.video), "segments": [
            {"id": "seg-001", "start_seconds": 0, "end_seconds": 1},
            {"id": "seg-002", "start_seconds": 1, "end_seconds": 2},
            {"id": "seg-003", "start_seconds": 2.01, "end_seconds": 2.7},
        ]}
        cls.segments.write_text(json.dumps(cls.data), encoding="utf-8")
        cls.report = cls.root / "report-draft.md"
        cls.report.write_text("# 测试图文报告\n\n" + "\n\n".join(
            f"## {item['id']}\n\n{{{{frame:{item['id']}}}}}\n\n真实原片首帧。"
            for item in cls.data["segments"]
        ) + '\n\n<script>alert(1)</script>\n', encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_real_frames_portable_html_and_raw_unchanged(self):
        before = self.segments.read_bytes(), self.report.read_bytes(), sha256_file(self.video)
        out = self.root / "delivery"
        result = visual.build(self.video, self.segments, self.report, out)
        self.assertEqual(result["segments"], 3)
        frames = json.loads((out / "frames.json").read_text(encoding="utf-8"))["segments"]
        for expected, frame in enumerate(frames):
            rgb = subprocess.run(["ffmpeg", "-v", "error", "-i", str(out / frame["image"]),
                                  "-vf", "scale=1:1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                                 check=True, capture_output=True).stdout
            self.assertEqual(max(range(3), key=lambda channel: rgb[channel]), expected)
            self.assertGreaterEqual(frame["frame_seconds"], frame["start_seconds"])
            self.assertLess(frame["frame_seconds"], frame["end_seconds"])
        self.assertAlmostEqual(frames[-1]["frame_seconds"], 2.2, places=2)
        page = (out / "report.html").read_text(encoding="utf-8")
        self.assertEqual(page.count('src="data:image/jpeg;base64,'), 3)
        self.assertNotIn('<script>', page)
        self.assertNotIn('{{frame:', page)
        self.assertNotIn('{{frame:', (out / "report-text.md").read_text(encoding="utf-8"))
        self.assertEqual(before, (self.segments.read_bytes(), self.report.read_bytes(), sha256_file(self.video)))
        with self.assertRaises(ValueError):
            visual.build(self.video, self.segments, self.report, out)
        # Explicit opt-in test artifact, outside the public repository.
        if os.environ.get("CINE_TEST_PREVIEW"):
            import shutil
            shutil.copytree(out, os.environ["CINE_TEST_PREVIEW"], dirs_exist_ok=True)

    def test_invalid_segments(self):
        for segments in ([{"id": "../escape", "start_seconds": 0, "end_seconds": 1}],
                         [{"id": "s", "start_seconds": -1, "end_seconds": 1}],
                         [{"id": "s", "start_seconds": float("nan"), "end_seconds": 1}],
                         [{"id": "s", "start_seconds": 0, "end_seconds": 301}]):
            with self.assertRaises(ValueError):
                visual.validate_segments(segments, 3)

    def test_missing_marker_and_wrong_source(self):
        for bad_hash, bad_markers in ((True, False), (False, True)):
            data = dict(self.data)
            if bad_hash:
                data["source_sha256"] = "wrong"
            path = self.root / "invalid.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            report = self.root / "invalid.md"
            report.write_text("# no markers" if bad_markers else self.report.read_text(encoding="utf-8"), encoding="utf-8")
            with self.assertRaises(ValueError):
                visual.build(self.video, path, report, self.root / "invalid-output")
            self.assertFalse((self.root / "invalid-output").exists())


if __name__ == "__main__":
    unittest.main()
