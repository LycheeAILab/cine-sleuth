# CineSleuth WorkBuddy installation guide

This is an execution guide for WorkBuddy. When a user asks to install CineSleuth, perform the installation rather than merely describing it.

## Safety gate

- Install release `0.1.0` from `LycheeAILab/cine-sleuth`.
- Verify the ZIP against `dist/SHA256SUMS`.
- Back up an existing installation instead of deleting it.
- Run only the local doctor after installation; do not upload a real video.

## Windows

```powershell
$script = Join-Path $env:TEMP "install-cine-sleuth-workbuddy.ps1"
Invoke-WebRequest "https://raw.githubusercontent.com/LycheeAILab/cine-sleuth/main/install-workbuddy.ps1" -OutFile $script
powershell -ExecutionPolicy Bypass -File $script -Version "0.1.0"
```

## macOS or Linux

```bash
script="$(mktemp)"
curl -fsSL "https://raw.githubusercontent.com/LycheeAILab/cine-sleuth/main/install-workbuddy.sh" -o "$script"
sh "$script" "0.1.0"
```

## Verify in WorkBuddy

Reload WorkBuddy or start a new conversation. Confirm `cine-sleuth` appears in installed Skills, then run its bundled `scripts/doctor.py`. Setup succeeds only when doctor reports version `0.1.0` and `ok: true`.

Runtime service configuration is separate from installation. Never put credentials in project files, Skills, installation logs, or chat messages.

