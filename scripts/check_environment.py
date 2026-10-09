"""Check GenHire dotenv files without displaying credential values."""
import argparse
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
PLACEHOLDER = re.compile(r"(?i)(replace_with|your[-_ ]|placeholder|change[-_ ]?me|xxxx|<[^>]+>)")
CLOUD_EXCLUSIONS = {"GOOGLE_APPLICATION_CREDENTIALS", "GOOGLE_APPLICATION_CREDENTIALS_JSON"}


def read_config(path):
    values = {}
    errors = []
    for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)=(.*)", line)
        if not match:
            errors.append(f"{path.name}: invalid assignment at line {number}")
            continue
        key, raw = match.groups()
        if key in values:
            errors.append(f"{path.name}: duplicate {key}")
        try:
            value = json.loads(raw) if raw.startswith('"') else raw.strip("'")
            if not isinstance(value, str):
                raise ValueError()
            values[key] = value
        except (ValueError, json.JSONDecodeError):
            errors.append(f"{path.name}: invalid quoted value for {key}")
    return values, errors


def inspect_backend(values, production):
    errors, warnings = [], []
    required = ["MONGODB_URI", "DATABASE_NAME", "FLASK_SECRET_KEY", "JWT_SECRET_KEY",
                "INVITE_TOKEN_SECRET", "FRONTEND_URL", "CORS_ORIGINS", "GCS_BUCKET_NAME"]
    if production:
        required += ["REDIS_URL"]
        if values.get("RATE_LIMIT_REQUIRE_REDIS") != "true":
            errors.append("RATE_LIMIT_REQUIRE_REDIS must be true in production")
        for key in CLOUD_EXCLUSIONS | {"PORT"}:
            if key in values:
                errors.append(f"Omit {key} from the Cloud Run import file")
    for key in required:
        if not values.get(key) or PLACEHOLDER.search(values[key]):
            errors.append(f"{key} is missing or contains a placeholder")
    if production and values.get("REDIS_URL") and not values["REDIS_URL"].startswith(("redis://", "rediss://")):
        errors.append("REDIS_URL must use redis:// or rediss://")
    for key, value in values.items():
        if key.startswith("RATE_LIMIT_") and key.endswith(("_CALLS", "_WINDOW_SECONDS")) or key.endswith("_MAX_INFLIGHT"):
            if not value.isdigit() or int(value) < 1:
                errors.append(f"{key} must be a positive integer")
    for key in ["MOBILE_RECORDING_ENABLED", "REQUIRE_EMAIL_VERIFICATION", "FORCE_HTTPS", "RATE_LIMIT_REQUIRE_REDIS"]:
        if values.get(key) not in ("true", "false"):
            errors.append(f"{key} must be true or false")
    mail = values.get("EMAIL_PROVIDER")
    for key in (["ZEPTOMAIL_API_KEY", "ZEPTOMAIL_FROM_EMAIL"] if mail == "zeptomail" else ["MAILGUN_API_KEY", "MAILGUN_DOMAIN", "MAILGUN_FROM_EMAIL"] if mail == "mailgun" else []):
        if not values.get(key) or PLACEHOLDER.search(values[key]):
            errors.append(f"{key} is required for the selected email provider")
    providers = [item.strip() for item in values.get("LLM_PROVIDER_PRIORITY", "").split(",")]
    for provider, key in [("deepseek", "DEEPSEEK_API_KEY"), ("gemini", "GOOGLE_API_KEY"), ("groq", "GROQ_API_KEY")]:
        if provider in providers and not values.get(key):
            warnings.append(f"{key} is empty; the configured {provider} LLM route cannot run")
    if values.get("STT_PROVIDER") == "groq" and not values.get("GROQ_API_KEY"):
        errors.append("GROQ_API_KEY is required for the configured speech-to-text provider")
    if values.get("RAZORPAY_KEY_ID") and (not values.get("RAZORPAY_WEBHOOK_SECRET") or PLACEHOLDER.search(values["RAZORPAY_WEBHOOK_SECRET"])):
        warnings.append("RAZORPAY_WEBHOOK_SECRET is empty; verified webhook processing needs the configured signing secret")
    if production and values.get("RAZORPAY_KEY_ID", "").startswith("rzp_test_"):
        warnings.append("Razorpay is configured in test mode; live payments need a matching live key pair")
    if production and not (values.get("GCS_SERVICE_ACCOUNT_JSON") or values.get("GCS_SERVICE_ACCOUNT_KEY")):
        errors.append("GCS_SERVICE_ACCOUNT_JSON or GCS_SERVICE_ACCOUNT_KEY is required for storage signing")
    if values.get("GCS_SERVICE_ACCOUNT_JSON"):
        try:
            credential = json.loads(values["GCS_SERVICE_ACCOUNT_JSON"])
            if not isinstance(credential, dict) or credential.get("type") != "service_account" or not credential.get("private_key"):
                raise ValueError()
        except (ValueError, TypeError):
            errors.append("GCS_SERVICE_ACCOUNT_JSON must be valid signing service-account JSON")
    object_path = values.get("PROCTORING_OBJECT_MODEL_PATH", "").strip()
    default_model = ROOT / "python-backend/models/proctoring/yolov8n.onnx"
    if not object_path and not default_model.is_file():
        warnings.append("Object-detection model is missing from the configured/default local artifact path")
    elif not object_path and production:
        warnings.append("Object model uses the default path; include the local ONNX artifact in the deployed image (it is gitignored)")
    if values.get("MOBILE_RECORDING_ENABLED") == "false":
        warnings.append("MOBILE_RECORDING_ENABLED is false; jobs requiring a second camera cannot start")

    return errors, warnings


