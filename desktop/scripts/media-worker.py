"""Desktop media-only worker. Receives no Lab or model credentials."""
import contextlib
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

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
import build_visual_report
import link_sources


def direct(url, output):
    if getattr(sys, "frozen", False):
        command = [sys.executable, "--douk", url, str(output)]
    else:
        command = [sys.executable, str(Path(__file__).resolve()), "--douk", url, str(output)]
    child = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120, creationflags=0x08000000 if os.name == "nt" else 0)
    if child.returncode:
        raise prepare_video_source.SourceError(child.stderr.strip()[-1000:] or "链接取片失败")
    return prepare_video_source.validate_video(Path(json.loads(child.stdout)["video"]))


def main():
    if len(sys.argv)>1 and sys.argv[1]=="--douk":
        import download
        print(json.dumps(download.run(sys.argv[2], Path(sys.argv[3]), 30)))
        return
    request = json.load(sys.stdin)
    if request.get("action") == "visual-report":
        result = build_visual_report.build(Path(request["video"]), Path(request["segments"]), Path(request["report"]), Path(request["outputDir"]))
        print(json.dumps(result, ensure_ascii=False))
        return
    output = Path(request["outputDir"]).resolve()
    output.mkdir(parents=True, exist_ok=True)
    prepare_video_source.download_with_douk_direct = direct
    if request.get("url"):
        try:
            link_sources.resolve_link(request["url"])
        except prepare_video_source.SourceError:
            raise ValueError("请输入抖音、Bilibili 或 YouTube 的 HTTPS 视频链接，或导入本地视频")
        cache_record = output / "resolved-source.json"
        cached = Path(json.loads(cache_record.read_text(encoding="utf-8"))["video"]) if cache_record.is_file() else output / "source.mp4"
        source = None
        if cached.is_file():
            try:
                source = prepare_video_source.validate_video(cached)
            except prepare_video_source.SourceError:
                pass
        if source is None:
            # Partial downloads from a failed attempt must not poison the next one.
            target = output / "link-attempts" / str(uuid4()) / "source.mp4"
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                source, _ = link_sources.download_link(request["url"], target)
            except (prepare_video_source.SourceError, OSError, subprocess.TimeoutExpired) as error:
                if "no longer than 5 minutes" in str(error):
                    raise ValueError("视频不能超过 5 分钟，请换一条视频")
                print(json.dumps({"code":"LINK_RESOLUTION_FAILED","message":"链接暂时解析失败"}), file=sys.stderr)
                sys.exit(2)
            cache_record.write_text(json.dumps({"video":str(source)}), encoding="utf-8")
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
