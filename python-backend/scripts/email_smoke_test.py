import argparse
import os
import secrets
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))


REQUIRED_ENV_KEYS = [
    "EMAIL_PROVIDER",
    "ZEPTOMAIL_API_KEY",
    "ZEPTOMAIL_FROM_EMAIL",
    "FRONTEND_URL",
    "REQUIRE_EMAIL_VERIFICATION",
]


def fail(message: str) -> None:
    print(f"[FAIL] {message}")
    sys.exit(1)


def pass_check(message: str) -> None:
    print(f"[PASS] {message}")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Validate production email config and optionally send a real test email."
    )
    parser.add_argument(
        "--env-file",
        default=os.getenv("ENV_FILE", ".env.production"),
        help="Dotenv file to load relative to python-backend. Defaults to .env.production.",
    )
    parser.add_argument(
        "--to",
        default=os.getenv("TEST_EMAIL", ""),
        help="Recipient for --send. Can also be provided with TEST_EMAIL.",
    )
    parser.add_argument(
        "--kind",
        choices=("verification", "reset"),
        default="verification",
        help="Which auth email method to exercise when --send is used.",
    )
    parser.add_argument(
        "--send",
        action="store_true",
        help="Send one real email through the configured provider.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    os.environ.setdefault("ENV_FILE", args.env_file)
    os.environ.setdefault("FLASK_ENV", "production")
    os.environ.setdefault("EMAIL_FAIL_FAST", "true")

    from config.env_loader import load_environment

    load_environment()

    missing = [key for key in REQUIRED_ENV_KEYS if not os.getenv(key)]
    if missing:
        fail(f"Missing required env vars: {', '.join(missing)}")
    pass_check("required email env vars are present")

    if os.getenv("REQUIRE_EMAIL_VERIFICATION", "").strip().lower() != "true":
        fail("REQUIRE_EMAIL_VERIFICATION must be true for hosted signup verification")
    pass_check("email verification is enabled")

    frontend_url = os.getenv("FRONTEND_URL", "").strip().rstrip("/")
    if "localhost" in frontend_url or "127.0.0.1" in frontend_url:
        fail(f"FRONTEND_URL is local, not hosted: {frontend_url}")
    if not frontend_url.startswith("https://"):
        fail(f"FRONTEND_URL should be https for hosted email links: {frontend_url}")
    pass_check(f"hosted frontend URL is {frontend_url}")

    from services.email_service import EmailService

    service = EmailService()
    provider_name = getattr(service.provider, "name", "unknown")
    if provider_name == "noop":
        fail("email provider resolved to noop; real emails will not be sent")
    pass_check(f"email provider resolved to {provider_name}")

    sample_token = f"smoke-{secrets.token_urlsafe(12)}"
    sample_path = "verify-email" if args.kind == "verification" else "reset-password"
    print(f"[INFO] sample {args.kind} link: {service.frontend_url}/{sample_path}?token={sample_token}")

    if not args.send:
        print("[INFO] dry run only. Add --send --to you@example.com to send one real email.")
        return 0

    if not args.to:
        fail("--send requires --to or TEST_EMAIL")

    if args.kind == "verification":
        sent = service.send_verification_email(args.to, sample_token, "GenHire Smoke Test")
    else:
        sent = service.send_password_reset_email(args.to, sample_token, "GenHire Smoke Test")

    if not sent:
        fail(f"provider returned False while sending {args.kind} email")

    pass_check(f"sent {args.kind} email to {args.to}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())