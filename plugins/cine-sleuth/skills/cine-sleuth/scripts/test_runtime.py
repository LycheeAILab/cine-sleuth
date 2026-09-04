#!/usr/bin/env python3
"""No-network smoke tests for the CineSleuth Lab gateway client."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import analyze_chunks
import lab_video


class FakeResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        evidence = json.dumps({
            "media_fingerprint": {"media_visible": True, "observed_frame_count": 2, "visual_medium": "live action", "visible_subjects": ["person"]},
            "shots": [{"start": 0, "end": 1, "video_generation_prompt": "A single verified shot"}],
        })
        payload = {"candidates": [{"content": {"parts": [{"text": evidence}]}}]}
        return json.dumps(payload).encode("utf-8")


class StaticResponse(FakeResponse):
    def __init__(self, payload: dict):
        self.payload = payload

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def main() -> None:
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse()

    with tempfile.TemporaryDirectory() as directory:
        video = Path(directory) / "chunk.mp4"
        video.write_bytes(b"mock-mp4")
        with patch.object(analyze_chunks.urllib.request, "urlopen", fake_urlopen):
            result = analyze_chunks.request_chunk(
                "lych_live_test_user_credential",
                "https://lab.lycheeai.com.cn/",
                "11111111-1111-1111-1111-111111111111",
                "chunk-001",
                "Inspect this chunk",
                video,
                12.0,
            )

    request = captured["request"]
    assert request.full_url == "https://lab.lycheeai.com.cn/api/cine-sleuth/analyze"
    assert request.headers["Authorization"] == "Bearer lych_live_test_user_credential"
    assert request.headers["Content-type"].startswith("multipart/form-data; boundary=")
    assert b'form-data; name="jobId"' in request.data
    assert b"11111111-1111-1111-1111-111111111111" in request.data
    assert b'form-data; name="chunkKey"' in request.data
    assert b"chunk-001" in request.data
    assert b"Inspect this chunk" in request.data
    assert b'form-data; name="video"' in request.data
    assert b"mock-mp4" in request.data
    assert captured["timeout"] == 12.0
    assert result["media_fingerprint"]["media_visible"] is True
    assert result["shots"] == [{"start": 0, "end": 1, "video_generation_prompt": "A single verified shot"}]

    recovered = {"candidates": [{"content": {"parts": [{"text": "{\"shots\": []}"}]}}]}
    with patch.object(
        analyze_chunks.urllib.request,
        "urlopen",
        return_value=StaticResponse({"status": "completed", "result": recovered}),
    ):
        assert analyze_chunks.wait_for_chunk(
            "lych_live_test_user_credential",
            "https://lab.lycheeai.com.cn",
            "11111111-1111-1111-1111-111111111111",
            "chunk-001",
            1.0,
        ) == recovered

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "original.mp4"
        source.write_bytes(b"untouched-original")
        manifest_path = root / "manifest.json"
        manifest = {"client_request_id": "cine-1.0.2-test-request", "source": {"path": str(source), "sha256": "a" * 64, "duration_seconds": 42.5}, "chunks": [{"chunk_id": "chunk-001"}]}
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        created = {
            "jobId": "22222222-2222-2222-2222-222222222222",
            "status": "queued",
            "reused": False,
            "originalVideo": {"status": "pending", "mediaType": "video/mp4"},
            "upload": {"method": "PUT", "url": "https://cos.example/signed"},
        }
        ready = {
            "jobId": created["jobId"],
            "status": "queued",
            "originalVideo": {"status": "ready", "mediaType": "video/mp4"},
            "upload": None,
        }
        with patch.object(lab_video, "api_json", side_effect=[created, ready]) as api_call, patch.object(lab_video, "stream_put") as upload:
            job_id = lab_video.ensure_original_uploaded(
                manifest_path, manifest, "lych_live_test_user_credential", "https://lab.lycheeai.com.cn"
            )
        assert job_id == created["jobId"]
        assert api_call.call_count == 2
        upload.assert_called_once_with("https://cos.example/signed", source, "video/mp4")
        saved = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert api_call.call_args_list[0].args[4]["clientRequestId"] == "cine-1.0.2-test-request"
        assert api_call.call_args_list[0].args[4]["durationSeconds"] == 42.5
        assert api_call.call_args_list[0].args[4]["chunkCount"] == 1
        assert saved["lab_task"] == {"job_id": created["jobId"], "original_upload": "ready", "status": "queued", "reused": False}
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        manifest_path = root / "manifest.json"
        manifest_path.write_text(json.dumps({"lab_task": {"status": "completed"}, "chunks": [{"chunk_id": "chunk-001"}]}), encoding="utf-8")
        with patch("sys.argv", ["analyze_chunks.py", str(manifest_path)]), patch.object(analyze_chunks, "authorized_token", return_value="test"), patch.object(analyze_chunks, "ensure_original_uploaded", return_value="existing-job"), patch.object(analyze_chunks, "analyze_one", return_value={"status": "cached"}) as recover, patch.object(analyze_chunks, "complete_task", return_value={"status": "completed"}) as finish:
            analyze_chunks.main()
            recover.assert_called_once()
            finish.assert_called_once()
        assert not (root / "report.md").exists(), "Model completion must not fabricate a customer report"
    print("CineSleuth runtime smoke test passed")


if __name__ == "__main__":
    main()
