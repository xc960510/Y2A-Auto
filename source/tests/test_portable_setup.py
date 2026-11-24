"""Regression checks for portable setup and the settings probes."""
import importlib.util
import os
from pathlib import Path
import shutil
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import app as web_app
from modules import ai_fallback_client, config_manager, ffmpeg_manager, youtube_handler


class PortableSettingsTests(unittest.TestCase):
    def setUp(self):
        self.client = web_app.app.test_client()
        with self.client.session_transaction() as session:
            session['csrf_token'] = 'test-csrf'
        self.headers = {'X-CSRF-Token': 'test-csrf'}

    def test_new_config_defaults_and_existing_key_destination(self):
        defaults = config_manager.DEFAULT_CONFIG
        self.assertEqual(defaults['OPENAI_BASE_URL'], 'https://agent.hbziyuan.xyz/whaleai/v1')
        self.assertEqual(config_manager.API_KEY_PORTAL_URL, 'https://agent.hbziyuan.xyz/whaleai')
        self.assertEqual(defaults['OPENAI_MODEL_NAME'], 'claude-sonnet')
        self.assertEqual(defaults['SUBTITLE_OPENAI_MODEL_NAME'], 'gpt-4o-mini')
        self.assertFalse(defaults['OPENAI_API_KEY'])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'config.json'
            path.write_text('{"OPENAI_API_KEY":"existing-test-key"}', encoding='utf-8')
            with patch.object(config_manager, 'get_app_subdir', return_value=tmp):
                existing = config_manager.load_config()
        self.assertEqual(existing['OPENAI_BASE_URL'], 'https://api.openai.com/v1')
        self.assertEqual(existing['SUBTITLE_OPENAI_MODEL_NAME'], '')

    def test_connection_requires_csrf_even_without_password_protection(self):
        with patch.object(web_app, 'load_config', return_value={}):
            response = self.client.post('/api/test_ai_connection', json={})
        self.assertEqual(response.status_code, 403)

    def test_connection_uses_unsaved_form_and_returns_public_message(self):
        form = {
            'base_url': 'https://relay.example/v1', 'api_key': 'test-key',
            'model': 'custom-model',
        }
        error = TimeoutError('private diagnostic must never reach the page')
        with (
            patch.object(web_app, 'load_config', return_value={}),
            patch.object(ai_fallback_client, 'probe_ai_connection', side_effect=error) as probe,
        ):
            response = self.client.post('/api/test_ai_connection', json=form, headers=self.headers)
        probe.assert_called_once_with(form['base_url'], form['api_key'], form['model'])
        self.assertFalse(response.json['success'])
        self.assertIn('超时', response.json['message'])
        self.assertNotIn(str(error), response.get_data(as_text=True))

    def test_connection_success_reports_response_from_selected_model(self):
        form = {
            'base_url': 'https://relay.example/v1/responses', 'api_key': 'test-key',
            'model': 'subtitle-test-model',
        }
        with (
            patch.object(web_app, 'load_config', return_value={}),
            patch.object(ai_fallback_client, 'probe_ai_connection') as probe,
        ):
            response = self.client.post('/api/test_ai_connection', json=form, headers=self.headers)
        probe.assert_called_once_with(form['base_url'], form['api_key'], form['model'])
        self.assertTrue(response.json['success'])
        self.assertIn('连接成功', response.json['message'])

    def test_empty_key_is_reported_without_request(self):
        with (
            patch.object(web_app, 'load_config', return_value={}),
            patch.object(ai_fallback_client, 'probe_ai_connection') as probe,
        ):
            response = self.client.post('/api/test_ai_connection', json={}, headers=self.headers)
        self.assertEqual(response.status_code, 400)
        self.assertIn('尚未填写', response.json['message'])
        probe.assert_not_called()

    def test_health_check_reports_presence_without_echoing_credentials(self):
        with (
            patch.object(web_app, 'load_config', return_value={'SUBTITLE_OPENAI_API_KEY': 'secret-test-key'}),
            patch.object(ffmpeg_manager, 'probe_ffmpeg', return_value=True),
            patch('modules.youtube_handler.probe_yt_dlp_version', return_value='2026.01.01'),
            patch.object(web_app.shutil, 'which', side_effect=[None, '/some/deno']),
        ):
            response = self.client.get('/api/health_check')
        checks = {check['label']: check for check in response.json['checks']}
        self.assertTrue(checks['FFmpeg']['ok'])
        self.assertIn('Deno', checks['Node.js']['message'])
        self.assertEqual(checks['yt-dlp']['message'], '2026.01.01')
        self.assertIn('字幕专用 Key 已填写', checks['AI API Key']['message'])
        self.assertNotIn('secret-test-key', response.get_data(as_text=True))

    def test_yt_dlp_probe_passes_module_logger_to_command_resolver(self):
        with (
            patch.object(youtube_handler, '_find_yt_dlp_command', return_value=['yt-dlp']) as resolve,
            patch.object(youtube_handler.subprocess, 'run', return_value=SimpleNamespace(stdout='2026.01.01\n')) as run,
        ):
            self.assertEqual(youtube_handler.probe_yt_dlp_version(), '2026.01.01')
        resolve.assert_called_once_with(youtube_handler.logger)
        self.assertEqual(run.call_args.args[0], ['yt-dlp', '--version'])

    def test_quota_and_rate_limit_are_distinct(self):
        cases = (
            (401, {}, '无效'),
            (402, {}, '额度不足'),
            (429, {'error': {'code': 'insufficient_quota'}}, '额度不足'),
            (429, {}, '过于频繁'),
        )
        for status, body, expected in cases:
            with self.subTest(status=status, body=body):
                error = SimpleNamespace(status_code=status, body=body)
                self.assertIn(expected, ai_fallback_client.ai_error_message(error))


@unittest.skipIf(os.name == 'nt', '此用例使用 POSIX 测试可执行文件')
class PortableLauncherTests(unittest.TestCase):
    def test_package_tools_precede_system_path(self):
        path = Path(__file__).resolve().parents[2] / 'launch.py'
        if not path.is_file():
            self.skipTest('需要便携包启动器')
        spec = importlib.util.spec_from_file_location('portable_launcher', path)
        launcher = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(launcher)
        with tempfile.TemporaryDirectory() as tmp:
            launcher.BASE = Path(tmp)
            portable = launcher.BASE / 'bin'
            (portable / 'ffmpeg').mkdir(parents=True)
            (portable / 'node').touch(mode=0o700)
            (portable / 'ffmpeg' / 'ffmpeg').touch(mode=0o700)
            with patch.dict(os.environ, {'PATH': '/usr/bin'}):
                launcher.configure_youtube_runtime()
                self.assertEqual(shutil.which('node'), str(portable / 'node'))
                self.assertEqual(shutil.which('ffmpeg'), str(portable / 'ffmpeg' / 'ffmpeg'))
                path = os.environ['PATH']
                launcher.configure_youtube_runtime()
                self.assertEqual(os.environ['PATH'], path)
