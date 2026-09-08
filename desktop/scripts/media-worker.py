"""Desktop media-only worker. Receives no Lab or model credentials."""
import contextlib
import json
import os
from pathlib import Path
import subprocess
import sys

for stream in (sys.stdin, sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

# Media subprocesses must not open console windows in the desktop app.
if os.name == "nt":
    class HiddenPopen(subprocess.Popen):
        def __init__(self, *args, **kwargs):
            kwargs.setdefault("creationflags", 0x08000000)
            super().__init__(*args, **kwargs)
    subprocess.Popen = HiddenPopen

SOURCE = Path(__file__).resolve().parents[2] / "plugins/cine-sleuth/skills/cine-sleuth/scripts"
if SOURCE.exists():
    sys.path.insert(0, str(SOURCE))
    sys.path.insert(0, str(SOURCE / "douk_downloader"))

import prepare_video
import prepare_video_source


def direct(url, output):
    if getattr(sys, "frozen", False):
        command = [sys.executable, "--douk", url, str(output)]
    else:
        command = [sys.executable, str(Path(__file__).resolve()), "--douk", url, str(output)]
    child = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600, creationflags=0x08000000 if os.name == "nt" else 0)
    if child.returncode:
        raise prepare_video_source.SourceError(child.stderr.strip()[-1000:] or "链接取片失败")
    return prepare_video_source.validate_video(Path(json.loads(child.stdout)["video"]))


def main():
    if len(sys.argv)>1 and sys.argv[1]=="--douk":
        import download
        print(json.dumps(download.run(sys.argv[2], Path(sys.argv[3]), 30)))
        return
    request = json.load(sys.stdin)
    output = Path(request["outputDir"]).resolve()
    output.mkdir(parents=True, exist_ok=True)
    prepare_video_source.download_with_douk_direct = direct
    if request.get("url"):
        cached = output / "source.mp4"
        if cached.is_file():
            source = prepare_video_source.validate_video(cached)
        else:
            source, _ = prepare_video_source.download_douyin(request["url"], cached)
    else:
        source = prepare_video_source.validate_video(Path(request["video"]))
    if source.stat().st_size > 5*1024**3:
        raise ValueError("原视频不能超过 5 GB")
    sys.argv=["prepare_video",str(source),"--output-dir",str(output),"--vad","silence"]
    with contextlib.redirect_stdout(sys.stderr):
        prepare_video.main()
    print(json.dumps({"manifest":str(output / "manifest.json")}))


if __name__=="__main__":
    try:
        main()
    except (Exception,SystemExit) as error:
        if isinstance(error,SystemExit) and error.code in (None,0):
            raise
        print(str(error),file=sys.stderr)
        sys.exit(1)
