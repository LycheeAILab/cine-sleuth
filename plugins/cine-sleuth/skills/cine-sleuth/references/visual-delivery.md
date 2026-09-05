# Link input and illustrated final delivery

## Video links

Support local videos and authorized HTTPS Douyin share/canonical links (including
share text), using Avatar Forge's separately invoked DouK-derived helper and
yt-dlp fallback. Do not promise arbitrary website support or bypass private/paid
content. Confirm source rights before downloading; retain one-time cloud-use
consent before analysis. Never read browser cookies/profiles.

Install this Skill's `requirements.txt`, then run:

```sh
python scripts/prepare_video_source.py --douyin-url "AUTHORIZED_SHARE_LINK_OR_TEXT" --output "C:/absolute/task/source.mp4"
```

Pass the returned `video` path to `prepare_video.py`. Downloads are bounded to
512 MiB and actual video duration to 300 seconds. On platform rejection request a
local video; do not bypass permissions. Resume with the existing file/manifest,
not another download or parent task. Local input is unchanged.

## Final report first frames

This is a local step AFTER the host Agent reasons about assembled evidence.
Do not change raw model results, prompts, evidence.json or Lab completion.
A **seg** is a final report visual segment/shot, NOT a technical analysis chunk.
Merge overlap duplicates; use GLOBAL source times (`global_start_seconds` and
`global_end_seconds`), not chunk-local `start`/`end`. Preserve uncertain boundaries.
Transcript-only reports do not require images.

Write `segments.json` with original `source.sha256` from manifest/evidence:

```json
{
  "source_sha256": "ORIGINAL_SOURCE_SHA256",
  "segments": [
    {"id": "seg-001", "start_seconds": 0, "end_seconds": 4.5, "title": "Opening"},
    {"id": "seg-002", "start_seconds": 4.5, "end_seconds": 9, "title": "Second shot"}
  ]
}
```

Author `report-draft.md` with the complete requested analysis and every shot's
video-generation prompt. Put exactly one `{{frame:seg-001}}` marker in that seg's
section; likewise for every other ID. Markers belong on standalone lines, outside
code blocks/tables. Do not ask another model to summarize or fabricate images.

```sh
python scripts/build_visual_report.py --video "C:/absolute/task/source.mp4" --segments "C:/absolute/task/segments.json" --report "C:/absolute/task/report-draft.md" --output-dir "C:/absolute/task/delivery"
```

Use a new/empty delivery directory. Hash, unique IDs, timestamps and one-to-one
markers are validated. Frames are the first original decoded frame at/after each
seg start, within its end; VFR uses actual timestamps. No later representative
frame or AI image substitution. Portrait aspect ratio is preserved.

Open `delivery/report.html` and inspect first/last seg and cut boundaries. Every
image must match its segment; fix the host inventory if needed, never raw model
output. Deliver self-contained HTML (embedded images), plus `report.md`, `frames/`
and `frames.json`. Markdown alone is not portable. Disclose missing evidence;
successful extraction cannot prove cloud analysis succeeded.

## Optional archive

Lab completes from model results independently. Final reports stay local unless
the user chooses archival. The existing archive endpoint accepts text/evidence,
not frame folders. For explicitly requested archival, publish a textual report
(`delivery/report-text.md`, without frame markers) and evidence; explain that illustrated HTML remains local.
Never publish broken relative image links or claim images were archived.
