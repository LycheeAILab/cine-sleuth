# Fallback for networks where Electron's Node downloader cannot reach its CDN.
# The mirror binary must match the checksum shipped in the pinned npm package.
$ErrorActionPreference = 'Stop'
$desktopRoot = Split-Path $PSScriptRoot -Parent
$electronRoot = Join-Path $desktopRoot 'node_modules/electron'
$version = (Get-Content -Raw (Join-Path $electronRoot 'package.json') | ConvertFrom-Json).version
$name = "electron-v$version-win32-x64.zip"
$archive = Join-Path $desktopRoot ".build/$name"
New-Item -ItemType Directory -Force (Split-Path $archive -Parent) | Out-Null
if (-not (Test-Path $archive)) {
  curl.exe --ssl-revoke-best-effort --fail --location --retry 2 --output $archive "https://npmmirror.com/mirrors/electron/$version/$name"
  if ($LASTEXITCODE -ne 0) { throw 'Electron download failed' }
}
$expected = (Get-Content -Raw (Join-Path $electronRoot 'checksums.json') | ConvertFrom-Json).$name
if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash -ne $expected) { throw 'Electron checksum mismatch' }
Expand-Archive -LiteralPath $archive -DestinationPath (Join-Path $electronRoot 'dist') -Force
[System.IO.File]::WriteAllText((Join-Path $electronRoot 'path.txt'), 'electron.exe')
