"""Real dotenv selection with synthetic files; no credentials, DB or network."""
import os
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from config import env_loader


class EnvironmentSelectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / '.env').write_text('MONGODB_URI=local-fixture\nLOCAL_ONLY=local-secret-fixture\n')
        (self.root / '.env.production').write_text('MONGODB_URI=production-fixture\n')
        for mock in (patch.dict(os.environ, {}, clear=True), patch.object(env_loader, '_LOADED', False),
                     patch.object(env_loader, '__file__', str(self.root / 'config/env_loader.py'))):
            mock.start(); self.addCleanup(mock.stop)

    def test_explicit_file_is_exclusive_and_platform_values_win(self):
        (self.root / 'staging.env').write_text('MONGODB_URI=staging-fixture\nJWT_SECRET_KEY=file-fixture\n')
        os.environ.update(ENV_FILE='staging.env', JWT_SECRET_KEY='injected-fixture')
        env_loader.load_environment()
        self.assertEqual(os.environ['MONGODB_URI'], 'staging-fixture')
        self.assertEqual(os.environ['JWT_SECRET_KEY'], 'injected-fixture')
        self.assertNotIn('LOCAL_ONLY', os.environ)

    def test_missing_explicit_file_refuses_local_fallback(self):
        os.environ['ENV_FILE'] = 'missing-fixture.env'
        with self.assertRaisesRegex(RuntimeError, 'refusing fallback'):
            env_loader.load_environment()
        self.assertNotIn('MONGODB_URI', os.environ)
        self.assertFalse(env_loader._LOADED)

    def test_database_worker_requires_explicit_connection_and_name_even_after_cached_load(self):
        (self.root / 'partial.env').write_text('JWT_SECRET_KEY=synthetic-secret\n')
        os.environ['ENV_FILE'] = 'partial.env'
        env_loader.load_environment()
        with self.assertRaisesRegex(RuntimeError, 'refusing MongoDB defaults'):
            env_loader.load_environment(require_database=True)
        os.environ.update(MONGODB_URI='mongodb://synthetic.invalid', DATABASE_NAME='synthetic')
        env_loader.load_environment(require_database=True)

    def test_production_does_not_import_local_only_credentials(self):
        os.environ['FLASK_ENV'] = 'production'
        env_loader.load_environment()
        self.assertEqual(os.environ['MONGODB_URI'], 'production-fixture')
        self.assertNotIn('LOCAL_ONLY', os.environ)

    def test_payment_configuration_cannot_bypass_selected_environment(self):
        (self.root / 'staging.env').write_text('RAZORPAY_KEY_ID=staging-public-fixture\n')
        os.environ['ENV_FILE'] = 'staging.env'
        path = Path(__file__).resolve().parents[1] / 'payment_module/config/settings.py'
        spec = importlib.util.spec_from_file_location('isolated_payment_selection', path)
        module = importlib.util.module_from_spec(spec)
        # An old direct dotenv import would try the real backend dotenv. Refuse
        # that call rather than allowing a test to read private credentials.
        with patch('dotenv.load_dotenv', side_effect=AssertionError('Unscoped dotenv access')):
            spec.loader.exec_module(module)
        self.assertEqual(module.PaymentConfig.RAZORPAY_KEY_ID, 'staging-public-fixture')
        self.assertIsNone(module.PaymentConfig.RAZORPAY_KEY_SECRET)
        self.assertNotIn('LOCAL_ONLY', os.environ)

    def test_cloud_environment_without_dotenv_never_falls_back_to_local(self):
        (self.root / '.env.production').unlink()
        os.environ.update(FLASK_ENV='production', MONGODB_URI='injected-cloud-fixture')
        env_loader.load_environment()
        self.assertEqual(os.environ['MONGODB_URI'], 'injected-cloud-fixture')
        self.assertNotIn('LOCAL_ONLY', os.environ)

    def test_development_and_dotenv_path_alias_select_intended_file(self):
        env_loader.load_environment()
        self.assertEqual(os.environ['MONGODB_URI'], 'local-fixture')
        env_loader._LOADED = False
        os.environ.pop('MONGODB_URI')
        (self.root / 'alias.env').write_text('MONGODB_URI=alias-fixture\n')
        os.environ['DOTENV_PATH'] = str(self.root / 'alias.env')
        env_loader.load_environment()
        self.assertEqual(os.environ['MONGODB_URI'], 'alias-fixture')
