"""Synchronize/annotate the eight dotenv profiles without copying private values.

Read-only by default. --apply writes reviewed defaults/comments, preserving all
nonblank values. Reports contain key names/counts only, never credential values.
"""
import argparse
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
FILES = ('.env', '.env.example', '.env.production', '.env.production.example')
PUBLIC_REFERENCE_DEFAULTS = {
    'INTERVIEW_SILENCE_SECONDS', 'INTERVIEW_INITIAL_WAIT_SECONDS', 'INTERVIEW_MAX_ANSWER_SECONDS',
    'INTERVIEW_SPEECH_LEVEL', 'INTERVIEW_SPEECH_HOLD_MS', 'INTERVIEW_QUESTION_MAX_TOKENS',
    'INTERVIEW_PROVIDER_TIMEOUT_SECONDS', 'INTERVIEW_QUESTION_BUDGET_SECONDS',
}

# None means there is no safe account-specific default. All flags start off.
OA = {
    'GENHIRE_WORKFLOW_ENABLED': ('false', 'Keep false until transactional Mongo, scoped accounts and staging checks pass. Enables the workflow foundation, not all OA features.'),
    'GENHIRE_OA_JOB_SETUP_CREDITS': ('30', '30 wallet credits per recruitment OA setup activation; saving a draft does not charge.'),
    'GENHIRE_OA_ATTEMPT_CREDITS': ('30', 'Provisional owner-editable price: 30 wallet credits per accepted recruitment OA attempt. Review before publishing a paid job; existing pinned attempts are not repriced.'),
    'GENHIRE_MOCK_OA_CREDITS': ('30', '30 wallet credits per validated mock OA purchase including one attempt and basic educational advice.'),
    'GENHIRE_DUAL_PROCTORING_CREDITS': ('10', 'Optional dual-camera extra, only when actual media/storage/device acceptance passes.'),
    'GENHIRE_ADVANCED_OA_ANALYTICS_CREDITS': ('10', 'Reserved price only; deferred advanced analytics must stay hidden/nonbillable.'),
    'GENHIRE_EXTRA_VARIANTS_CREDITS': ('10', 'Credits per explicitly approved extra variant-generation batch; review/publish its content.'),
    'GENHIRE_PLAGIARISM_CHECK_CREDITS': ('10', 'Credits per approved recruitment similarity report; never an automatic cheating verdict. Practice similarity is deferred.'),
    'GENHIRE_ASSESSMENT_EXECUTION_ENABLED': ('false', 'Enable only for deliberate real acceptance, then approved isolated execution. Tokens alone do not establish security.'),
    'SPHERE_COMPILERS_ENDPOINT': (None, 'Sphere dashboard > Compilers API v4 account endpoint: https://ACCOUNT.compilers.sphere-engine.com/api/v4 (no token/query in URL).'),
    'SPHERE_COMPILERS_TOKEN': (None, 'Sphere dashboard > Compilers API access token. Store server-side locally or Secret Manager on GCP; never REACT_APP_*.'),
    'SPHERE_PROBLEMS_ENDPOINT': (None, 'Sphere dashboard > Problems API v4 account endpoint: https://ACCOUNT.problems.sphere-engine.com/api/v4.'),
    'SPHERE_PROBLEMS_TOKEN': (None, 'Sphere dashboard > Problems API access token; arrange access/billing for this product separately.'),
    'SPHERE_RUNTIME_PROFILES_JSON': ('{}', 'Replace {} with one-line raw JSON from BOTH live /compilers catalogs: python/javascript/java/cpp each need compiler_id, version_id, version_name, runtime_label. Labels: 3.12, 22, 21, C++20. See owner guide step 5; do not invent IDs.'),
    'SPHERE_MASTER_JUDGE_ID': (None, 'Run python scripts/admin/discover_sphere_account.py from backend; select the account Generic master judge ID for Problems acceptance. See docs/oa_sphere_sql_setup.md.'),
    'SPHERE_TESTCASE_JUDGE_ID': (None, 'Run backend scripts/admin/discover_sphere_account.py; select the account Ignores extra white spaces testcase judge ID for the echo canary; do not guess IDs.'),
    'GENHIRE_SQL_PROJECT': (None, 'Google Cloud Console project selector > existing GenHire PROJECT ID, not display name/project number. Use the project where SQL jobs are deployed.'),
    'GENHIRE_SQL_REGION': ('europe-west1', 'Approved Belgium region; current SQL adapter requires exactly europe-west1.'),
    'GENHIRE_SQL_ARTIFACT_BUCKET': (None, 'After infra/oa_sql Terraform apply, copy artifact_bucket output: bare private bucket name, no gs://. Separate from application evidence bucket.'),
    'GENHIRE_SQL_POSTGRESQL_JOB': ('genhire-oa-sql-postgresql', 'Planned Terraform job name, not proof it exists. Deploy/verify the PostgreSQL 17 job in the selected project/region.'),
    'GENHIRE_SQL_MYSQL_JOB': ('genhire-oa-sql-mysql', 'Planned Terraform job name, not proof it exists. Deploy/verify the MySQL 8.4 job in the selected project/region.'),
    'GENHIRE_SQL_MONTHLY_EXECUTION_LIMIT': ('200', 'Hard pilot range 1-200 dispatches per UTC month, including preflight/uncertain dispatches; not number of candidates.'),
    'GENHIRE_SPHERE_MONTHLY_SUBMISSION_LIMIT': ('500', 'Hard pilot range 1-500 submissions/month including reference validation/preflight/public/final cases; see renewal/quota blocker in owner guide.'),
    'GENHIRE_SQL_MAX_CONCURRENT_EXECUTIONS': ('1', 'Pilot SQL concurrency is fixed globally at one across both engines; this does not enable higher capacity.'),
    'GENHIRE_SQL_TASK_TIMEOUT_SECONDS': ('60', 'Pilot SQL Cloud Run task timeout is fixed at 60 seconds; keep deployment consistent.'),
    'GENHIRE_SQL_MONTHLY_BUDGET_USD': ('10', 'SQL-only monthly target, not a spending cap. Verify real Cloud Billing alerts; worker/AI/Sphere costs are separate.'),
    'GENHIRE_ASSESSMENT_GENERATION_ENABLED': ('false', 'Enable after funded supported AI credentials/JSON quality and authoring/practice workers are verified.'),
    'GENHIRE_OA_REGENERATION_CREDITS': ('10', 'Credits per explicitly approved regeneration; failed generation returns the applicable reservation.'),
    'GENHIRE_EXECUTOR_ISOLATION_POLICY_ID': (None, 'Choose a versioned ID only after an actual sandbox/image isolation review. Must match policy_id in private security-review JSON; no guessed approval.'),
    'GENHIRE_SCHEDULING_ENABLED': ('false', 'Enable only with active scheduler, correct timezone/windows and scoped workflow verification.'),
    'GENHIRE_HIRING_EMAILS_ENABLED': ('false', 'Enable last, after verified sender, approved recipients/content and unknown-delivery tests. Scheduler and company email workers are separate.'),
    'GENHIRE_OA_RUNTIME_ENABLED': ('false', 'Keep off until actual grading/security acceptance and integrity/worker readiness. Disabling new starts must not stop accepted saves/deadlines.'),
    'GENHIRE_OA_EVALUATION_ACCEPTED': ('false', 'Operator assertion ONLY after actual grading/failure/billing acceptance; a test double or key is not acceptance.'),
    'GENHIRE_OA_SECURITY_ACCEPTED': ('false', 'Operator assertion ONLY after secure launch/device/scoped-token/isolation and accommodation tests pass.'),
    'GENHIRE_OA_EVALUATION_ENABLED': ('false', 'Enable with supervised evaluation/execution worker. Keep evaluation running while draining already accepted attempts.'),
    'GENHIRE_OA_EXECUTION_CONCURRENCY': ('2', 'Shared code/SQL task dispatcher pilot range 1-4. SQL retains its separate one-execution limit.'),
    'GENHIRE_OA_EXECUTION_QUEUE_LIMIT': ('1000', 'Shared queue bound, range 1-5000. Full queues return backpressure; unknown external POSTs must be reconciled.'),
    'GENHIRE_OA_GRADING_CASE_LIMIT': ('200', 'Maximum grading cases per attempt. This is not a provider monthly allowance.'),
    'GENHIRE_OA_INTEGRITY_ENABLED': ('false', 'Enable only after scoped launch/consent/preflight, kiosk/accommodation and retention checks.'),
    'GENHIRE_COMPANY_HIRING_ENABLED': ('false', 'Enable after recruiter review/release/export/company-stage tests; no automatic company interview is performed.'),
    'GENHIRE_MOCK_OA_ENABLED': ('false', 'Enable paid mock purchase/start only after shared runtime, actual content acceptance and generation/advice worker readiness.'),
    'GENHIRE_MOCK_OA_CONTENT_ACCEPTED': ('false', 'Operator assertion after actual role-question/explanation quality review; AI self-agreement alone is insufficient.'),
    'GENHIRE_OA_KIOSK_RELEASE_ID': ('1.3.0', 'Must match installed/tested packaged runtime release; upload the matching signed installer and update public frontend download URL.'),
    'GENHIRE_OA_MEDIA_ENABLED': ('false', 'Optional sampled camera/dual images. Requires private GCS, signing permissions, models and real device tests; no continuous video claim.'),
    'GENHIRE_OA_MEDIA_ACCEPTED': ('false', 'Operator assertion only after actual camera/phone/GCS/detector/retention acceptance.'),
    'GENHIRE_OA_RAW_RETENTION_DAYS': ('30', 'Raw evidence retention, supported 1-90 days; run retention worker and respect reasoned holds.'),
    'GENHIRE_OA_SUMMARY_RETENTION_DAYS': ('180', 'Summary retention, supported 30-730 days. Core scores/history follow separate policy.'),
    'GENHIRE_OA_VARIANTS_ENABLED': ('false', 'Optional; enable after a real independently reviewed/published pool and allocation verification.'),
    'GENHIRE_OA_SIMILARITY_ENABLED': ('false', 'Optional recruitment report after grading; human interpretation only, no objective-mark changes.'),
    'GENHIRE_CAMERA_PROCTORING_CREDITS': ('10', 'Optional sampled desktop-camera extra, billable only when the implemented media tier is available.'),
}

