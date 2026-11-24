# Y2A-Auto 开箱即用便携版

**海外视频本地化与 AI 双语字幕工作台。** 在本地浏览器中提交 YouTube 链接或使用频道、关键词监控，获取媒体和原字幕，也可用 Whisper 识别语音。工作台支持 AI 批量翻译与质检、字幕烧录、中文标题和简介生成，以及投稿前的人工审核。

## 便携版增加了什么

1. Windows 下双击 `一键启动.bat`，启动器会优先使用便携包 `bin/` 内置的 Node.js 和 FFmpeg，工作台就绪后自动打开 [本地工作台](http://127.0.0.1:18765/)。
2. 设置页顶部的环境自检栏检查 FFmpeg、Node.js、yt-dlp 版本和 AI API Key 填写状态。
3. 新配置预置 OpenAI 兼容接口，投稿文案默认用 `claude-sonnet`，字幕翻译默认用 `gpt-4o-mini`。Base URL、Key 和模型都可以修改，提交设置前即可测试当前填写的配置。
4. AI 翻译遇到 401、402、429 或请求超时时，任务页会显示中文原因，例如 Key 无效、余额或额度不足、请求过频，或网络超时。

## 演示视频

<!-- 在此拖入 demo_output.mp4 -->

## 三步上手

1. 在仓库右侧 **Releases** 下载最新的 Windows 绿色便携包并完整解压。开发者也可以克隆仓库，按下文从源码启动。
2. 双击 `一键启动.bat`，等待浏览器打开工作台。
3. 打开「设置」，查看顶部环境状态。在 AI 端点配置里填入自己的 Key，也可点「获取 Key」前往默认中转站的申请页。可以换成其他 OpenAI 兼容接口。点击对应模型旁的「测试连接」，成功后保存设置。

## 常见问题

- **18765 端口被占用怎么办？** 退出占用该端口的应用，再双击启动脚本。已运行本工作台时，可直接打开 [本地工作台](http://127.0.0.1:18765/)。
- **YouTube 下载失败怎么办？** 检查设置里的下载代理是否开启、地址是否正确，并查看 yt-dlp 和 Node.js 状态。监控接口和媒体下载各有代理配置，监控正常时也要单独检查下载代理。
- **AI 报错 401 或 402 怎么处理？** 401 检查 Key 是否有效、是否属于当前 Base URL、是否有模型权限。402 检查中转站账户的余额或额度，处理后重新测试连接。

## 从源码启动

准备 Python 3.12、Node.js 和 FFmpeg，确认 Node.js 与 FFmpeg 在 PATH 中。在仓库根目录执行：

```bash
python -m venv venv
# macOS / Linux
./venv/bin/python -m pip install -r source/requirements.txt
./venv/bin/python launch.py start
```

在 Windows PowerShell 中创建虚拟环境后，使用 `./venv/Scripts/python.exe -m pip install -r source/requirements.txt` 安装依赖，再双击 `一键启动.bat`。从源码创建的普通虚拟环境适合本机开发。发布团队如需构建可搬移的 Windows 便携包，请参阅 [Windows Release 打包说明](RELEASE.md)。

## 开源协议与上游致谢

本项目基于 [fqscfqj/Y2A-Auto](https://github.com/fqscfqj/Y2A-Auto) 二次改造，沿用 **GNU GPL v3** 并保留原版 [LICENSE](LICENSE)。可在 [上游基线提交](https://github.com/fqscfqj/Y2A-Auto/tree/82f99a2dde5e309da9b56019e37fed8e39f5a9af) 查看原始源码。
