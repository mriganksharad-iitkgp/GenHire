"""Configuration validation tests use synthetic secrets only."""
import importlib.util
from pathlib import Path
import unittest
import tempfile
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("check_environment", Path(__file__).with_name("check_environment.py"))
checks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checks)


class EnvironmentChecks(unittest.TestCase):
    def test_required_error_never_contains_credential_value(self):
        private_value = "mongodb+srv://user:YOUR-private-password@host/database"
        errors, _ = checks.inspect_backend({"MONGODB_URI": private_value}, True)
        combined = " ".join(errors)
        self.assertNotIn(private_value, combined)
        self.assertNotIn("private-password", combined)
        self.assertIn("MONGODB_URI", combined)
        self.assertIn("REDIS_URL", combined)

    def test_frontend_blocks_backend_secret_and_invalid_api_relationship(self):
        errors = checks.inspect_frontend({"REACT_APP_GROQ_API_KEY":"synthetic-secret", "REACT_APP_API_URL":"http://localhost:5000", "REACT_APP_API_BASE":"http://localhost:5000"}, {}, True)
        self.assertTrue(any("REACT_APP_GROQ_API_KEY" in error for error in errors))
        self.assertTrue(any("public HTTPS" in error for error in errors))
        self.assertTrue(any("REACT_APP_API_BASE" in error for error in errors))
        self.assertNotIn("synthetic-secret", " ".join(errors))

    def test_schema_parity_and_quoted_values_in_all_eight_files(self):
        errors, _ = checks.audit(schema_only=True)
        self.assertEqual(errors, [])

    def test_matching_public_api_and_oauth_are_accepted(self):
        values = {"REACT_APP_API_URL":"https://api.example.test", "REACT_APP_API_BASE":"https://api.example.test/api", "REACT_APP_GOOGLE_CLIENT_ID":"public-client"}
        self.assertEqual(checks.inspect_frontend(values, {"GOOGLE_CLIENT_ID":"public-client"}, True), [])

    def test_site_origin_must_agree_with_backend_and_cors(self):
        frontend = {"REACT_APP_API_URL":"https://api.example.test", "REACT_APP_API_BASE":"https://api.example.test/api", "REACT_APP_FRONTEND_URL":"https://app.example.test"}
        errors = checks.inspect_frontend(frontend, {"FRONTEND_URL":"https://other.example.test", "CORS_ORIGINS":"https://other.example.test"}, True)
        self.assertTrue(any("FRONTEND_URL values must match" in error for error in errors))
        self.assertTrue(any("CORS_ORIGINS" in error for error in errors))
        backend = {"FRONTEND_URL":"https://app.example.test", "CORS_ORIGINS":"https://app.example.test,https://alias.example.test"}
        self.assertEqual(checks.inspect_frontend(frontend, backend, True), [])

    def test_nonobject_storage_json_is_reported_without_crashing(self):
        errors, _ = checks.inspect_backend({"GCS_SERVICE_ACCOUNT_JSON":"[]"}, False)
        self.assertTrue(any("valid signing service-account JSON" in error for error in errors))

    def test_present_default_object_artifact_avoids_missing_model_notice(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            model = root / "python-backend/models/proctoring/yolov8n.onnx"
            model.parent.mkdir(parents=True)
            model.touch()
            with patch.object(checks, "ROOT", root):
                _, local = checks.inspect_backend({}, False)
                _, production = checks.inspect_backend({}, True)
            self.assertFalse(any("model" in notice.lower() for notice in local))
            self.assertTrue(any("gitignored" in notice for notice in production))

    def test_disabled_mobile_and_placeholder_webhook_are_actionable(self):
        _, notices = checks.inspect_backend({"MOBILE_RECORDING_ENABLED":"false", "RAZORPAY_KEY_ID":"synthetic-key", "RAZORPAY_WEBHOOK_SECRET":"your_webhook_secret"}, False)
        self.assertTrue(any("second camera" in notice for notice in notices))
        self.assertTrue(any("RAZORPAY_WEBHOOK_SECRET" in notice for notice in notices))


if __name__ == "__main__":
    unittest.main()
