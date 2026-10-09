"""Probe Redis-backed request limits without customer keys or credential output.

Use the backend virtualenv. The probe creates one random, ten-second quota key;
it does not start the real app, use the database, or change existing limits.
"""
import argparse
import hashlib
import os
from pathlib import Path
import sys
import uuid

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))


def load_profile(profile):
    from dotenv import dotenv_values
    name = ".env.production" if profile == "production" else ".env"
    values = dotenv_values(BACKEND / name, interpolate=False)
    for key in ("REDIS_URL", "RATE_LIMIT_NAMESPACE", "RATE_LIMIT_REQUIRE_REDIS"):
        if key not in os.environ and values.get(key) is not None:
            os.environ[key] = values[key]


def probe():
    from flask import Flask
    from middleware import rate_limiter as limits
    url = os.getenv("REDIS_URL", "").strip()
    if not url:
        print("FAIL: REDIS_URL is empty. Local memory limits can work, but this command verifies Redis.")
        return 1
    policy = "setup_probe_" + uuid.uuid4().hex
    namespace = os.getenv("RATE_LIMIT_NAMESPACE", "genhire")
    digest = hashlib.sha256(b"setup-check").hexdigest()
    key = f"{namespace}:quota:{policy}:{digest}"
    client = None
    try:
        client = limits.store._client()
        if not client.ping():
            raise RuntimeError()
        app = Flask(__name__)

        @app.get("/probe")
        def endpoint():
            blocked = limits.check_limit(policy, "setup-check", 2, 10)
            return blocked if blocked is not None else ("ok", 200)

        with app.test_client() as requests:
            responses = [requests.get("/probe") for _ in range(3)]
        statuses = [response.status_code for response in responses]
        if statuses != [200, 200, 429]:
            print("FAIL: Redis quota probe returned unexpected statuses; check writable Lua/EVAL access and service availability.")
            return 1
        limited = responses[-1]
        ttl = client.ttl(key)
        if (limited.get_json().get("error_code") != "rate_limited"
                or not 1 <= int(limited.headers.get("Retry-After", "0")) <= 10
                or not 0 < ttl <= 10):
            print("FAIL: Quota expiry or Retry-After validation failed.")
            return 1
        print("PASS: Redis PING, atomic Lua counter, TTL expiry, HTTP 200/200/429 and Retry-After.")
        print("Only a random short-lived probe key was used. URLs, passwords and customer quotas were not displayed or inspected.")
        return 0
    except Exception as error:
        # Redis exceptions often contain server URLs/auth details: print type only.
        print(f"FAIL: Redis connection/probe failed ({type(error).__name__}). Check TCP URL, TLS, credentials and network reachability.")
        return 1
    finally:
        if client is not None:
            try:
                client.delete(key)  # Only this invocation's randomly named probe key.
            except Exception:
                pass  # It has a ten-second TTL if cleanup cannot reach Redis.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=["local", "production"], default="local")
    args = parser.parse_args()
    try:
        load_profile(args.profile)
        return probe()
    except ImportError:
        print("FAIL: Use python-backend/venv/Scripts/python.exe after installing backend requirements.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
