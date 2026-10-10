from __future__ import annotations

import io
import getpass
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

from lazy_commit.cli import run
from lazy_commit.config import config_path, load_settings, read_user_config, save_user_config
from lazy_commit.errors import ConfigError
from lazy_commit.i18n import get_language, set_language, translation_issues
from lazy_commit.setup_wizard import run_setup


class _Terminal(io.StringIO):
    def isatty(self) -> bool:
        return True


class _ConfigTestCase(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / 'settings' / 'config.json'
        env = patch.dict(os.environ, {'LAZY_COMMIT_CONFIG_PATH': str(self.path)}, clear=True)
        env.start()
        self.addCleanup(env.stop)
        language = get_language()
        self.addCleanup(set_language, language)
        set_language('en')


class SavedConfigTests(_ConfigTestCase):
    def test_saved_settings_and_override_priority(self) -> None:
        save_user_config({
            'api_key': 'saved-key', 'base_url': 'https://saved.example/v1',
            'model_name': 'saved-model', 'max_context_size': 1234, 'max_context_tokens': 567,
        })
        settings = load_settings()
        self.assertEqual(settings.api_key, 'saved-key')
        self.assertEqual(settings.model_name, 'saved-model')
        self.assertEqual(settings.max_context_size, 1234)
        self.assertEqual(settings.max_context_tokens, 567)
        with patch.dict(os.environ, {
            'LAZY_COMMIT_OPENAI_API_KEY': 'env-key',
            'LAZY_COMMIT_OPENAI_BASE_URL': 'https://env.example/v1',
            'LAZY_COMMIT_OPENAI_MODEL_NAME': 'env-model',
            'LAZY_COMMIT_MAX_CONTEXT_SIZE': '2222',
            'LAZY_COMMIT_MAX_CONTEXT_TOKENS': '888',
        }):
            settings = load_settings()
            self.assertEqual(settings.api_key, 'env-key')
            self.assertEqual(settings.base_url, 'https://env.example/v1')
            self.assertEqual(settings.model_name, 'env-model')
            self.assertEqual(settings.max_context_size, 2222)
            self.assertEqual(settings.max_context_tokens, 888)
            settings = load_settings(api_key='cli-key', base_url='https://cli.example/v1',
                                     model_name='cli-model', max_context_size=3333,
                                     max_context_tokens=999)
            self.assertEqual(settings.api_key, 'cli-key')
            self.assertEqual(settings.base_url, 'https://cli.example/v1')
            self.assertEqual(settings.model_name, 'cli-model')
            self.assertEqual(settings.max_context_size, 3333)
            self.assertEqual(settings.max_context_tokens, 999)

    def test_private_atomic_save_preserves_old_file_on_failure(self) -> None:
        save_user_config({'api_key': 'old-key'})
        original = self.path.read_bytes()
        if os.name != 'nt':
            self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)
        with patch('lazy_commit.config.os.replace', side_effect=OSError('cannot replace')):
            with self.assertRaises(ConfigError):
                save_user_config({'api_key': 'new-key'})
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_invalid_file_reports_no_secrets(self) -> None:
        self.path.parent.mkdir()
        for payload in ('{"api_key":"secret-value",', '[]', '{"max_context_tokens":true}'):
            self.path.write_text(payload, encoding='utf-8')
            with self.assertRaises(ConfigError) as error:
                read_user_config()
            self.assertNotIn('secret-value', str(error.exception))
            self.assertIn('--setup', str(error.exception))

    def test_platform_config_locations(self) -> None:
        with patch.dict(os.environ, {}, clear=True), patch('pathlib.Path.home', return_value=Path('/users/demo')):
            with patch('sys.platform', 'darwin'):
                self.assertEqual(config_path(), Path('/users/demo/Library/Application Support/lazy-commit/config.json'))
            with patch('sys.platform', 'win32'), patch.dict(os.environ, {'APPDATA': '/roaming'}):
                self.assertEqual(config_path(), Path('/roaming/lazy-commit/config.json'))
            with patch('sys.platform', 'linux'), patch.dict(os.environ, {'XDG_CONFIG_HOME': '/xdg'}):
                self.assertEqual(config_path(), Path('/xdg/lazy-commit/config.json'))

    def test_help_language_uses_file_env_then_flag(self) -> None:
        save_user_config({'language': 'zh-cn'})
        for env_language, flags, expected in (
            ('', [], '理解 Git 变更'),
            ('en', [], 'Understand git changes'),
            ('en', ['--lang', 'zh-TW'], '理解 Git 變更'),
        ):
            with self.subTest(flags=flags, env=env_language), \
                    patch.dict(os.environ, {'LAZY_COMMIT_LANG': env_language}), \
                    patch('sys.stdout', new_callable=io.StringIO) as output:
                with self.assertRaises(SystemExit):
                    run([*flags, '--help'])
                self.assertIn(expected, output.getvalue())


