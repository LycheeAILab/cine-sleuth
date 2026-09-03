# CineSleuth WorkBuddy installation guide

This is an execution guide for WorkBuddy. When a user asks to install CineSleuth, perform the installation rather than merely describing it.

## Safety gate

- Install release `1.0.0` from `LycheeAILab/cine-sleuth`.
- Verify the ZIP against `dist/SHA256SUMS`.
- Back up an existing installation instead of deleting it.
- Run only the local doctor after installation; do not upload a real video.

## Windows

```powershell
$script = Join-Path $env:TEMP "install-cine-sleuth-workbuddy.ps1"
Invoke-WebRequest "https://raw.githubusercontent.com/LycheeAILab/cine-sleuth/main/install-workbuddy.ps1" -OutFile $script
powershell -ExecutionPolicy Bypass -File $script -Version "1.0.0"
```

## macOS or Linux

```bash
script="$(mktemp)"
curl -fsSL "https://raw.githubusercontent.com/LycheeAILab/cine-sleuth/main/install-workbuddy.sh" -o "$script"
sh "$script" "1.0.0"
```

## Verify in WorkBuddy

Reload WorkBuddy or start a new conversation. Confirm `cine-sleuth` appears in installed Skills, run `scripts/lab_auth.py` to authorize through LycheeAILab, then run `scripts/doctor.py`. Setup succeeds only when doctor reports version `1.0.0`, `authenticated: true`, and `runtime_ready: true`.

The local installation stores only the user's revocable Lab credential. No underlying service credential is requested, displayed, or stored by the Skill.
