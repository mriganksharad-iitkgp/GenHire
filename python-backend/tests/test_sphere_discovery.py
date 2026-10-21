import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from models.hiring_workflow import WorkflowError
from services.sphere_engine_service import SphereEngineClient


class Response:
    status_code = 200
    def __init__(self, value): self.value = value
    def iter_content(self, chunk_size): yield json.dumps(self.value).encode()
    def close(self): pass


class SphereDiscoveryTests(unittest.TestCase):
    def test_judges_paginate_both_types_without_following_vendor_urls(self):
        class Session:
            calls = []
            def request(inner, method, url, **kwargs):
                self.assertEqual(method, 'GET')
                self.assertEqual(url, 'https://fixture.problems.sphere-engine.com/api/v4/judges')
                inner.calls.append(kwargs['params'])
                p = kwargs['params']
                count = 100 if p['offset'] == 0 else 1
                return Response(dict(items=[dict(id=p['offset']+i+1, name='Judge', type=dict(id=p['typeId']),
                    uri='https://evil.test/?access_token=SECRET') for i in range(count)], paging=dict(next='https://evil.test')))
        session = Session()
        client = SphereEngineClient('https://fixture.problems.sphere-engine.com/api/v4', 'SECRET', 'problems', session)
        for kind in (0, 1):
            rows = client.judges(kind)
            self.assertEqual(len(rows), 101)
            self.assertNotIn('SECRET', json.dumps(rows))
        self.assertEqual([p['offset'] for p in session.calls], [0, 100, 0, 100])

    def test_wrong_judge_type_and_auth_override_are_rejected(self):
        class Session:
            def request(inner, *args, **kwargs): return Response(dict(items=[dict(id=2, name='wrong', type=dict(id=1))]))
        client = SphereEngineClient('https://fixture.problems.sphere-engine.com/api/v4', 'SECRET', 'problems', Session())
        with self.assertRaises(WorkflowError): client.judges(0)
        with self.assertRaises(ValueError): client.request('GET', '/judges', query={'access_token': 'override'})
        with self.assertRaises(ValueError): client.judges(True)

    def test_cli_does_not_connect_when_credentials_missing_and_redacts_catalog(self):
        spec = importlib.util.spec_from_file_location('sphere_discovery', Path(__file__).resolve().parents[1]/'scripts/admin/discover_sphere_account.py')
        cli = importlib.util.module_from_spec(spec); spec.loader.exec_module(cli)
        with patch('config.env_loader.load_environment'), patch.dict('os.environ', {}, clear=True), patch('builtins.print') as output:
            self.assertEqual(cli.main(), 1)
            self.assertIn('execution_not_configured', output.call_args.args[0])
        env = {f'SPHERE_{p.upper()}_{k}': v for p in ('compilers', 'problems') for k, v in
               [('ENDPOINT', f'https://fixture.{p}.sphere-engine.com/api/v4'), ('TOKEN', 'SECRET')]}
        with patch('config.env_loader.load_environment'), patch.dict('os.environ', env, clear=True), \
                patch.object(cli, 'discover', return_value={'label': 'SECRET'}), patch('builtins.print') as output:
            self.assertEqual(cli.main(), 0)
            self.assertNotIn('SECRET', output.call_args.args[0])


if __name__ == '__main__': unittest.main()
