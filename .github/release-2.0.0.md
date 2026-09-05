# CineSleuth 2.0.0

## 新增

- 支持有授权的抖音视频分享链接：复用 Avatar Forge 的独立下载组件，提供备用下载路径；本地视频输入保持兼容。
- 最终 Agent 拉片报告可为每个 seg 提取原片首帧，和分析、视频生成提示词一起展示。
- 同时交付图片内嵌的 HTML、Markdown 图片包、首帧时间点索引，以及可选归档用的纯文字报告。
- Codex Plugin 和 WorkBuddy 自包含 Skill ZIP 同步更新。

## 保持不变

- 原始模型结果、Lab 认证、任务完成规则和五分钟视频上限不变。
- 图文报告生成在本地完成，不额外调用模型；Agent 最终报告是否归档由用户选择。
- 链接功能仅面向公开可获取且用户有权使用的抖音视频，不绕过平台权限；下载受平台可用性影响，失败时仍可使用本地视频。

## 升级

Codex 用户升级插件后新建会话。WorkBuddy 用户下载本 Release 的 ZIP，或按仓库 `WORKBUDDY_INSTALL.md` 安装；安装器验证 SHA-256。
依赖更新：运行 Skill 目录中的 `python -m pip install -r requirements.txt`，并确保 FFmpeg/ffprobe 在 PATH。

## 验证范围

本地真实 FFmpeg/VFR 首帧、HTML 内嵌图片、时间/素材一致性、下载备用路径模拟、原有网关模拟、分发一致性与静态校验通过。本次未使用用户视频调用付费分析接口，也未对未提供的抖音链接进行实际下载测试。

项目自身代码为 MIT；独立 DouK 下载组件随包提供 GPL-3.0-only 源码、License 和 Notice。