def inspect_frontend(values, backend, production):
    errors = []
    for key in values:
        if not key.startswith("REACT_APP_") or any(secret in key for secret in ["API_KEY", "SECRET", "CREDENTIAL", "PRIVATE", "REDIS", "MONGODB"]):
            errors.append(f"{key} must not be included in public frontend configuration")
    url = values.get("REACT_APP_API_URL", "")
    parsed = urlsplit(url)
    if not parsed.netloc or parsed.scheme not in ("http", "https") or PLACEHOLDER.search(url):
        errors.append("REACT_APP_API_URL needs the actual backend origin")
    if parsed.path or parsed.query or parsed.fragment:
        errors.append("REACT_APP_API_URL must be an origin without a path/query/fragment")
    if production and (parsed.scheme != "https" or parsed.hostname in ("localhost", "127.0.0.1")):
        errors.append("Production REACT_APP_API_URL must use public HTTPS")
    if values.get("REACT_APP_API_BASE") != url.rstrip("/") + "/api":
        errors.append("REACT_APP_API_BASE must equal REACT_APP_API_URL + /api")
    frontend = values.get("REACT_APP_FRONTEND_URL")
    if frontend:
        site = urlsplit(frontend)
        if site.scheme not in ("http", "https") or not site.netloc or site.path or site.query or site.fragment:
            errors.append("REACT_APP_FRONTEND_URL must be a site origin")
        if production and site.scheme != "https":
            errors.append("Production REACT_APP_FRONTEND_URL must use HTTPS")
        if frontend != backend.get("FRONTEND_URL"):
            errors.append("Frontend/backend FRONTEND_URL values must match")
        origins = {item.strip() for item in backend.get("CORS_ORIGINS", "").split(",")}
        if frontend not in origins:
            errors.append("CORS_ORIGINS must include the configured frontend origin")
    if values.get("REACT_APP_GOOGLE_CLIENT_ID") != backend.get("GOOGLE_CLIENT_ID"):
        errors.append("Frontend/backend Google OAuth client IDs must match")
    return errors


def audit(profile="local", schema_only=False):
    errors, warnings = [], []
    local_maps = {}
    production_maps = {}
    for folder in ["python-backend", "react-frontend"]:
        maps = {}
        for name in [".env", ".env.example", ".env.production", ".env.production.example"]:
            path = ROOT / folder / name
            if not path.is_file():
                errors.append(f"{folder}/{name} is missing")
                maps[name] = {}
                continue
            maps[name], problems = read_config(path)
            errors += [folder + "/" + problem for problem in problems]
        for active, example in [(".env", ".env.example"), (".env.production", ".env.production.example")]:
            if set(maps[active]) != set(maps[example]):
                errors.append(f"{folder}: {active}/{example} keys differ")
        expected = set(maps[".env"]) - (CLOUD_EXCLUSIONS if folder == "python-backend" else set())
        if expected != set(maps[".env.production"]):
            errors.append(f"{folder}: local/production schema differs beyond documented Cloud Run exclusions")
        local_maps[folder], production_maps[folder] = maps[".env"], maps[".env.production"]
    if not schema_only:
        selected = production_maps if profile == "production" else local_maps
        backend = selected["python-backend"]
        problems, notices = inspect_backend(backend, profile == "production")
        errors += ["backend: " + problem for problem in problems]
        warnings += ["backend: " + notice for notice in notices]
        errors += ["frontend: " + problem for problem in inspect_frontend(selected["react-frontend"], backend, profile == "production")]
    return errors, warnings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=["local", "production"], default="local")
    parser.add_argument("--schema-only", action="store_true", help="Check key parity and syntax without requiring deployment credentials")
    args = parser.parse_args()
    errors, warnings = audit(args.profile, args.schema_only)
    for message in warnings:
        print("NOTICE " + message)
    for message in errors:
        print("ERROR " + message)
    print(f"Environment check: {len(errors)} errors, {len(warnings)} notices. Credential values were not displayed.")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
