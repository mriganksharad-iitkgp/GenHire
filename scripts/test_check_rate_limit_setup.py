"""Redis setup probe regressions; synthetic credentials and no external service."""
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

BACKEND = Path(__file__).resolve().parents[1] / "python-backend"
sys.path.insert(0, str(BACKEND))
spec = importlib.util.spec_from_file_location("redis_probe", BACKEND / "scripts/check_rate_limit_setup.py")
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)
from middleware import rate_limiter as limits


class FakeRedis:
    def __init__(self):
        self.counts = {"customer-quota": 9}
        self.deleted = []

    def ping(self):
        return True

    def eval(self, script, number, key, window):
        assert script == limits.COUNTER_SCRIPT and number == 1 and window == 10
        self.counts[key] = self.counts.get(key, 0) + 1
        return [self.counts[key], window]

    def ttl(self, key):
        return 10 if key in self.counts else -2

    def delete(self, key):
        self.deleted.append(key)
        self.counts.pop(key, None)


class RedisProbeChecks(unittest.TestCase):
    def capture(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = probe.probe()
        return code, output.getvalue()

    def test_empty_url_reports_memory_distinction_without_connecting(self):
        with patch.dict(os.environ, {"REDIS_URL":""}), patch.object(limits.store, "_client") as connect:
            code, output = self.capture()
        self.assertEqual(code, 1)
        self.assertIn("Local memory limits can work", output)
        connect.assert_not_called()

    def test_success_uses_only_random_probe_key_and_cleans_it(self):
        client = FakeRedis()
        temporary_store = limits.CounterStore()
        with patch.dict(os.environ, {"REDIS_URL":"redis://synthetic", "RATE_LIMIT_NAMESPACE":"test-only"}), patch.object(limits, "store", temporary_store), patch.object(temporary_store, "_client", return_value=client):
            code, output = self.capture()
        self.assertEqual(code, 0)
        self.assertIn("200/200/429", output)
        self.assertEqual(client.counts, {"customer-quota": 9})
        self.assertEqual(len(client.deleted), 1)
        self.assertTrue(client.deleted[0].startswith("test-only:quota:setup_probe_"))

    def test_connection_failure_never_prints_credential_exception(self):
        sensitive = "rediss://default:private-password@private-host"
        with patch.dict(os.environ, {"REDIS_URL": sensitive}), patch.object(limits.store, "_client", side_effect=RuntimeError(sensitive)):
            code, output = self.capture()
        self.assertEqual(code, 1)
        self.assertIn("RuntimeError", output)
        self.assertNotIn(sensitive, output)
        self.assertNotIn("private-password", output)


if __name__ == "__main__":
    unittest.main()
