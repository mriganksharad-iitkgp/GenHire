"""Exercise real google-auth credential discovery without credentials/network."""
from contextlib import ExitStack
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import google.auth
from google.auth import _default
from google.auth.credentials import AnonymousCredentials
from google.auth.exceptions import DefaultCredentialsError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import env_loader


class GoogleCredentialEnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict(os.environ, {}, clear=True))
        self.stack.enter_context(patch.object(env_loader, '_LOADED', False))
        self.credentials = AnonymousCredentials()
        self.stack.enter_context(patch.object(_default, '_get_gcloud_sdk_credentials', return_value=(None, None)))
        self.stack.enter_context(patch.object(_default, '_get_gae_credentials', return_value=(None, None)))
        self.metadata = self.stack.enter_context(patch.object(
            _default, '_get_gce_credentials', return_value=(self.credentials, 'test-project')))

    def test_real_sdk_reproduces_empty_file_override_failure(self):
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = ''
        with self.assertRaises(DefaultCredentialsError):
            google.auth.default()
        self.metadata.assert_not_called()

    def test_blank_overrides_allow_real_sdk_to_reach_attached_identity(self):
        for value in ('', '   ', '\t\n'):
            with self.subTest(value=value):
                os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = value
                os.environ['GOOGLE_APPLICATION_CREDENTIALS_JSON'] = value
                os.environ['REDIS_URL'] = ''
                env_loader.normalize_google_credential_overrides()
                self.assertNotIn('GOOGLE_APPLICATION_CREDENTIALS', os.environ)
                self.assertNotIn('GOOGLE_APPLICATION_CREDENTIALS_JSON', os.environ)
                self.assertEqual(os.environ['REDIS_URL'], '')
                credentials, project = google.auth.default()
                self.assertIs(credentials, self.credentials)
                self.assertEqual(project, 'test-project')

    def test_nonblank_invalid_file_still_fails_instead_of_using_other_identity(self):
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'test-only-nonexistent-credential.json'
        os.environ['GOOGLE_APPLICATION_CREDENTIALS_JSON'] = '{"test": "preserve"}'
        env_loader.normalize_google_credential_overrides()
        self.assertEqual(os.environ['GOOGLE_APPLICATION_CREDENTIALS'], 'test-only-nonexistent-credential.json')
        self.assertEqual(os.environ['GOOGLE_APPLICATION_CREDENTIALS_JSON'], '{"test": "preserve"}')
        with self.assertRaises(DefaultCredentialsError):
            google.auth.default()
        self.metadata.assert_not_called()

    def test_dotenv_blanks_are_removed_after_files_load(self):
        def load_file(path, override):
            self.assertFalse(override)
            os.environ.setdefault('GOOGLE_APPLICATION_CREDENTIALS', '')
            os.environ.setdefault('GOOGLE_APPLICATION_CREDENTIALS_JSON', '')
        with patch.object(env_loader, 'load_dotenv', side_effect=load_file):
            env_loader.load_environment()
        credentials, _ = google.auth.default()
        self.assertIs(credentials, self.credentials)

    def test_platform_key_path_is_preserved_when_dotenv_is_loaded(self):
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'test-only-platform-key.json'
        with patch.object(env_loader, 'load_dotenv'):
            env_loader.load_environment()
        self.assertEqual(os.environ['GOOGLE_APPLICATION_CREDENTIALS'], 'test-only-platform-key.json')

    def test_speech_client_with_blank_overrides_reaches_real_adc_discovery(self):
        from services.google_speech_service import GoogleSpeechService
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = ''
        os.environ['GOOGLE_APPLICATION_CREDENTIALS_JSON'] = ''
        with patch('google.cloud.texttospeech.TextToSpeechClient') as tts:
            service = GoogleSpeechService()
        self.metadata.assert_called_once()
        tts.assert_called_once_with(credentials=self.credentials)
        self.assertIs(service._credentials, self.credentials)
        self.assertIs(service.tts_client, tts.return_value)

    def test_repeated_loader_call_removes_a_reintroduced_blank_override(self):
        env_loader._LOADED = True
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = ''
        with patch.object(env_loader, 'load_dotenv') as dotenv:
            env_loader.load_environment()
        dotenv.assert_not_called()
        self.assertNotIn('GOOGLE_APPLICATION_CREDENTIALS', os.environ)


if __name__ == '__main__':
    unittest.main()
