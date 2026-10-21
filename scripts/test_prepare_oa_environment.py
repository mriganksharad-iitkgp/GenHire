"""Environment preparation tests never access real private dotenv files."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('prepare_oa_environment', Path(__file__).with_name('prepare_oa_environment.py'))
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


class PreparationTests(unittest.TestCase):
    def test_preserves_secrets_enables_no_flags_defaults_empty_values_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for folder in ('python-backend', 'react-frontend'):
                (root / folder).mkdir()
                for name in prepare.FILES:
                    (root / folder / name).write_text('PRIVATE_KEY="secret-'+name+'"\n')
            local = root / 'python-backend/.env'
            local.write_text(local.read_text()+'GENHIRE_OA_ATTEMPT_CREDITS=""\nGENHIRE_SQL_POSTGRESQL_JOB="custom-existing-job"\n')
            plans, report = prepare.prepare(root)
            for path, text in plans.items():
                before = prepare.blocks(path.read_text())
                after = prepare.blocks(text)
                self.assertEqual(after['PRIVATE_KEY'][1], before['PRIVATE_KEY'][1])
                self.assertNotIn('secret-', str(report))
                if path.parent.name == 'python-backend':
                    for key in prepare.OA:
                        if key.endswith(('_ENABLED', '_ACCEPTED')):
                            self.assertEqual(prepare.value(after[key][1]), 'false')
                path.write_text(text)
            self.assertEqual(prepare.value(prepare.blocks(plans[local])['GENHIRE_OA_ATTEMPT_CREDITS'][1]), '30')
            self.assertIn('custom-existing-job', plans[local])
            self.assertEqual(plans, prepare.prepare(root)[0])

    def test_unknown_private_fields_are_not_copied_to_other_profiles(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for folder in ('python-backend', 'react-frontend'):
                (root / folder).mkdir()
                for name in prepare.FILES:
                    (root / folder / name).write_text('')
            (root / 'python-backend/.env.example').write_text('CUSTOM_PRIVATE_FIELD="example-secret-fixture"\n')
            plans, _ = prepare.prepare(root)
            for name in ('.env', '.env.production', '.env.production.example'):
                self.assertNotIn('example-secret-fixture', plans[root / 'python-backend' / name])

    def test_duplicate_assignments_fail_before_any_write(self):
        with self.assertRaisesRegex(ValueError, 'Duplicate environment key'):
            prepare.blocks('A="first"\nA="second"\n')
