"""
GCS Service - Google Cloud Storage utility for file uploads/downloads.

Handles CV PDFs, JD PDFs, and other file uploads.
Uses signed URLs for secure, time-limited access.
Cloud Run uses its attached service identity; local development can use a key file.
GCS is mandatory for application startup; there is no local upload fallback.
"""

import os
import logging
from datetime import timedelta
from google.cloud import storage
from google.oauth2 import service_account
import google.auth
from google.auth.transport.requests import Request

logger = logging.getLogger(__name__)

_client = None
_bucket = None
_credentials = None
_uses_adc = False


def _get_client():
    """Get or create a GCS client using ADC or local development credentials."""
    global _client, _credentials, _uses_adc
    if _client is not None:
        return _client

    import json

    key_json = os.getenv("GCS_SERVICE_ACCOUNT_JSON")
    if key_json and key_json.strip().startswith("{"):
        try:
            creds_dict = json.loads(key_json)
            _credentials = service_account.Credentials.from_service_account_info(creds_dict)
            _client = storage.Client(credentials=_credentials, project=_credentials.project_id)
            return _client
        except Exception as e:
            logger.error(f"Failed to parse GCS_SERVICE_ACCOUNT_JSON: {e}")

    key_path = os.getenv("GCS_SERVICE_ACCOUNT_KEY") or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if key_path and key_path.strip().startswith("{"):
        try:
            creds_dict = json.loads(key_path)
            _credentials = service_account.Credentials.from_service_account_info(creds_dict)
            _client = storage.Client(credentials=_credentials, project=_credentials.project_id)
            return _client
        except Exception as e:
            logger.error(f"Failed to parse JSON from GCS_SERVICE_ACCOUNT_KEY: {e}")

    if key_path:
        if not os.path.isabs(key_path):
            key_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), key_path)
        if not os.path.exists(key_path):
            raise FileNotFoundError(f"Service account key file not found: {key_path}")
        _credentials = service_account.Credentials.from_service_account_file(key_path)
        _client = storage.Client(credentials=_credentials, project=_credentials.project_id)
        return _client

    _credentials, project_id = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    _uses_adc = True
    _client = storage.Client(credentials=_credentials, project=project_id)
    return _client


def _get_bucket():
    """Get the configured GCS bucket."""
    global _bucket
    if _bucket is not None:
        return _bucket

    bucket_name = os.getenv("GCS_BUCKET_NAME")
    if not bucket_name:
        raise RuntimeError("GCS_BUCKET_NAME not set")

    client = _get_client()
    _bucket = client.bucket(bucket_name)
    return _bucket


def is_gcs_configured():
    """Resolve the same credentials used for uploads, including Cloud Run ADC.

    Client initialization validates credentials without listing/writing objects.
    Bucket permissions still need an actual storage operation to verify them.
    """
    try:
        if not os.getenv("GCS_BUCKET_NAME", "").strip():
            return False
        return _get_client() is not None
    except Exception as exc:
        # Credential exception messages may contain paths or private JSON.
        logger.warning("GCS credentials unavailable (%s)", type(exc).__name__)
        return False


def upload_file(file_obj, gcs_path, content_type="application/pdf"):
    """
    Upload a file to GCS.

    Args:
        file_obj: File-like object or bytes to upload
        gcs_path: Destination path in the bucket (e.g., 'cvs/user123/abc.pdf')
        content_type: MIME type of the file

    Returns:
        str: The gs:// URI of the uploaded file
    """
    try:
        bucket = _get_bucket()
        blob = bucket.blob(gcs_path)
        
        if isinstance(file_obj, bytes):
            blob.upload_from_string(file_obj, content_type=content_type)
        elif hasattr(file_obj, 'read'):
            # File-like object (e.g. from Flask request.files)
            blob.upload_from_file(file_obj, content_type=content_type, rewind=True)
        else:
            # Assume it's a file path
            blob.upload_from_filename(file_obj, content_type=content_type)

        gcs_uri = f"gs://{bucket.name}/{gcs_path}"
        logger.info(f"Uploaded to GCS: {gcs_uri}")
        return gcs_uri
    except Exception as e:
        logger.error(f"GCS upload failed for {gcs_path}: {e}")
        raise


def upload_from_path(local_path, gcs_path, content_type="application/pdf"):
    """
    Upload a local file to GCS by path.

    Args:
        local_path: Local file path
        gcs_path: Destination path in the bucket
        content_type: MIME type

    Returns:
        str: The gs:// URI
    """
    try:
        bucket = _get_bucket()
        blob = bucket.blob(gcs_path)
        blob.upload_from_filename(local_path, content_type=content_type)
        gcs_uri = f"gs://{bucket.name}/{gcs_path}"
        logger.info(f"Uploaded local file to GCS: {gcs_uri}")
        return gcs_uri
    except Exception as e:
        logger.error(f"GCS upload from path failed for {gcs_path}: {e}")
        raise


def generate_signed_url(gcs_path, expiration_minutes=60):
    """
    Generate a signed URL for temporary access to a GCS file.

    Args:
        gcs_path: Path in the bucket (e.g., 'cvs/user123/abc.pdf')
        expiration_minutes: How long the URL is valid (default: 60 min)

    Returns:
        str: A signed URL that can be opened in a browser
    """
    try:
        bucket = _get_bucket()
        blob = bucket.blob(gcs_path)

        signing_options = {}
        if _uses_adc:
            if _credentials is None:
                raise RuntimeError("GCS credentials were not initialized")
            _credentials.refresh(Request())
            service_account_email = getattr(_credentials, "service_account_email", None)
            if not service_account_email:
                raise RuntimeError(
                    "The ADC identity cannot sign URLs; configure a service account "
                    "runtime identity with Service Account Token Creator permission"
                )
            signing_options = {
                "service_account_email": service_account_email,
                "access_token": _credentials.token,
            }

        url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=expiration_minutes),
            method="GET",
            **signing_options,
        )
        return url
    except Exception as e:
        logger.error(f"Failed to generate signed URL for {gcs_path}: {e}")
        raise


def download_file(gcs_path):
    """Download an object's bytes (used to proxy small artifacts — gaze
    JSON/plots — through the API so browsers don't need bucket CORS)."""
    bucket = _get_bucket()
    blob = bucket.blob(gcs_path)
    return blob.download_as_bytes()


def delete_file(gcs_path):
    """
    Delete a file from GCS.

    Args:
        gcs_path: Path in the bucket
    """
    try:
        bucket = _get_bucket()
        blob = bucket.blob(gcs_path)
        blob.delete()
        logger.info(f"Deleted from GCS: {gcs_path}")
    except Exception as e:
        logger.warning(f"Failed to delete from GCS {gcs_path}: {e}")


def gcs_path_from_uri(gcs_uri):
    """Extract the path portion from a gs:// URI."""
    if gcs_uri and gcs_uri.startswith("gs://"):
        # gs://bucket-name/path/to/file -> path/to/file
        parts = gcs_uri.split("/", 3)
        return parts[3] if len(parts) > 3 else ""
    return gcs_uri or ""
