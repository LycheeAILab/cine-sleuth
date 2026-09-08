"""Offline regression: partial link downloads must not block a later attempt."""
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

worker_file = Path(__file__).resolve().parents[1] / "scripts/media-worker.py"
spec = importlib.util.spec_from_file_location("desktop_media_worker", worker_file)
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)
original_argv = sys.argv[:]
with tempfile.TemporaryDirectory(prefix="cine-link-test-") as folder:
    output = Path(folder)
    request = {"url":"https://v.douyin.com/test", "outputDir":folder}
    targets = []
    def download(url, target):
        targets.append(target)
        target.write_bytes(b"partial" if len(targets) == 1 else b"valid")
        if len(targets) == 1:
            raise worker.prepare_video_source.SourceError("test network failure")
        return target, "test"
    def run():
        sys.argv = [str(worker_file)]
        with patch.object(sys, "stdin", io.StringIO(json.dumps(request))), patch.object(sys, "stdout", io.StringIO()), patch.object(sys, "stderr", io.StringIO()):
            worker.main()
    with patch.object(worker.prepare_video_source, "download_douyin", download), patch.object(worker.prepare_video_source, "validate_video", lambda p:p), patch.object(worker.prepare_video, "main", lambda:None):
        try:
            run()
            raise AssertionError("failure must propagate")
        except SystemExit as error:
            assert error.code == 2
        run()
        assert targets[0] != targets[1]
        assert targets[0].read_bytes() == b"partial"
        run()
        assert len(targets) == 2, "successful resolution is cached without downloading again"
sys.argv = original_argv
print("PASS: isolated partial attempts, retryable failure marker, successful source reuse")
