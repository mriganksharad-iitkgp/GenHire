"""Cloud Run storage startup regressions; no network or private credentials."""
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services import gcs_service as gcs
from google.auth.exceptions import DefaultCredentialsError


class StorageStartupTests(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(os.environ, {
            "GCS_BUCKET_NAME": "test-only-bucket", "GCS_SERVICE_ACCOUNT_JSON": "",
            "GCS_SERVICE_ACCOUNT_KEY": "", "GOOGLE_APPLICATION_CREDENTIALS": "",
        })
        environment.start()
        self.addCleanup(environment.stop)
        for attribute, value in (("_client", None), ("_credentials", None), ("_uses_adc", False)):
            stub = patch.object(gcs, attribute, value)
            stub.start()
            self.addCleanup(stub.stop)

    def test_cloud_run_identity_without_a_key_file_boots_and_reuses_client(self):
        credentials, client = MagicMock(), MagicMock()
        with patch.object(gcs.google.auth, "default", return_value=(credentials, "test-project")) as adc, \
                patch.object(gcs.storage, "Client", return_value=client) as create:
            self.assertTrue(gcs.is_gcs_configured())
            self.assertIs(gcs._get_client(), client)
            self.assertTrue(gcs.is_gcs_configured())
        adc.assert_called_once()
        create.assert_called_once_with(credentials=credentials, project="test-project")
        self.assertTrue(gcs._uses_adc)

    def test_bucket_is_still_required(self):
        with patch.dict(os.environ, {"GCS_BUCKET_NAME": ""}), patch.object(gcs.google.auth, "default") as adc:
            self.assertFalse(gcs.is_gcs_configured())
        adc.assert_not_called()

    def test_missing_credentials_fail_without_disclosing_exception(self):
        with patch.object(gcs.google.auth, "default", side_effect=DefaultCredentialsError("private-value")), \
                self.assertLogs(gcs.logger, level="WARNING") as logs:
            self.assertFalse(gcs.is_gcs_configured())
        self.assertIn("DefaultCredentialsError", " ".join(logs.output))
        self.assertNotIn("private-value", " ".join(logs.output))

    def test_local_key_file_remains_supported(self):
        credentials = MagicMock(project_id="test-project")
        with patch.dict(os.environ, {"GCS_SERVICE_ACCOUNT_KEY": "test-only-key.json"}), \
                patch.object(gcs.os.path, "exists", return_value=True), \
                patch.object(gcs.service_account.Credentials, "from_service_account_file", return_value=credentials), \
                patch.object(gcs.storage, "Client") as create, patch.object(gcs.google.auth, "default") as adc:
            self.assertTrue(gcs.is_gcs_configured())
        adc.assert_not_called()
        create.assert_called_once_with(credentials=credentials, project="test-project")
        self.assertFalse(gcs._uses_adc)


if __name__ == "__main__":
    unittest.main()
