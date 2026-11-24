# 构建 Windows 便携包

在有 Python 3.12 与 Git 的 **Windows 构建机**上执行。源码取自当前 `HEAD`，先提交要发布的改动。运行时从工作目录里新准备的 `venv/` 和 `bin/` 取得。

1. 将 [Windows Python 3.12 嵌入式发行包](https://www.python.org/downloads/windows/) 解压到 `venv/Scripts/`，选择与目标机器一致的架构。保留 `python.exe`、`python312.dll`、`python312.zip` 和运行时许可证。编辑 `venv/Scripts/python312._pth`，保留原来的路径行，加上 `..\Lib\site-packages`，并取消 `import site` 的注释。
2. 在同架构的 Windows 构建机，使用本机安装的 Python 3.12 安装依赖到便携目录。

   ```powershell
   py -3.12 -m pip install --only-binary=:all: -r source/requirements.txt --target .\venv\Lib\site-packages
   ```

   普通 `python -m venv` 会引用创建环境的机器路径。请使用干净的嵌入式运行时目录，并让 pip 与嵌入式 Python 的架构一致。

3. 将同架构的 Windows `node.exe`、`ffmpeg.exe`、`ffprobe.exe` 放到 `bin/`，附上各发行包的许可证和再分发所需文件。准备 FFmpeg 构建对应的源码获取方式，并在 Release 说明里列出 Python、Node.js 和 FFmpeg 的版本与来源。
4. 在仓库根目录执行以下单条命令。

   ```powershell
   py -3.12 tools/package_windows.py Y2A-Auto-Windows-portable.zip
   ```

   打包器从提交中导出 `source/`、`launch.py`、`一键启动.bat`、`README.md` 和 `LICENSE`，加入运行时，在临时目录测试 Python 依赖、Node.js、FFmpeg 和 FFprobe 后生成 ZIP。运行时配置、Cookie、数据库、日志、媒体和 `service.json` 均被排除。请用干净的 Windows 环境解压后双击启动，确认设置页自检、两种模型的测试连接和关闭后再启动，再把 ZIP 附到 GitHub Releases。
