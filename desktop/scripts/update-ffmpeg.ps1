$ErrorActionPreference = 'Stop'
$desktopRoot = Split-Path $PSScriptRoot -Parent
$archive = Join-Path $desktopRoot '.build/ffmpeg-release-essentials.zip'
$extract = Join-Path $desktopRoot '.build/ffmpeg-release'
$runtimeRoot = Join-Path $desktopRoot 'runtime'
New-Item -ItemType Directory -Force (Split-Path $archive -Parent),$runtimeRoot | Out-Null
if (-not (Test-Path $archive)) {
  curl.exe --ssl-revoke-best-effort --fail --location --retry 2 --output $archive https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip
  if ($LASTEXITCODE -ne 0) { throw 'FFmpeg download failed' }
}
$expected = (curl.exe --ssl-revoke-best-effort --fail --silent --show-error --location https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip.sha256).Trim().Split(' ')[0]
if ($LASTEXITCODE -ne 0 -or $expected -notmatch '^[a-fA-F0-9]{64}$') { throw 'Cannot read FFmpeg checksum' }
$stream = [IO.File]::OpenRead($archive)
try {
  $sha256 = [Security.Cryptography.SHA256]::Create()
  try { $actual = ([BitConverter]::ToString($sha256.ComputeHash($stream))).Replace('-', '') }
  finally { $sha256.Dispose() }
} finally { $stream.Dispose() }
if ($actual -ne $expected.ToUpperInvariant()) { throw 'FFmpeg checksum mismatch' }
Expand-Archive -LiteralPath $archive -DestinationPath $extract -Force
$binaryRoot = Get-ChildItem -LiteralPath $extract -Directory | Select-Object -First 1
foreach ($binaryName in @('ffmpeg.exe','ffprobe.exe')) {
  Copy-Item -LiteralPath (Join-Path $binaryRoot.FullName "bin/$binaryName") -Destination (Join-Path $runtimeRoot $binaryName) -Force
}
Copy-Item -LiteralPath (Join-Path $binaryRoot.FullName 'LICENSE') -Destination (Join-Path $runtimeRoot 'FFMPEG-LICENSE.txt') -Force
Copy-Item -LiteralPath (Join-Path $binaryRoot.FullName 'README.txt') -Destination (Join-Path $runtimeRoot 'FFMPEG-README.txt') -Force
& (Join-Path $runtimeRoot 'ffmpeg.exe') -version | Set-Content (Join-Path $runtimeRoot 'ffmpeg-build.txt') -Encoding utf8
$expected | Set-Content (Join-Path $runtimeRoot 'ffmpeg-archive.sha256') -Encoding ascii