class SetupWizardTests(_ConfigTestCase):
    def _wizard(self, answers: list[str], keys: list[str]) -> tuple[int, str]:
        output = _Terminal()
        with patch('sys.stdin', _Terminal()), patch('sys.stdout', output), \
                patch('builtins.input', side_effect=answers), \
                patch('getpass.getpass', side_effect=keys):
            result = run_setup()
        return result, output.getvalue()

    def test_new_configuration_is_immediately_usable(self) -> None:
        result, output = self._wizard(['', '', '', ''], ['test-secret'])
        self.assertEqual(result, 0)
        self.assertEqual(load_settings().api_key, 'test-secret')
        self.assertEqual(load_settings().base_url, 'https://api.openai.com/v1')
        self.assertEqual(read_user_config()['language'], 'zh-cn')
        self.assertNotIn('test-secret', output)
        self.assertIn('配置已保存', output)
        self.assertEqual(translation_issues(), ())

    def test_reconfigure_keeps_hidden_key_and_advanced_values(self) -> None:
        save_user_config({'api_key': 'keep-me', 'base_url': 'https://api.openai.com/v1',
                          'model_name': 'custom-model', 'language': 'en', 'max_context_tokens': 123})
        result, output = self._wizard(['', '', '', ''], [''])
        self.assertEqual(result, 0)
        self.assertEqual(load_settings().api_key, 'keep-me')
        self.assertEqual(load_settings().model_name, 'custom-model')
        self.assertEqual(load_settings().max_context_tokens, 123)
        self.assertNotIn('keep-me', output)

    def test_provider_switch_requires_new_key(self) -> None:
        save_user_config({'api_key': 'old-key', 'base_url': 'https://api.openai.com/v1'})
        result, output = self._wizard(['2', '2', '', ''], ['', 'new-key'])
        self.assertEqual(result, 0)
        self.assertEqual(load_settings().api_key, 'new-key')
        self.assertTrue(load_settings().is_gemini)
        self.assertNotIn('old-key', output)

    def test_custom_provider_reprompts_invalid_input(self) -> None:
        result, output = self._wizard(
            ['9', '2', '3', 'invalid', 'https://user:secret@example.com/v1',
             'http://localhost:8080/v1', '', 'my-model', ''], ['custom-key'])
        self.assertEqual(result, 0)
        self.assertEqual(load_settings().base_url, 'http://localhost:8080/v1')
        self.assertEqual(load_settings().model_name, 'my-model')
        self.assertIn('This value is required', output)

    def test_decline_or_interrupt_preserves_existing_config(self) -> None:
        save_user_config({'api_key': 'old-key'})
        original = self.path.read_bytes()
        result, _ = self._wizard(['2', '1', '', 'n'], ['new-key'])
        self.assertEqual(result, 1)
        self.assertEqual(self.path.read_bytes(), original)
        for interruption in (EOFError, KeyboardInterrupt):
            with patch('sys.stdin', _Terminal()), patch('sys.stdout', _Terminal()), \
                    patch('builtins.input', side_effect=interruption):
                self.assertEqual(run_setup(), 1)
            self.assertEqual(self.path.read_bytes(), original)

    def test_setup_repairs_bad_config_after_confirmation(self) -> None:
        self.path.parent.mkdir()
        self.path.write_text('broken-json', encoding='utf-8')
        output = _Terminal()
        with patch('sys.stdin', _Terminal()), patch('sys.stdout', output), \
                patch('builtins.input', side_effect=['2', '1', '', '']), \
                patch('getpass.getpass', return_value='new-key'):
            self.assertEqual(run(['--setup']), 0)
        self.assertEqual(load_settings().api_key, 'new-key')

    def test_noninteractive_setup_fails_without_writing(self) -> None:
        with patch('sys.stdin', io.StringIO()), self.assertRaises(ConfigError):
            run_setup()
        self.assertFalse(self.path.exists())

    def test_unsafe_key_input_fails_without_saving(self) -> None:
        with patch('sys.stdin', _Terminal()), patch('sys.stdout', _Terminal()), \
                patch('builtins.input', side_effect=['2', '1', '']), \
                patch('getpass.getpass', side_effect=getpass.GetPassWarning), \
                self.assertRaises(ConfigError):
            run_setup()
        self.assertFalse(self.path.exists())

    def test_existing_environment_is_explained_without_exposing_key(self) -> None:
        with patch.dict(os.environ, {'LAZY_COMMIT_API_KEY': 'env-secret'}):
            result, output = self._wizard(['2', '1', '', ''], ['saved-secret'])
            self.assertEqual(result, 0)
            self.assertIn('take priority', output)
            self.assertNotIn('env-secret', output)
            self.assertNotIn('saved-secret', output)
            self.assertEqual(load_settings().api_key, 'env-secret')

    def test_configured_first_run_does_not_open_wizard(self) -> None:
        save_user_config({'api_key': 'saved-key'})
        with patch('sys.stdin', _Terminal()), patch('sys.stdout', _Terminal()), \
                patch('lazy_commit.setup_wizard.run_setup') as wizard, \
                patch('lazy_commit.cli.GitClient') as git:
            git.return_value.snapshot.return_value.has_any_changes = False
            self.assertEqual(run([]), 0)
            wizard.assert_not_called()

    def test_setup_and_first_run_skip_git_and_model(self) -> None:
        for argv in (['--setup'], []):
            with self.subTest(argv=argv), patch('sys.stdin', _Terminal()), \
                    patch('sys.stdout', _Terminal()), \
                    patch('lazy_commit.setup_wizard.run_setup', return_value=0) as wizard, \
                    patch('lazy_commit.cli.GitClient') as git:
                self.assertEqual(run(argv), 0)
                wizard.assert_called_once()
                git.assert_not_called()

    def test_noninteractive_first_run_has_setup_hint(self) -> None:
        with patch('sys.stdin', io.StringIO()), patch('sys.stdout', io.StringIO()), \
                self.assertRaisesRegex(ConfigError, 'lazy-commit --setup'):
            run([])
        self.assertFalse(self.path.exists())
