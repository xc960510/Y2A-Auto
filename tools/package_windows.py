"""Build a Windows portable ZIP from committed source and a clean runtime."""
import argparse
import os
from itertools import chain
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ENTRIES = ('source', 'launch.py', '一键启动.bat', 'README.md', 'LICENSE')
PRIVATE_DIRS = {
    '.git', '.backups', '__pycache__', '.pytest_cache', 'config', 'cookies',
    'db', 'logs', 'downloads', 'acfunid', 'demo_raw', 'security', 'temp',
}
PRIVATE_FILES = {'service.json', 'record_demo.py', 'qrcode.png', '.env', '.ds_store', 'thumbs.db'}
PRIVATE_SUFFIXES = {'.mp4', '.zip', '.log', '.key', '.p12', '.pfx', '.pyc'}
DATABASE = re.compile(r'\.(?:db|sqlite3?)(?:-(?:shm|wal|journal))?$', re.I)


def private_path(path):
    parts = [part.lower() for part in path.parts]
    name = parts[-1]
    return (
        any(part in PRIVATE_DIRS or part.startswith('._') for part in parts)
        or name in PRIVATE_FILES or name.startswith('.env.')
        or Path(name).suffix in PRIVATE_SUFFIXES or bool(DATABASE.search(name))
        # Some Python packages ship public CA bundles in PEM format.
        or (name.endswith('.pem') and name not in {'cacert.pem', 'ca-bundle.pem'})
    )


def copy_runtime(source, destination):
    def excluded(relative):
        # The official embedded Python standard library is a required ZIP.
        if destination.name == 'venv' and relative.as_posix() == 'Scripts/python312.zip':
            return False
        return private_path(relative)

    def ignore(directory, names):
        relative = Path(directory).relative_to(source)
        return {name for name in names if excluded(relative / name)}

    for path in chain((source,), source.rglob('*')):
        relative = path.relative_to(source)
        if relative.parts and excluded(relative):
            continue
        info = path.lstat()
        if path.is_symlink() or getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise ValueError(f'运行时包含链接或重解析点，请改用独立文件：{path}')
    shutil.copytree(source, destination, ignore=ignore)


def export_source(staging, archive_path):
    subprocess.run(
        ['git', '-C', str(ROOT), 'archive', '--format=zip', '-o', str(archive_path),
         'HEAD', '--', *SOURCE_ENTRIES],
        check=True,
    )
    with ZipFile(archive_path) as archive:
        for entry in archive.infolist():
            path = PurePosixPath(entry.filename)
            if (
                path.is_absolute() or '..' in path.parts or private_path(path)
                or any(':' in part or '\\' in part for part in path.parts)
                or stat.S_ISLNK(entry.external_attr >> 16)
            ):
                raise ValueError(f'提交快照包含不应打包的条目：{entry.filename}')
        archive.extractall(staging)


def run_smoke_test(command, cwd):
    result = subprocess.run(
        command, cwd=cwd, capture_output=True, timeout=60, check=False,
    )
    if result.returncode:
        raise ValueError(f'在临时目录执行 {Path(command[0]).name} 失败（退出码 {result.returncode}）。')


def validate_windows_tools(staging):
    python = staging / 'venv/Scripts/python.exe'
    requirements = (
        (python, ['-I', '-c', 'import flask, openai, yt_dlp, silero_vad, apscheduler, curl_cffi']),
        (staging / 'bin/node.exe', ['--version']),
        (staging / 'bin/ffmpeg.exe', ['-version']),
        (staging / 'bin/ffprobe.exe', ['-version']),
    )
    runtime_files = ('python312.dll', 'python312.zip', 'python312._pth')
    if (
        (staging / 'venv/pyvenv.cfg').exists() or (python.parent / 'pyvenv.cfg').exists()
        or not all(python.with_name(name).is_file() for name in runtime_files)
    ):
        raise ValueError('请使用独立的 Windows Python 3.12 嵌入式运行时，普通 venv 依赖原机安装路径。')
    for executable, args in requirements:
        if not executable.is_file():
            raise ValueError(f'打包缺少 {executable.relative_to(staging)}')
        with executable.open('rb') as binary:
            if binary.read(2) != b'MZ':
                raise ValueError(f'{executable.name} 不是 Windows 可执行文件。')
        run_smoke_test([str(executable), *args], cwd=staging)


def build(output):
    if os.name != 'nt':
        raise ValueError('请在 Windows 上执行，以实测打包后的运行时。')
    for name in ('venv', 'bin'):
        if not (ROOT / name).is_dir():
            raise ValueError(f'请先准备 {name}/，见 RELEASE.md。')
    with tempfile.TemporaryDirectory(prefix='Y2A Release ') as temp:
        temp = Path(temp)
        staging = temp / 'portable'
        export_source(staging, temp / 'source.zip')
        for name in ('venv', 'bin'):
            copy_runtime(ROOT / name, staging / name)
        validate_windows_tools(staging)

        with tempfile.NamedTemporaryFile(dir=output.parent, suffix='.tmp', delete=False) as handle:
            temporary_zip = Path(handle.name)
        try:
            with ZipFile(temporary_zip, 'w', compression=ZIP_DEFLATED) as archive:
                for path in sorted(staging.rglob('*')):
                    if path.is_file():
                        archive.write(path, path.relative_to(staging).as_posix())
            with ZipFile(temporary_zip) as archive:
                if archive.testzip() is not None:
                    raise ValueError('ZIP 校验失败。')
            temporary_zip.replace(output)
        finally:
            temporary_zip.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path, help='输出 ZIP 路径')
    args = parser.parse_args()
    output = args.output.resolve()
    if output.suffix.lower() != '.zip':
        parser.error('输出文件必须使用 .zip 扩展名。')
    if output.is_relative_to(ROOT / 'bin') or output.is_relative_to(ROOT / 'venv'):
        parser.error('ZIP 输出请放到 bin/ 和 venv/ 以外。')
    try:
        build(output)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        parser.exit(1, f'打包失败：{exc}\n')
    print(output)


if __name__ == '__main__':
    main()
