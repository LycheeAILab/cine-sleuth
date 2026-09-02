# CineSleuth Codex Plugin installation guide

This is an execution guide for Codex agents. When a user asks to install or upgrade CineSleuth, perform the steps rather than merely describing them.

## Host gate

Installation must run in the Codex desktop app on the user's local machine. In a web or isolated cloud conversation, ask the user to open Codex desktop and paste:

> 阅读 https://raw.githubusercontent.com/LycheeAILab/cine-sleuth/main/INSTALL.md，帮我安装或升级 CineSleuth 插件并创建一个新任务。

## Install or upgrade

Locate the Codex CLI bundled with the desktop app. Verify it with `"<BUNDLED_CODEX>" --version`, then run:

```text
"<BUNDLED_CODEX>" plugin marketplace add https://github.com/LycheeAILab/cine-sleuth.git
"<BUNDLED_CODEX>" plugin marketplace list
"<BUNDLED_CODEX>" plugin list --marketplace cine-sleuth
"<BUNDLED_CODEX>" plugin add cine-sleuth@cine-sleuth
```

If the marketplace already exists, upgrade it before reinstalling:

```text
"<BUNDLED_CODEX>" plugin marketplace upgrade cine-sleuth
"<BUNDLED_CODEX>" plugin add cine-sleuth@cine-sleuth
```

Do not modify unrelated marketplaces, plugins, or Skills.

## Verify locally

Confirm `cine-sleuth@cine-sleuth` is installed and enabled at version `0.3.0`. Run the installed Skill's `scripts/lab_auth.py`; it opens the official LycheeAILab login and stores only the user's revocable Lab API Key. Then run `scripts/doctor.py`; it performs no media upload and must return `"version": "0.3.0"`, `"authenticated": true`, and `"runtime_ready": true`.

Do not upload a real video merely to test setup. Never request or expose the Gemini Router Key: it remains encrypted on the Lab server.

## Start a new task

New plugin Skills are available in a new Codex task. Create and open one with:

```text
CineSleuth 0.3.0 已安装、完成 LycheeAILab 授权并通过 doctor 验证。请使用 $cine-sleuth 分析我接下来提供的视频：默认输出逐句台词、物理场景、逐镜表、内容结构和视听分析；所有结论保留时间码，听不清或看不清的内容必须标记，不要猜测。长视频使用本地语音与镜头边界切分，并由当前 Agent 自己完成跨片段总结。
```

Installation is complete only after the plugin is verified and the new task is created.
