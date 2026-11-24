import ast
import importlib.util
import os
import tempfile
import pathlib
import unittest
from unittest import mock


def _load_function(name):
    module_path = pathlib.Path(__file__).resolve().parents[1] / "modules" / "youtube_handler.py"
    source = module_path.read_text(encoding="utf-8")
    module_ast = ast.parse(source, filename=str(module_path))
    selected = [
        node for node in module_ast.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    ]
    isolated_module = ast.Module(body=selected, type_ignores=[])
    namespace = {"Any": object}
    exec(compile(isolated_module, str(module_path), "exec"), namespace)
    return namespace[name]


class YouTubeSubtitleDownloadOptionsTests(unittest.TestCase):
    def test_returns_no_write_subs_when_subtitles_disabled(self):
        build_args = _load_function("_build_subtitle_download_args")

        args = build_args({}, include_subtitles=False)

        self.assertEqual(args, ["--no-write-subs"])

    def test_returns_no_write_subs_when_auto_gen_disabled(self):
        """YOUTUBE_AUTO_GENERATED_SUBTITLES_ENABLED 默认 False，不下载字幕"""
        build_args = _load_function("_build_subtitle_download_args")

        args = build_args({}, include_subtitles=True)

        self.assertEqual(args, ["--no-write-subs"])

    def test_includes_auto_generated_subtitle_flag_when_enabled(self):
        build_args = _load_function("_build_subtitle_download_args")

        args = build_args(
            {"YOUTUBE_AUTO_GENERATED_SUBTITLES_ENABLED": True},
            include_subtitles=True,
        )

        self.assertIn("--write-auto-subs", args)
        self.assertEqual(args[:-1], ["--write-subs", "--all-subs", "--convert-subs", "srt"])


class YouTubeJsRuntimeOptionsTests(unittest.TestCase):
    def test_prefers_deno_and_keeps_node_as_fallback(self):
        detect_args = _load_function("_detect_js_runtime_args")
        detect_args.__globals__["_which"] = mock.Mock(
            side_effect=lambda runtime: f"/{runtime}" if runtime in {"deno", "node"} else None
        )

        self.assertEqual(
            detect_args(),
            ["--js-runtimes", "deno", "--js-runtimes", "node"],
        )

    def test_uses_deno_when_node_is_unavailable(self):
        detect_args = _load_function("_detect_js_runtime_args")
        detect_args.__globals__["_which"] = mock.Mock(
            side_effect=lambda runtime: "/deno" if runtime == "deno" else None
        )

        self.assertEqual(detect_args(), ["--js-runtimes", "deno"])

    def test_uses_node_when_deno_is_unavailable(self):
        detect_args = _load_function("_detect_js_runtime_args")
        detect_args.__globals__["_which"] = mock.Mock(
            side_effect=lambda runtime: "/node" if runtime == "node" else None
        )

        self.assertEqual(detect_args(), ["--js-runtimes", "node"])

    def test_returns_no_args_without_a_runtime(self):
        detect_args = _load_function("_detect_js_runtime_args")
        detect_args.__globals__["_which"] = mock.Mock(return_value=None)

        self.assertEqual(detect_args(), [])


class LocalLauncherRuntimeTests(unittest.TestCase):
    def setUp(self):
        path = pathlib.Path(__file__).resolve().parents[2] / "launch.py"
        if not path.is_file():
            self.skipTest("local deployment launcher is absent")
        spec = importlib.util.spec_from_file_location("local_y2a_launcher", path)
        self.launcher = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.launcher)

    def test_restores_runtime_with_a_minimal_service_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.launcher.BASE = pathlib.Path(tmp)
            node = self.launcher.BASE / "venv/bin/node"
            node.parent.mkdir(parents=True)
            node.touch(mode=0o700)
            with mock.patch.dict(os.environ, {"PATH": tmp}):
                self.launcher.configure_youtube_runtime()
                self.assertEqual(self.launcher.shutil.which("node"), str(node))
                path = os.environ["PATH"]
                self.launcher.configure_youtube_runtime()
                self.assertEqual(os.environ["PATH"], path)

    def test_preserves_existing_runtime(self):
        with mock.patch.dict(os.environ, {"PATH": "/existing"}):
            with mock.patch.object(self.launcher.shutil, "which", return_value="/existing/deno"):
                self.launcher.configure_youtube_runtime()
            self.assertEqual(os.environ["PATH"], "/existing")


if __name__ == "__main__":
    unittest.main()
