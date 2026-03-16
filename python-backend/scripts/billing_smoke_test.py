import json
import os
import sys
import urllib.request
import urllib.error


BASE_URL = os.getenv("SMOKE_BASE_URL", "http://localhost:5000")
RECRUITER_TOKEN = os.getenv("SMOKE_RECRUITER_TOKEN", "")
CANDIDATE_TOKEN = os.getenv("SMOKE_CANDIDATE_TOKEN", "")


def call_api(method, path, token=None, body=None):
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            payload = response.read().decode("utf-8")
            parsed = json.loads(payload) if payload else {}
            return response.getcode(), parsed
    except urllib.error.HTTPError as err:
        payload = err.read().decode("utf-8")
        try:
            parsed = json.loads(payload) if payload else {}
        except Exception:
            parsed = {"raw": payload}
        return err.code, parsed
    except Exception as err:
        return None, {"error": str(err)}


def assert_status(name, actual_status, allowed_statuses):
    ok = actual_status in allowed_statuses
    state = "PASS" if ok else "FAIL"
    print(f"[{state}] {name} -> status={actual_status}, expected={sorted(list(allowed_statuses))}")
    return ok


def extract_plan_slugs(payload):
    if not isinstance(payload, dict):
        return set()

    data_node = payload.get("data")
    if not isinstance(data_node, dict):
        return set()

    plans = data_node.get("plans")
    if not isinstance(plans, list):
        return set()

    slugs = set()
    for plan in plans:
        if not isinstance(plan, dict):
            continue
        slug = plan.get("slug")
        if isinstance(slug, str):
            slugs.add(slug)
    return slugs


def main():
    if not RECRUITER_TOKEN or not CANDIDATE_TOKEN:
        print("Missing tokens. Set SMOKE_RECRUITER_TOKEN and SMOKE_CANDIDATE_TOKEN.")
        sys.exit(2)

    checks = []

    # Auth-scoped plans visibility
    status, data = call_api("GET", "/api/payment/plans", token=RECRUITER_TOKEN)
    checks.append(assert_status("Recruiter can list plans", status, {200}))
    recruiter_slugs = extract_plan_slugs(data)
    checks.append(("candidate-pro" not in recruiter_slugs) and ("candidate-max" not in recruiter_slugs))
    print(f"[{'PASS' if checks[-1] else 'FAIL'}] Recruiter does not see candidate-only paid plans")

    status, data = call_api("GET", "/api/payment/plans", token=CANDIDATE_TOKEN)
    checks.append(assert_status("Candidate can list plans", status, {200}))
    candidate_slugs = extract_plan_slugs(data)
    checks.append(("candidate-pro" in candidate_slugs) and ("candidate-max" in candidate_slugs))
    print(f"[{'PASS' if checks[-1] else 'FAIL'}] Candidate sees candidate paid plans")

    # Subscription + payment history
    status, _ = call_api("GET", "/api/payment/subscriptions/me", token=RECRUITER_TOKEN)
    checks.append(assert_status("Recruiter subscription endpoint", status, {200}))

    status, _ = call_api("GET", "/api/payment/subscriptions/me", token=CANDIDATE_TOKEN)
    checks.append(assert_status("Candidate subscription endpoint", status, {200}))

    status, _ = call_api("GET", "/api/payment/payments/history", token=RECRUITER_TOKEN)
    checks.append(assert_status("Recruiter payment history endpoint", status, {200}))

    status, _ = call_api("GET", "/api/payment/payments/history", token=CANDIDATE_TOKEN)
    checks.append(assert_status("Candidate payment history endpoint", status, {200}))

    # Role-isolated cost statistics
    status, _ = call_api("GET", "/api/recruiter/cost-statistics", token=RECRUITER_TOKEN)
    checks.append(assert_status("Recruiter cost statistics for recruiter", status, {200}))

    status, _ = call_api("GET", "/api/recruiter/cost-statistics", token=CANDIDATE_TOKEN)
    checks.append(assert_status("Recruiter cost statistics blocked for candidate", status, {403}))

    status, _ = call_api("GET", "/api/candidate/cost-statistics", token=CANDIDATE_TOKEN)
    checks.append(assert_status("Candidate cost statistics for candidate", status, {200}))

    status, _ = call_api("GET", "/api/candidate/cost-statistics", token=RECRUITER_TOKEN)
    checks.append(assert_status("Candidate cost statistics blocked for recruiter", status, {403}))

    passed = all(checks)
    print("\nSUMMARY:", "PASS" if passed else "FAIL")
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
