"""Desktop platform dispatch; never reads browser cookies or model credentials."""
import re
import shutil
from urllib.parse import urlparse
from pathlib import Path
import prepare_video_source as source

PLATFORMS = {"douyin": ("douyin.com", "iesdouyin.com"), "bilibili": ("bilibili.com", "b23.tv"), "youtube": ("youtube.com", "youtu.be")}

def resolve_link(text):
    for match in re.finditer(r'https?://[^\s"<>]+', text):
        candidate = match.group(0).rstrip("，。；！？、)]}")
        try:
            url = urlparse(candidate)
            host = (url.hostname or "").lower().rstrip(".")
            if url.scheme != "https" or url.username or url.password or url.port not in (None, 443):
                continue
            for platform, domains in PLATFORMS.items():
                if any(host == domain or host.endswith("." + domain) for domain in domains):
                    if platform == "youtube" and host != "youtu.be" and not (url.path == "/watch" or url.path.startswith(("/shorts/", "/live/", "/embed/"))):
                        continue
                    if platform == "bilibili" and host != "b23.tv" and not url.path.startswith("/video/"):
                        continue
                    return candidate, platform
        except ValueError:
            continue
    raise source.SourceError("请输入抖音、Bilibili 或 YouTube 的 HTTPS 单条视频链接")

def download_link(text, output):
    url, platform = resolve_link(text)
    if platform == "douyin":
        return source.download_douyin(url, output)
    from yt_dlp import YoutubeDL
    from yt_dlp.utils import DownloadError
    def limit(info, **kwargs):
        if (info.get("duration") or 0) > 300:
            raise source.SourceError("Source video must be no longer than 5 minutes.")
    options = {"outtmpl": str(output.with_suffix(".%(ext)s")), "format": "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b",
               "merge_output_format": "mp4", "noplaylist": True, "playlistend": 1, "quiet": True, "no_warnings": True,
               "socket_timeout": 30, "retries": 2, "max_filesize": 512 * 1024 * 1024, "match_filter": limit}
    node = shutil.which("node")
    if node:
        options["js_runtimes"] = {"node": {"path": node}}
    try:
        with YoutubeDL(options) as downloader:
            info = downloader.extract_info(url, download=True)
            if not isinstance(info, dict) or info.get("_type") in ("playlist", "multi_video"):
                raise source.SourceError("请使用单条视频链接，不支持播放列表")
            candidates = [output, Path(downloader.prepare_filename(info))]
            candidates += [Path(item["filepath"]) for item in info.get("requested_downloads", []) if item.get("filepath")]
            for candidate in candidates:
                if candidate.is_file():
                    return source.validate_video(candidate), "yt-dlp-" + platform
    except DownloadError as exc:
        raise source.SourceError("链接解析失败，可能受网络、平台或登录限制；可改用本地视频") from exc
    raise source.SourceError("未能获取可读取的视频文件")
