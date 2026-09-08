$ErrorActionPreference = 'Stop'
$desktopRoot = Split-Path $PSScriptRoot -Parent
$skillScripts = Join-Path (Split-Path $desktopRoot -Parent) 'plugins/cine-sleuth/skills/cine-sleuth/scripts'
$buildRoot = Join-Path $desktopRoot '.build'
$runtimeRoot = Join-Path $desktopRoot 'runtime'
New-Item -ItemType Directory -Force $buildRoot,$runtimeRoot | Out-Null
if (-not (Test-Path (Join-Path $buildRoot 'venv/Scripts/python.exe'))) {
  python -m venv (Join-Path $buildRoot 'venv')
  if ($LASTEXITCODE -ne 0) { throw 'Cannot create Python build environment' }
}
$buildPython = Join-Path $buildRoot 'venv/Scripts/python.exe'
& $buildPython -m pip install 'pyinstaller==6.16.0' 'requests==2.32.5' 'yt-dlp==2026.8.19'
if ($LASTEXITCODE -ne 0) { throw 'Cannot install runtime build dependencies' }
& $buildPython -m PyInstaller --noconfirm --clean --onedir --name cine-media --distpath $runtimeRoot --workpath (Join-Path $buildRoot 'pyinstaller') --specpath $buildRoot --paths $skillScripts --paths (Join-Path $skillScripts 'douk_downloader') --hidden-import download --hidden-import a_bogus --collect-all yt_dlp --exclude-module torch --exclude-module torchaudio --exclude-module silero_vad (Join-Path $PSScriptRoot 'media-worker.py')
if ($LASTEXITCODE -ne 0) { throw 'Cannot package media worker' }
& (Join-Path $PSScriptRoot 'update-ffmpeg.ps1')
& $buildPython -m pip freeze | Set-Content (Join-Path $runtimeRoot 'python-packages.txt') -Encoding utf8
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'media-worker.py') -Destination (Join-Path $runtimeRoot 'media-worker-source.py') -Force
$licensesRoot = Join-Path $runtimeRoot 'licenses'
New-Item -ItemType Directory -Force $licensesRoot | Out-Null
Get-ChildItem -LiteralPath (Join-Path $buildRoot 'venv/Lib/site-packages') -Directory -Filter '*dist-info' | ForEach-Object {
  $packageLicense = Join-Path $licensesRoot $_.Name
  New-Item -ItemType Directory -Force $packageLicense | Out-Null
  Get-ChildItem -LiteralPath $_.FullName -File -Recurse | Where-Object { $_.Name -match 'LICENSE|COPYING|NOTICE' } | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $packageLicense $_.Name) -Force
  }
}
$pythonBase = & $buildPython -c 'import sys; print(sys.base_prefix)'
Copy-Item -LiteralPath (Join-Path $pythonBase 'LICENSE.txt') -Destination (Join-Path $licensesRoot 'PYTHON-LICENSE.txt') -Force
