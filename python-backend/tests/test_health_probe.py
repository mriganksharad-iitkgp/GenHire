"""A production HTTP startup probe must check readiness, not return an HTTPS redirect."""
import importlib.util
import os
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

from flask import Flask
from flask_talisman import Talisman

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))


class HealthProbeTests(unittest.TestCase):
    def application(self, database):
        auth = types.ModuleType("middleware.auth_middleware")
        auth.token_required = lambda view: view
        spec = importlib.util.spec_from_file_location("probe_system", BACKEND / "routes/system_routes.py")
        system = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"middleware.auth_middleware": auth}):
            spec.loader.exec_module(system)
        app = Flask(__name__)
        Talisman(app, force_https=True)
        app.register_blueprint(system.create_system_routes(database))
        return app

    def test_plain_http_probe_checks_dependencies_and_other_routes_keep_https(self):
        database = MagicMock()
        with patch.dict(os.environ, {"REDIS_URL": "", "RATE_LIMIT_REQUIRE_REDIS": "false"}), \
                self.application(database).test_client() as client:
            response = client.get("/health", base_url="http://localhost", follow_redirects=False)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json["status"], "healthy")
            self.assertEqual(client.get("/", follow_redirects=False).status_code, 302)
        database.command.assert_called_once()

    def test_dependency_failure_is_503_not_a_successful_redirect(self):
        database = MagicMock()
        database.command.side_effect = ConnectionError("test-only")
        with self.application(database).test_client() as client:
            response = client.get("/health", base_url="http://localhost", follow_redirects=False)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json["status"], "unhealthy")


if __name__ == "__main__":
    unittest.main()
