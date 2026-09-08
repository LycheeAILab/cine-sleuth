"""Offline platform routing/URL safety; no third-party media downloaded."""
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch
root = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(root / "desktop/scripts"), str(root / "plugins/cine-sleuth/skills/cine-sleuth/scripts")]
import link_sources as links
from yt_dlp import YoutubeDL

samples = [("https://v.douyin.com/test/", "douyin"), ("https://www.bilibili.com/video/BV1xx411c7mD", "bilibili"),
           ("https://b23.tv/test", "bilibili"), ("https://www.youtube.com/watch?v=BaW_jenozKc", "youtube"),
           ("https://youtu.be/BaW_jenozKc", "youtube"), ("https://www.youtube.com/shorts/BaW_jenozKc", "youtube")]
for url, platform in samples:
    assert links.resolve_link("分享 " + url + "。") == (url, platform)
for bad in ["https://youtube.com.evil.test/watch?v=x", "https://localhost/x", "https://u:p@b23.tv/x", "http://b23.tv/x",
            "https://youtu.be:bad/x", "https://www.youtube.com/playlist?list=x", "https://www.bilibili.com/"]:
    try: links.resolve_link(bad)
    except links.source.SourceError: pass
    else: raise AssertionError(bad)
with tempfile.TemporaryDirectory() as directory:
    output = Path(directory) / "source.mp4"
    with patch.object(links.source, "download_douyin", return_value=(output,"direct")) as direct:
        assert links.download_link(samples[0][0], output)[1] == "direct"
        assert direct.call_count == 1
    for url, platform in [samples[1], samples[3]]:
        output.write_bytes(b"fixture")
        def extract(self, incoming, download):
            assert incoming == url and download is True
            assert self.params["noplaylist"] and self.params["playlistend"] == 1
            assert not self.params.get("cookiesfrombrowser")
            try: self.params["match_filter"]({"duration":301})
            except links.source.SourceError: pass
            else: raise AssertionError("duration guard missing")
            return {"id":"test", "ext":"mp4", "filepath":str(output)}
        with patch.object(YoutubeDL,"extract_info",extract), patch.object(links.source,"validate_video",lambda p:p):
            assert links.download_link(url,output) == (output,"yt-dlp-"+platform)
print("PASS: Douyin/Bilibili/YouTube dispatch, HTTPS/domain guards, single-video and duration boundaries")