NOTES = {
    'REACT_APP_API_URL': 'Public API origin: Cloud Run service URL, without /api; local uses http://localhost:5000. Match the intended environment, then rebuild.',
    'REACT_APP_API_BASE': 'Public API origin plus /api exactly once; takes precedence over API_URL. Copy the matching backend origin, not the Vercel frontend URL.',
    'REACT_APP_FRONTEND_URL': 'Public website origin: localhost:3000 locally, the intended Vercel/custom domain in production. Match backend FRONTEND_URL/CORS.',
    'REACT_APP_GOOGLE_CLIENT_ID': 'Public OAuth WEB client ID from Google Cloud OAuth console; match backend GOOGLE_CLIENT_ID and authorized frontend origins.',
    'REACT_APP_TOKEN_KEY': 'Browser session-storage name only, not a credential. Preserve the existing value to avoid an unintended login-state reset.',
    'REACT_APP_USER_KEY': 'Browser metadata storage name only; keep aligned with the existing account session configuration.',
    'REACT_APP_KIOSK_DOWNLOAD_URL': 'Public HTTPS URL of the uploaded/tested signed Windows OA installer (release 1.3.0). Existing URL presence does not verify its contents; never make an evidence bucket public.',
    'MONGODB_URI': 'MongoDB Atlas > Connect > Drivers, or your isolated local replica-set URI. OA needs multi-document transactions; never use a production DB for local experiments.',
    'GOOGLE_CLIENT_ID': 'Google Cloud > Google Auth Platform/OAuth web client > Client ID; match frontend public client ID and authorized origins.',
    'FLASK_SECRET_KEY': 'Generate a stable private random secret locally (Python secrets.token_urlsafe(48)); preserve existing production value to avoid invalidating sessions.',
    'JWT_SECRET_KEY': 'Generate a separate stable private random signing secret (Python secrets.token_urlsafe(48)); preserve existing production value.',
    'INVITE_TOKEN_SECRET': 'Generate a separate stable private random invitation secret; do not rotate working values during OA setup.',
    'DEEPSEEK_API_KEY': 'DeepSeek platform account > API keys; fund/verify the configured text model. Backend/AI workers only.',
    'GOOGLE_API_KEY': 'Google AI Studio > API keys; verify billing/quota and configured Gemini model access. Backend only.',
    'GROQ_API_KEY': 'Groq console > API keys; fund/verify model and STT access. Backend only.',
    'ZEPTOMAIL_API_KEY': 'Verified ZeptoMail Mail Agent > send-mail token; match the verified sender/domain.',
    'RAZORPAY_KEY_ID': 'Razorpay Dashboard > API keys; use a matching test-mode pair locally and approved live pair in production.',
    'RAZORPAY_KEY_SECRET': 'Razorpay Dashboard > API keys > paired secret; server only, never a frontend build value.',
    'RAZORPAY_WEBHOOK_SECRET': 'Razorpay Dashboard > Webhooks > backend /api/payment/webhooks/razorpay > signing secret. Set this SAME secret there and here; API key secret is different.',
    'GCS_BUCKET_NAME': 'Google Cloud Storage > intended PRIVATE application artifact/evidence bucket name (no gs://); do not reuse SQL one-day retention policy.',
    'REDIS_URL': 'Local running Redis URI or production managed Redis connection secret. In production keep blank only if Cloud Run Secret Manager injects REDIS_URL; preserve that existing reference.',
    'SENTRY_DSN': 'OPTIONAL: leave blank to disable external error reporting, or copy backend project DSN from Sentry project settings.',
    'LANGCHAIN_API_KEY': 'OPTIONAL: required only when tracing is enabled; get LangSmith settings API key. Leave blank with LANGCHAIN_TRACING_V2=false.',
    'GCS_SERVICE_ACCOUNT_JSON': 'OPTIONAL: leave blank with attached/impersonated Google ADC. Local explicit signing JSON only if deliberately selected; never expose to frontend.',
    'GCS_SERVICE_ACCOUNT_KEY': 'OPTIONAL: leave blank with ADC; otherwise local private signing-key file path. Omit overrides on Cloud Run.',
    'GOOGLE_APPLICATION_CREDENTIALS': 'KEEP BLANK for local gcloud ADC/impersonation and Cloud Run attached identity; omit on Cloud Run. Only use a real private local key-file path for an intentional key-based setup.',
    'GOOGLE_APPLICATION_CREDENTIALS_JSON': 'KEEP BLANK with Google ADC/attached identity. Do not deploy local account keys to Cloud Run or Vercel.',
    'PROCTORING_OBJECT_MODEL_PATH': 'OPTIONAL override: blank uses backend models/proctoring/yolov8n.onnx. Provision that gitignored artifact into the final image and verify detection; a path alone is not a model.',
    'FACE_MATCH_GROQ_MODEL': 'OPTIONAL: blank disables this Groq face-match route; fill only a currently account-supported IMAGE model, not a text-only GPT-OSS model.',
    'GCP_BILLING_EXPORT_BQ_LOCATION': 'OPTIONAL: if BigQuery billing export is enabled, copy dataset location from BigQuery dataset details (do not guess from Cloud Run region). Otherwise leave blank.',
    'REACT_APP_KIOSK_MAC_DOWNLOAD_URL': 'OPTIONAL: leave blank until a real tested/signed Mac installer is published; then set its public HTTPS URL, never a Windows exe.',
}
GENERATED = ('# OA OWNER:', '# OWNER ACTION:', '# SAFE DEFAULT:', '# OPTIONAL / ADC:', '# SETUP NOTE:')
ASSIGNMENT = re.compile(r'^([A-Za-z_][A-Za-z0-9_]*)=(.*)$')


