"""Check GenHire dotenv files without displaying credential values."""
import argparse
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
PLACEHOLDER = re.compile(r"(?i)(replace_with|your[-_ ]|placeholder|change[-_ ]?me|xxxx|<[^>]+>)")
CLOUD_ADC_OVERRIDES = {"GOOGLE_APPLICATION_CREDENTIALS", "GOOGLE_APPLICATION_CREDENTIALS_JSON"}
OBSOLETE_SETTINGS = {
    "OPENAI_API_KEY", "OPENAI_MODEL", "OPENAI_CV_MODEL", "LLM_OPENAI_MODEL",
    "FACE_MATCH_OPENAI_MODEL", "OPENAI_ADMIN_API_KEY", "OPENAI_CREDIT_BALANCE_USD",
    "INFRA_MONTHLY_OPENAI_INR", "MAILGUN_API_KEY", "MAILGUN_DOMAIN",
    "MAILGUN_FROM_EMAIL", "MAILGUN_FROM_NAME", "LLM_PRIMARY_PROVIDER",
    "LLM_SECONDARY_PROVIDER", "LLM_TERTIARY_PROVIDER", "CV_SCORING_MODEL", "GROQ_CV_MODEL",
}


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


def inspect_backend(values, production, allow_runtime_secrets=False):
    errors, warnings = [], []
    required = ["MONGODB_URI", "DATABASE_NAME", "FLASK_SECRET_KEY", "JWT_SECRET_KEY",
                "INVITE_TOKEN_SECRET", "FRONTEND_URL", "CORS_ORIGINS", "GCS_BUCKET_NAME"]
    if production:
        if allow_runtime_secrets and not values.get("REDIS_URL"):
            warnings.append("REDIS_URL is deferred to Cloud Run Secret Manager; verify genhire-redis-url is injected at runtime")
        else:
            required += ["REDIS_URL"]
        if values.get("RATE_LIMIT_REQUIRE_REDIS") != "true":
            errors.append("RATE_LIMIT_REQUIRE_REDIS must be true in production")
        if "PORT" in values:
            errors.append("Omit PORT from the Cloud Run import file")
        for key in CLOUD_ADC_OVERRIDES:
            if values.get(key):
                errors.append(f"Keep {key} empty in the production profile and omit it from Cloud Run variables for its service identity")
        if "GOOGLE_APPLICATION_CREDENTIALS" in values and not values.get("GOOGLE_APPLICATION_CREDENTIALS"):
            warnings.append("Omit GOOGLE_APPLICATION_CREDENTIALS from Cloud Run variables, including blank assignments; an empty SDK path blocks ADC in older images")
    for key in required:
        if not values.get(key) or PLACEHOLDER.search(values[key]):
            errors.append(f"{key} is missing or contains a placeholder")
    if production and values.get("REDIS_URL") and not values["REDIS_URL"].startswith(("redis://", "rediss://")):
        errors.append("REDIS_URL must use redis:// or rediss://")
    for key in ("REDIS_CONNECT_TIMEOUT_MS", "REDIS_SOCKET_TIMEOUT_MS"):
        value = values.get(key, "")
        if not value.isdigit() or not 100 <= int(value) <= 30000:
            errors.append(f"{key} must be an integer between 100 and 30000 milliseconds")
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
    # Cloud Run uses its attached service account through ADC. Explicit signing
    # credentials remain supported for local development and legacy deployments.
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

    oa_errors, oa_warnings = inspect_oa(values)
    errors.extend(oa_errors)
    warnings.extend(oa_warnings)
    return errors, warnings


