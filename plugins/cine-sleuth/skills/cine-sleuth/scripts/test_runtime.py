#!/usr/bin/env python3
"""No-network smoke tests for the CineSleuth Lab gateway client."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import analyze_chunks


class FakeResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        evidence = json.dumps({"shots": [{"start": 0, "end": 1}]})
        payload = {"candidates": [{"content": {"parts": [{"text": evidence}]}}]}
        return json.dumps(payload).encode("utf-8")


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
                "Inspect this chunk",
                video,
                12.0,
            )

    request = captured["request"]
    assert request.full_url == "https://lab.lycheeai.com.cn/api/cine-sleuth/analyze"
    assert request.headers["Authorization"] == "Bearer lych_live_test_user_credential"
    assert request.headers["Content-type"].startswith("multipart/form-data; boundary=")
    assert b"Inspect this chunk" in request.data
    assert b"mock-mp4" in request.data
    assert captured["timeout"] == 12.0
    assert result == {"shots": [{"start": 0, "end": 1}]}
    print("CineSleuth runtime smoke test passed")


if __name__ == "__main__":
    main()