def blocks(text):
    result, prefix = {}, []
    for number, line in enumerate(text.splitlines(), 1):
        match = ASSIGNMENT.fullmatch(line)
        if match:
            key, raw = match.groups()
            if key in result:
                raise ValueError('Duplicate environment key: '+key)
            result[key] = ([v for v in prefix if not v.startswith(GENERATED)], raw)
            prefix = []
        elif not line.strip() or line.lstrip().startswith('#'):
            prefix.append(line)
        else:
            raise ValueError('Unsupported assignment at line '+str(number))
    return result


def value(raw):
    return raw.strip().strip('"\'')


def unfilled(raw):
    text = value(raw)
    return not text or text == '{}' or bool(re.search(r'(?i)(REPLACE_WITH|YOUR_|PLACEHOLDER|path/to/service-account)', text))


def prepare(root):
    plans, reports = {}, []
    for folder in ('python-backend', 'react-frontend'):
        paths = [root / folder / name for name in FILES]
        originals = {p: p.read_text(encoding='utf-8-sig') for p in paths}
        parsed = {p: blocks(text) for p, text in originals.items()}
        reference = parsed[root / folder / '.env.example']
        order = [k for k in reference if k not in OA]
        for mapping in parsed.values():
            order.extend(k for k in mapping if k not in order and k not in OA)
        if folder == 'python-backend': order += list(OA)
        for path in paths:
            mapping, output, added, defaulted = parsed[path], [], [], []
            scope = 'production server' if folder == 'python-backend' and 'production' in path.name else 'local server' if folder == 'python-backend' else 'PUBLIC frontend build'
            output += ['# OA OWNER: '+scope+' profile. Search OWNER ACTION below; see docs/oa_owner_setup_guide.md.',
                '# OA OWNER: Private filled values are preserved. Comments/defaults do not provision services or approve rollout.']
            for key in order:
                exists = key in mapping
                prefix, raw = mapping.get(key, reference.get(key, ([], '""')))
                if not exists:
                    added.append(key)
                    # Never copy values across profiles; only public reference defaults.
                    if key not in OA and key not in PUBLIC_REFERENCE_DEFAULTS: raw = '""'
                if key in OA:
                    default, note = OA[key]
                    if not exists: raw = json.dumps(default if default is not None else '')
                    elif not value(raw) and default is not None:
                        raw = json.dumps(default); defaulted.append(key)
                    if key == 'GENHIRE_WORKFLOW_ENABLED':
                        output += ['', '# ============================================================================', '# OA owner configuration - server only, deployment/acceptance flags stay off', '# ============================================================================']
                    marker = '# OWNER ACTION: ' if default is None or key == 'SPHERE_RUNTIME_PROFILES_JSON' else '# SAFE DEFAULT: '
                    if marker == '# OWNER ACTION: ' and not unfilled(raw): marker = '# SETUP NOTE: '
                    output += [marker+note, key+'='+raw]
                else:
                    if folder == 'python-backend':
                        prefix = [line.replace('# Import the entire production file into Cloud Run Variables & Secrets; never into Vercel.',
                            '# Cloud Run: merge reviewed settings, preserve secret references and omit blank secrets/ADC overrides; never import into Vercel.') for line in prefix]
                    output += prefix
                    note = NOTES.get(key)
                    if note:
                        marker = '# OPTIONAL / ADC: ' if note.startswith(('OPTIONAL', 'KEEP BLANK')) else '# OWNER ACTION: ' if unfilled(raw) else '# SETUP NOTE: '
                        output.append(marker+note)
                    output.append(key+'='+raw)
            rendered = '\n'.join(output).rstrip()+'\n'
            # Guard against secret loss; only empty values can receive defaults.
            after = blocks(rendered)
            for key, (_, raw) in mapping.items():
                if value(raw) and after[key][1] != raw:
                    raise ValueError('Refusing to change existing filled value: '+key)
            plans[path] = rendered
            reports.append(dict(file=str(path.relative_to(root)), keys=len(after), added_keys=added, defaulted_empty_keys=defaulted))
    return plans, reports


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    plans, reports = prepare(ROOT)
    if args.apply:
        for path, text in plans.items():
            path.write_text(text, encoding='utf-8')
    print(json.dumps(dict(mode='apply' if args.apply else 'dry_run', files=reports, filled_values_preserved=True), indent=2))


if __name__ == '__main__':
    main()