def inspect_oa(values):
    """Flag-aware offline readiness checks. Never substitutes for live evidence."""
    errors, warnings = [], []
    flags = [key for key in values if key.startswith('GENHIRE_') and key.endswith(('_ENABLED', '_ACCEPTED'))]
    for key in flags:
        if values[key] not in ('true', 'false'):
            errors.append(f'{key} must be true or false')
    enabled = lambda key: values.get(key) == 'true'
    dependencies = {
        'GENHIRE_OA_RUNTIME_ENABLED': ['GENHIRE_WORKFLOW_ENABLED', 'GENHIRE_SCHEDULING_ENABLED',
            'GENHIRE_OA_INTEGRITY_ENABLED', 'GENHIRE_OA_EVALUATION_ENABLED', 'GENHIRE_OA_EVALUATION_ACCEPTED', 'GENHIRE_OA_SECURITY_ACCEPTED'],
        'GENHIRE_MOCK_OA_ENABLED': ['GENHIRE_WORKFLOW_ENABLED', 'GENHIRE_ASSESSMENT_GENERATION_ENABLED',
            'GENHIRE_OA_RUNTIME_ENABLED', 'GENHIRE_MOCK_OA_CONTENT_ACCEPTED'],
        'GENHIRE_COMPANY_HIRING_ENABLED': ['GENHIRE_WORKFLOW_ENABLED'],
        'GENHIRE_OA_MEDIA_ENABLED': ['GENHIRE_OA_INTEGRITY_ENABLED', 'GENHIRE_OA_MEDIA_ACCEPTED'],
    }
    for key, required in dependencies.items():
        if enabled(key):
            for dependency in required:
                if not enabled(dependency): errors.append(f'{key} requires {dependency}=true after its actual acceptance')
    for key, raw in values.items():
        if key.startswith('GENHIRE_') and key.endswith('_CREDITS') and raw and (not raw.isdigit() or len(raw) > 9):
            errors.append(f'{key} must be a nonnegative integer wallet-credit amount')
    limits = {'GENHIRE_SQL_MONTHLY_EXECUTION_LIMIT': (1, 200), 'GENHIRE_SPHERE_MONTHLY_SUBMISSION_LIMIT': (1, 500),
        'GENHIRE_OA_EXECUTION_CONCURRENCY': (1, 4), 'GENHIRE_OA_EXECUTION_QUEUE_LIMIT': (1, 5000),
        'GENHIRE_OA_RAW_RETENTION_DAYS': (1, 90), 'GENHIRE_OA_SUMMARY_RETENTION_DAYS': (30, 730)}
    for key, (lower, upper) in limits.items():
        raw = values.get(key)
        if raw is not None and (not raw.isdigit() or not lower <= int(raw) <= upper):
            errors.append(f'{key} must be an integer between {lower} and {upper}')
    for key, expected in {'GENHIRE_SQL_REGION': 'europe-west1', 'GENHIRE_SQL_MAX_CONCURRENT_EXECUTIONS': '1',
                          'GENHIRE_SQL_TASK_TIMEOUT_SECONDS': '60'}.items():
        if key in values and values[key] != expected:
            errors.append(f'{key} does not match the supported SQL pilot configuration')
    required = ['SPHERE_COMPILERS_ENDPOINT', 'SPHERE_COMPILERS_TOKEN', 'SPHERE_PROBLEMS_ENDPOINT', 'SPHERE_PROBLEMS_TOKEN',
        'SPHERE_MASTER_JUDGE_ID', 'SPHERE_TESTCASE_JUDGE_ID', 'SPHERE_RUNTIME_PROFILES_JSON', 'GENHIRE_SQL_PROJECT', 'GENHIRE_SQL_ARTIFACT_BUCKET',
        'GENHIRE_SQL_POSTGRESQL_JOB', 'GENHIRE_SQL_MYSQL_JOB', 'GENHIRE_EXECUTOR_ISOLATION_POLICY_ID']
    missing = [key for key in required if not values.get(key) or values[key] == '{}' or PLACEHOLDER.search(values[key])]
    if 'GENHIRE_WORKFLOW_ENABLED' in values and missing:
        message = 'OA owner configuration remains unfilled: '+', '.join(missing)
        (errors if enabled('GENHIRE_ASSESSMENT_EXECUTION_ENABLED') else warnings).append(message)
    if enabled('GENHIRE_ASSESSMENT_EXECUTION_ENABLED'):
        for product in ('COMPILERS', 'PROBLEMS'):
            key = 'SPHERE_'+product+'_ENDPOINT'
            try:
                url = urlsplit(values.get(key, ''))
                valid = (url.scheme == 'https' and url.port in (None, 443) and not url.query and not url.fragment
                    and not url.username and not url.password and url.path.rstrip('/') == '/api/v4'
                    and re.fullmatch(r'[a-zA-Z0-9-]+\.'+product.lower()+r'\.sphere-engine\.com', url.hostname or ''))
            except ValueError:
                valid = False
            if not valid: errors.append(f'{key} must use the account-specific HTTPS v4 endpoint without credentials/query')
        try:
            profiles = json.loads(values.get('SPHERE_RUNTIME_PROFILES_JSON', '{}'))
            targets = {'python': '3.12', 'javascript': '22', 'java': '21', 'cpp': 'C++20'}
            if not isinstance(profiles, dict) or set(profiles) != set(targets): raise ValueError()
            for language, label in targets.items():
                p = profiles[language]
                if (not isinstance(p, dict) or set(p) != {'compiler_id', 'version_id', 'version_name', 'runtime_label'}
                    or any(type(p.get(k)) is not int or p[k] <= 0 for k in ('compiler_id', 'version_id'))
                    or not isinstance(p.get('version_name'), str) or not p['version_name'] or p.get('runtime_label') != label): raise ValueError()
        except (ValueError, TypeError):
            errors.append('SPHERE_RUNTIME_PROFILES_JSON needs four account-verified positive compiler/version pins with approved runtime labels')
        for key in ('SPHERE_MASTER_JUDGE_ID', 'SPHERE_TESTCASE_JUDGE_ID'):
            if not values.get(key, '').isdigit() or int(values[key]) < 1:
                errors.append(f'{key} must be an account-approved positive integer')
        warnings.append('Execution is enabled: this offline audit cannot establish current Mongo executor attestation, sandbox isolation or remaining provider quota')
    if enabled('GENHIRE_OA_RUNTIME_ENABLED'):
        warnings.append('Candidate starts enabled: verify live workers, accepted device/security/grading evidence and enforce intended private-cohort admission')
    return errors, warnings


