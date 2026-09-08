# 镜探 Windows 桌面端 · 0.1.0 Preview

本阶段实现：Lab 浏览器授权 → 本地视频或抖音链接取片 → 原视频上传 → 分段模型分析 → 云端结果与历史 → JSON 导出。用户 Agent、跨段报告整理、分镜首帧及最终报告归档未接入。

桌面端使用独立设备凭据，不读取或更改 Skill 的个人 API Key。客户端只访问正式 Lab；模型服务商密钥保留在 Lab 后端。

## 使用

1. 配套 Lab 更新部署完成后，运行 `release/CineSleuth-0.1.0-Windows-x64-Setup.exe` 安装。
2. 点击“登录 LycheeAILab”，在系统浏览器登录并授权，返回桌面端。
3. 选择最长 5 分钟的本地视频，或粘贴有权使用的抖音分享链接。确认云端上传后开始分析。
4. 查看本机进度及模型结果。失败或重启后点击“继续”，已完成的云端片段会跳过。暂停本地流程不会取消已经提交到 Lab 的模型请求。
5. “分析历史”读取当前 Lab 账号的 CineSleuth 任务；“导出 JSON”保存原始模型结果。

2026-09-08，配套 Lab `0.4.3-prod`（`dc43ff7`）已部署正式环境，可使用正式站点登录。

## 构建

构建机需要 Node.js、npm、Python 和网络；安装包内含独立媒体运行环境，用户无需安装 Python 或 FFmpeg。

```powershell
cd desktop
npm install
npm run runtime
npm test
node tests/media-smoke.cjs
npm run dist
```

Electron 的 Node 下载器在某些网络中不可用时，可运行 `scripts/install-electron.ps1`。它会以 npm 包内置 SHA-256 校验镜像文件。FFmpeg 构建脚本从 Gyan 获取当前 release essentials 并验证发布方校验和，保存版本及许可；正式发布应固定归档和校验和以保证重建一致性。

开发启动：`npm start`。本地 Lab 联调可在未打包开发模式设置 `CINESLEUTH_LAB_URL=http://127.0.0.1:3000`，对应后端设置相同的 `LAB_PUBLIC_ORIGIN`。打包版本拒绝将 API 地址改为其他域名或本地地址。

界面验证脚本 `tests/ui-smoke.cjs` 使用 Playwright，可通过 `CINE_PLAYWRIGHT` 指向已有安装。脚本采用模拟接口，不能替代真实 Lab 联调。

## Lab 配套变更

工作区相邻的 `lycheeailab-0.3.3` 包含本版本所需代码：

- 新增 `/desktop-authorize`，复用 Lab 密码、短信和注册表单；`/desktop-devices` 查看并撤销设备。
- 新增 `/api/desktop-auth/authorize|token|me|logout|devices`；授权码 90 秒、访问凭据 10 分钟、设备授权最长 30 天。PKCE S256，一次性交换、刷新轮换、重复刷新撤销该设备。
- API 启动迁移自动创建三张 `desktop_*` 表，不修改现有 `api_keys` 或网页 `sessions`。
- 原有 CineSleuth 接口接受桌面凭据；任务 `source_id` 保留 `cine-sleuth`，在 `input_payload.entryPoint` 写入 `desktop` 及已认证 `desktopDeviceId`。
- 新增 `GET /api/cine-sleuth/jobs?before=...` 和 `GET /api/cine-sleuth/jobs/:id/model-results`。所有读取按登录用户检查归属。
- 分析、云端模型存档及任务完成继续调用已有服务。客户端不会调用报告归档接口，不新增模型提供商或客户端计费逻辑。

后端 `LAB_PUBLIC_ORIGIN` 默认 `https://lab.lycheeai.com.cn`。授权和设备撤销校验该精确来源，不依赖客户端传来的 host。

## 本地数据

Electron 用户数据目录中，`desktop-session.enc` 用 Windows DPAPI 加密保存设备凭据；主进程负责访问，渲染页面不接触凭据。`tasks/<userId>/<taskId>` 保存任务、代理片段及模型结果，账号之间隔离。退出当前设备会先请求 Lab 撤销；网络不可用时提示失败，保留凭据供稍后重试，也可在 Lab 的设备页面远程撤销。

## 验证范围与发布状态

已完成客户端鉴权及调用流程单测、模拟接口的本地／链接完整流程和断点恢复测试、实际打包媒体运行环境测试、1220/980 像素界面检查；Lab API 和 Web 构建通过。

2026-09-08 已使用临时测试账号完成正式 Lab 浏览器密码登录、PKCE 授权、刷新及设备撤销；使用一段 4 秒自制视频，经过安装包内同版媒体运行环境，完成真实 COS 上传、Lab 模型分析及云端结果保存。生产 MySQL 实测授权码并发一次消费、刷新重放撤销、设备归属及个人 API Key 不受影响；测试账号、任务和 COS 对象均已清理。抖音取片沿用现有两级下载器，尚未用真实抖音链接实测。

当前 Preview 安装包未配置代码签名；正式公开分发前需完成签名、干净 Windows 安装升级验证及第三方许可证／对应源代码交付核对。

第三方取片代码及其许可证随安装包保留，见仓库 `THIRD_PARTY_NOTICES.md`。FFmpeg 及 Python 依赖许可随运行环境交付。使用的 OAuth 登录设计依据 [RFC 8252](https://www.rfc-editor.org/info/rfc8252/) 和 [RFC 9700](https://www.rfc-editor.org/info/rfc9700/)。
