"""Launch the local Y2A-Auto workbench."""
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

BASE = Path(__file__).resolve().parent
SOURCE = BASE / 'source'
PIDFILE = BASE / 'service.json'
URL = 'http://127.0.0.1:18765/'


def owned(pid):
    if type(pid) is not int or pid <= 0:
        return False
    if os.name == 'nt':
        command = [
            'powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
            f"(Get-CimInstance Win32_Process -Filter 'ProcessId = {pid}').CommandLine",
        ]
    else:
        command = ['/bin/ps', '-p', str(pid), '-o', 'command=']
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return False
    line = result.stdout.strip()
    script = str(BASE / 'launch.py')
    if os.name == 'nt':
        line, script = line.casefold(), script.casefold()
    return result.returncode == 0 and line.endswith((script + ' serve', f'"{script}" serve'))


def configure_youtube_runtime():
    portable = BASE / 'bin'
    suffix = '.exe' if os.name == 'nt' else ''
    directories = []
    for tool in ('node', 'ffmpeg'):
        for directory in (portable / tool, portable / tool / 'bin', portable):
            if (directory / (tool + suffix)).is_file() and directory not in directories:
                directories.append(directory)
    if directories:
        original = (os.environ.get('PATH') or os.defpath).split(os.pathsep)
        preferred = [str(path) for path in directories]
        os.environ['PATH'] = os.pathsep.join(preferred + [path for path in original if path not in preferred])

    # Keep the existing macOS system and local Node fallbacks.
    if os.name != 'nt' and not (shutil.which('node') or shutil.which('deno')):
        candidates = (
            BASE / 'venv/bin/node',
            Path('/opt/homebrew/bin/node'),
            Path('/usr/local/bin/node'),
            Path.home() / '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node',
        )
        for node in candidates:
            if node.is_file() and os.access(node, os.X_OK):
                os.environ['PATH'] = os.pathsep.join((str(node.parent), os.environ['PATH']))
                break


def serve():
    configure_youtube_runtime()
    os.chdir(SOURCE)
    sys.path.insert(0, str(SOURCE))
    os.umask(0o077)
    import app as application

    runtime = application.initialize_application()

    def stop(*_):
        raise KeyboardInterrupt()

    signal.signal(signal.SIGTERM, stop)
    try:
        application.app.run(host='127.0.0.1', port=18765, debug=False, use_reloader=False)
    finally:
        application.shutdown_application(runtime)


def open_when_ready(process=None):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if process is not None and process.poll() is not None:
            raise SystemExit('启动失败，请查看 source/logs/launcher.log。')
        try:
            with opener.open(URL, timeout=1) as response:
                if response.status == 200:
                    print(URL, flush=True)
                    try:
                        if not webbrowser.open(URL):
                            print('无法自动打开浏览器，请手动访问上方地址。')
                    except (OSError, webbrowser.Error):
                        print('无法自动打开浏览器，请手动访问上方地址。')
                    return
        except urllib.error.HTTPError:
            pass
        except OSError:
            pass
        time.sleep(0.2)
    raise SystemExit('工作台启动后未能就绪，请查看 source/logs/launcher.log。')


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else 'start'
    if action == 'serve':
        serve()
        return
    if action not in {'start', 'stop'}:
        raise SystemExit('Usage: launch.py [start|stop]')

    try:
        pid = json.loads(PIDFILE.read_text(encoding='utf-8')).get('pid') if PIDFILE.exists() else None
    except (OSError, ValueError, AttributeError):
        pid = None
    running = owned(pid)
    if action == 'stop':
        if running:
            os.kill(pid, signal.SIGTERM)
            print('工作台已停止。')
        else:
            print('未找到此便携包启动的工作台。')
        return
    if running:
        open_when_ready()
        return
    with socket.socket() as sock:
        sock.settimeout(1)
        if sock.connect_ex(('127.0.0.1', 18765)) == 0:
            raise SystemExit('18765 端口已被占用，请关闭占用该端口的应用后重试。')

    venv_python = BASE / ('venv/Scripts/python.exe' if os.name == 'nt' else 'venv/bin/python')
    python = str(venv_python) if venv_python.is_file() else sys.executable
    platform_options = {'creationflags': subprocess.DETACHED_PROCESS} if os.name == 'nt' else {'start_new_session': True}
    log_dir = SOURCE / 'logs'
    log_dir.mkdir(exist_ok=True)
    with (log_dir / 'launcher.log').open('ab') as log_file:
        process = subprocess.Popen(
            [python, str(BASE / 'launch.py'), 'serve'],
            cwd=SOURCE, stdin=subprocess.DEVNULL, stdout=log_file,
            stderr=subprocess.STDOUT, **platform_options,
        )
    PIDFILE.write_text(json.dumps({'pid': process.pid, 'url': URL}), encoding='utf-8')
    if os.name != 'nt':
        PIDFILE.chmod(0o600)
    open_when_ready(process)


if __name__ == '__main__':
    main()