def inspect_frontend(values, backend, production):
    errors = []
    public_keys = {"REACT_APP_API_URL", "REACT_APP_API_BASE", "REACT_APP_FRONTEND_URL",
                   "REACT_APP_GOOGLE_CLIENT_ID", "REACT_APP_TOKEN_KEY", "REACT_APP_USER_KEY",
                   "REACT_APP_KIOSK_DOWNLOAD_URL", "REACT_APP_KIOSK_MAC_DOWNLOAD_URL"}
    for key in values:
        if key not in public_keys:
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


def audit(profile="local", schema_only=False, allow_runtime_secrets=False):
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
            if folder == "python-backend":
                for key in sorted(set(maps[name]) & OBSOLETE_SETTINGS):
                    errors.append(f"{folder}/{name}: remove obsolete {key}; use the canonical provider settings")
        for active, example in [(".env", ".env.example"), (".env.production", ".env.production.example")]:
            if list(maps[active]) != list(maps[example]):
                errors.append(f"{folder}: {active}/{example} keys or order differ")
        if list(maps[".env"]) != list(maps[".env.production"]):
            errors.append(f"{folder}: local/production keys or order differ")
        local_maps[folder], production_maps[folder] = maps[".env"], maps[".env.production"]
    if not schema_only:
        selected = production_maps if profile == "production" else local_maps
        backend = selected["python-backend"]
        problems, notices = inspect_backend(backend, profile == "production", allow_runtime_secrets)
        errors += ["backend: " + problem for problem in problems]
        warnings += ["backend: " + notice for notice in notices]
        errors += ["frontend: " + problem for problem in inspect_frontend(selected["react-frontend"], backend, profile == "production")]
    return errors, warnings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=["local", "production"], default="local")
    parser.add_argument("--schema-only", action="store_true", help="Check key parity and syntax without requiring deployment credentials")
    parser.add_argument("--allow-runtime-secrets", action="store_true", help="Allow blank production REDIS_URL supplied separately by Cloud Run Secret Manager; does not verify the deployed reference")
    args = parser.parse_args()
    errors, warnings = audit(args.profile, args.schema_only, args.allow_runtime_secrets)
    for message in warnings:
        print("NOTICE " + message)
    for message in errors:
        print("ERROR " + message)
    print(f"Environment check: {len(errors)} errors, {len(warnings)} notices. Credential values were not displayed.")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
