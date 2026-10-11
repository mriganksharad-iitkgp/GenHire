# Required owner setup: Redis, rate limits and remaining services

**12 October recovery update:** revision `hrtech-00149-5dg` now serves 100% of
traffic and returns HTTP 200 for health and Google-auth preflight. Removing the
empty ordinary `GOOGLE_APPLICATION_CREDENTIALS` variable restored attached
identity discovery; the HTTP startup probe and Redis secret reference are in
place. Pending workspace fixes prevent blank overrides and remove duplicate
wallet scans that made cold startup take minutes. Deploy those source changes
and verify actual login. Follow
[Backend startup and login recovery](backend-startup-and-login-recovery.md)
for the verified result, source deployment steps and recovery commands. The
guide retains the resolved `actAs` repair separately.

**11 October recovery update:** the Cloud Run worker logs confirm an old image
crashing on its explicit GCS credential requirement. Follow
[Backend startup and login recovery](backend-startup-and-login-recovery.md) first.
The workspace supports Cloud Run ADC and local Redis has been verified. The
owner reports production Redis is injected from Secret Manager
`genhire-redis-url:latest`; `REDIS_URL=""` in `.env.production` is intentional.
DeepSeek/production webhook values are populated. The table below is
the original 9 October audit, not the current credential state. Mobile recording
and deployment/model checks remain relevant. The 11 October kiosk 1.2.2 update
enables mobile recording in all four backend environment files; also enable it
in the running Cloud Run revision. Follow
[Interview setup fixes and kiosk 1.2.2](interview-setup-recovery.md).

Audit date: **9 October 2026 (IST)**. Follow the actions below before considering
production ready. The audit inspected the current private configuration and source;
it did not authenticate to your provider dashboards, deploy resources or spend credits.
A populated key proves configuration presence, not account access or available quota.

## 1. What is required now

| Priority | Finding in the current workspace | Your action |
| --- | --- | --- |
| Required for production boot | `REDIS_URL` is empty; production has `RATE_LIMIT_REQUIRE_REDIS=true`. | Create/connect Redis and inject its URL into Cloud Run. Follow section 3. |
| Required for the primary LLM | `DEEPSEEK_API_KEY` is empty locally and in production. | Create/fund the key or explicitly choose a different supported provider order. See section 7. |
| Required for payment webhooks | Local `RAZORPAY_WEBHOOK_SECRET` is a placeholder; production is empty. | Set up the signed webhook and matching secret. See section 8. |
| Required if jobs use a second camera | `MOBILE_RECORDING_ENABLED=false` in both private files. | Enable it where dual-camera interviews are intended and verify phone pairing. See section 9. |
| Required for deployed object detection | The default ONNX model **is present locally**. Its path setting is empty, which correctly falls back to that file. The binary is gitignored. | Include the model in the deployment build context/image; a Git checkout alone will omit it. |
| Incomplete optional identity/head-pose coverage | `PROCTORING_IDENTITY_ENABLED=true`, but the selected backend environment lacks DeepFace, TensorFlow and MediaPipe. The default local VGG-Face weight file was not found. | Disable optional identity continuity until you provision/test its runtime, or complete the runtime deployment. Do not expect an env flag alone to enable it. |
| Required deployment verification | The prior production `/health` probe returned HTTP 503. | Inspect Cloud Run revision logs and deploy a healthy revision after resolving its actual error. Redis is a known local-config blocker, not a confirmed diagnosis of that remote revision. |
| Optional Mac support | `REACT_APP_KIOSK_MAC_DOWNLOAD_URL` is empty. | Build/publish a compatible Mac release if you offer Mac support. |
| Optional error monitoring | `SENTRY_DSN` is empty. | Configure Sentry if you want external error monitoring. It does not block app operation. |

MongoDB, authentication secrets, Google OAuth, ZeptoMail, Gemini, Groq, Razorpay
API keys and GCS signing configuration are populated. Their external permissions,
active billing, DNS, provider quotas and deployed values still need confirmation.
The BigQuery billing-export table setting is populated; its location setting is
optional when the API can infer the dataset location. Empty alternate GCS credential
fields and `FACE_MATCH_GROQ_MODEL` are intentional, not additional required secrets.

## 2. How rate limiting currently works

Source: `python-backend/middleware/rate_limiter.py`.

- Local development with empty `REDIS_URL` and `RATE_LIMIT_REQUIRE_REDIS=false`
  already has bounded in-memory counters. They are per process and reset on restart.
- A configured Redis URL uses atomic Lua `INCR`/`EXPIRE`/`TTL` counters, shared by
  all processes using that Redis database and `RATE_LIMIT_NAMESPACE`.
- Production requires Redis to respond to `PING` at startup. Missing/unreachable
  Redis prevents boot. Failure after startup returns HTTP **503** with
  `error_code=protection_unavailable`; it does not silently remove protection.
- Exceeding a working quota returns HTTP **429**, `error_code=rate_limited`, and
  `Retry-After` in seconds. HTTP **503** with `capacity_busy` is a separate workload
  limit, not a Redis error. Socket events return equivalent acknowledgements.
- Limits apply to verified account identity, auth target and/or client network,
  depending on the route. Failed requests can consume quotas too.
- `/health`, `/` and HTTP `OPTIONS` are exempt. Repeated health checks cannot prove
  that rate limiting works. Webhook requests still have network/admission protection.

Redis stores request counters here. It does **not** automatically move interview
sessions, Socket.IO rooms or background queues into a shared store. Keep one
Gunicorn worker and at most one Cloud Run instance for the current application;
adding Redis does not make unrestricted horizontal scaling safe.

## 3. Production Redis: recommended simple route

For the current small deployment, a managed Redis service with a public TLS/TCP
endpoint is the simplest setup. **Upstash Redis** is one compatible option. This is
an implementation recommendation; review its current plan limits/costs before
creating the database. If you require GCP private networking, use section 4 instead.

1. Sign in to the [Upstash console](https://console.upstash.com/), open Redis, and
   create a database named `genhire-production`. Choose a primary region close to
   your **backend in europe-west1**, rather than the location of your laptop.
   Check the selected plan's request, connection and data limits.
   [Creation/region guide](https://upstash.com/docs/redis/overall/getstarted).
2. Open the database's **Connect > TCP** details. Copy the **read/write** connection
   URL. GenHire uses `redis-py` over TCP; an `https://` REST endpoint or read-only
   credential will not work. The URL should resemble the example below; use the
   provider's actual endpoint, port and credential. Keep TLS enabled.
   [TCP client and TLS guidance](https://upstash.com/docs/redis/howto/connect-client).
3. Keep eviction disabled for this quota database. Removing active counters early
   would reset limits. Monitor capacity and command quotas; write rejection or a
   suspended database makes protected requests unavailable.
   [Eviction behavior](https://upstash.com/docs/redis/features/eviction).
4. For this deployment, keep **python-backend/.env.production** free of the Redis
   password; Secret Manager supplies the real URL at runtime. Retain these settings:

   ```dotenv
   REDIS_URL="" # Intentional file blank; Cloud Run injects genhire-redis-url:latest
   RATE_LIMIT_REQUIRE_REDIS="true"
   RATE_LIMIT_NAMESPACE="genhire-production"
   ```

   Copy a provider-generated URL when possible. URL-encode special characters in a
   password if constructing it yourself. Do not put Redis credentials into frontend
   files. Do not reuse production quotas from development: use a separate database
   or at least `RATE_LIMIT_NAMESPACE="genhire-local"` in local configuration.
   The current files use `genhire-local` and `genhire-production` respectively,
   so local checks do not consume production quotas.
5. In GCP **Secret Manager**, create a secret such as `genhire-redis-url` whose value
   is the raw connection URL, without dotenv's outer quotes. Grant the Cloud Run
   **runtime service account** `Secret Manager Secret Accessor` for this secret.
   [Cloud Run secret setup](https://docs.cloud.google.com/run/docs/configuring/services/secrets).
6. Open your existing Cloud Run backend service (confirm its URL matches
   `https://hrtech-628047232128.europe-west1.run.app`). Edit the revision's
   **Variables & Secrets**. Reference the secret as environment variable
   **REDIS_URL**; set `RATE_LIMIT_REQUIRE_REDIS=true` and the production namespace
   as ordinary variables. Remove any conflicting plain `REDIS_URL` entry. Pin the
   intended secret version. No Redis configuration belongs on Vercel.
7. For a public TLS Redis endpoint, the backend needs working outbound internet
   connectivity. A Redis-specific VPC connector is unnecessary. If you already
   route all egress into a VPC, check its NAT/routing/firewall configuration. IP
   allowlisting requires the correct stable egress setup, not your browser's IP.
8. Validate configuration, then deploy the backend through your existing pipeline.
   Read the new revision's startup logs. A successful revision must boot and reach
   Redis. Keep TLS certificate validation; fix certificate/hostname issues rather
   than disabling validation. Current defaults are **5 seconds to connect** and
   **2 seconds to read**, configured by `REDIS_CONNECT_TIMEOUT_MS` and
   `REDIS_SOCKET_TIMEOUT_MS`; verify from the backend network.

No new Redis SDK/package is required: the backend already declares and installs
`redis`. The service must permit writable Lua scripts and the commands used by
GenHire, not only `GET`. [Lua support](https://upstash.com/docs/redis/sdks/py/commands/scripts/eval).

## 4. GCP-only alternative: Memorystore

Choose this instead of section 3 when a Redis instance inside your GCP VPC is
preferred. It adds private networking configuration and provisioned service costs.

1. Enable the Memorystore for Redis API in the backend project. Create a Redis
   instance in `europe-west1`, select its authorized VPC network and appropriate
   capacity/availability tier. Review the displayed estimate before creating it.
2. Record its private IP, port and authentication/TLS requirements. Enable AUTH
   and follow the instance's client TLS/CA configuration when encryption is enabled.
   A self/private CA may require a mounted CA file plus a compatible `rediss://`
   URL option such as `ssl_ca_certs=/secrets/redis-ca.pem`; verify certificate
   handling with the installed client. Do not substitute an unauthenticated public
   Redis server.
3. Configure the Cloud Run service's **Direct VPC egress** with the authorized VPC
   and a subnet in the same region. Use private-range routing for the private Redis
   address, and allow egress to its port. Leave public MongoDB/AI calls with working
   internet routes. Google documents Direct VPC egress for this connection.
   [Memorystore connection steps](https://docs.cloud.google.com/memorystore/docs/redis/connect-redis-instance-cloud-run).
4. Construct `REDIS_URL` using the instance's actual connection settings; then use
   the Secret Manager and Cloud Run steps from section 3. Private IPs are generally
   unreachable from your Windows laptop or a default Cloud Shell session. Test from
   a VM/job/runtime attached to the same network.
5. Account for VPC connection establishment during cold starts. Google documents
   possible startup delays; this app's Redis startup check fails fast. If the new
   revision repeatedly fails before networking becomes ready, bounded startup
   retry handling is a code/deployment prerequisite, not something to bypass by
   disabling production protection.
   [Direct VPC limitations](https://docs.cloud.google.com/run/docs/configuring/vpc-direct-vpc).

## 5. Optional local Redis on Windows

You can keep local memory limits if you only need basic development. To exercise
Redis behavior locally, install/start Docker Desktop with Linux containers, then
run these commands from PowerShell or Git Bash:

```bash
docker run --name genhire-redis -d -p 127.0.0.1:6379:6379 redis:7.4-alpine
docker exec genhire-redis redis-cli ping
```

Expect `PONG`. The port is bound to loopback; this container is a local development
service. If a container of that name already exists, use `docker start genhire-redis`
instead of creating a second one. [Redis Docker instructions](https://redis.io/docs/latest/operate/oss_and_stack/install/install-stack/docker/).

In **python-backend/.env** set:

```dotenv
REDIS_URL="redis://127.0.0.1:6379/0"
RATE_LIMIT_REQUIRE_REDIS="true"
RATE_LIMIT_NAMESPACE="genhire-local"
```

Restart your local backend after editing configuration. `true` makes local startup
reject an unavailable Redis service, matching production's requirement. Setting
`false` does not ignore a broken nonempty URL: if a URL is configured, it is used.
To deliberately return to local memory limits, empty `REDIS_URL` and set the
requirement to `false`. Start an existing container with `docker start genhire-redis`;
stop it when finished with `docker stop genhire-redis`.

## 6. Verify Redis and quotas

From the repository root:

```bash
python scripts/check_environment.py --schema-only
python scripts/check_environment.py --profile production
./python-backend/venv/Scripts/python.exe python-backend/scripts/check_rate_limit_setup.py --profile local
```

For a reachable hosted production Redis URL, change the last command's profile
to `production`. On Linux or inside the deployed image, use its installed `python`
instead of the Windows executable. An injected `REDIS_URL` takes precedence over
the private file, just as it does in the application. The checker needs the backend
requirements; it does not boot the real application or access MongoDB.

Expected success:

```text
PASS: Redis PING, atomic Lua counter, TTL expiry, HTTP 200/200/429 and Retry-After.
```

The command uses one random quota key with a ten-second expiry and removes only
that key afterwards. It checks the actual middleware's 429 response in an isolated
Flask test client; it does not issue customer requests or change your real quotas.
This verifies connectivity **from the machine where you run it**. For private
Memorystore, run it from the authorized VPC network. A local pass does not prove
Cloud Run networking is configured. After redeployment, also check backend health,
login and an authenticated read from `genhire.in` to confirm the deployed path.

Current examples of configured budgets:

| Policy | Requests | Window |
| --- | ---: | ---: |
| Login | 10 | 60 seconds |
| Registration | 5 | 300 seconds |
| Verification/password email | 3 | 300 seconds |
| Application submission | 5 | 60 seconds, plus 30/hour |
| AI operations | 10 | 300 seconds |
| Interview starts | 4 | 300 seconds |
| Interview answers | 60 | 60 seconds |
| General reads | 240 | 60 seconds |

`RATE_LIMIT_<POLICY>_CALLS` and `_WINDOW_SECONDS` control these policies. Keep the
existing values initially. `API_MAX_INFLIGHT`/`AI_MAX_INFLIGHT` and similar settings
bound concurrent work per process; Redis quotas do not replace those limits.

Troubleshooting:

| Result | Meaning / action |
| --- | --- |
| Empty URL | Add the TCP connection URL to the selected private file or injected environment. |
| Authentication failure | Correct the read/write user/password and URL encoding. |
| TLS/certificate failure | Use `rediss://`, the correct hostname, and the provider's required CA. |
| Timeout/connection failure | Check region, endpoint/port, firewall, egress or VPC routing. |
| `EVAL`/write failure | Check command permission, read-only credentials, plan/capacity and eviction policy. |
| HTTP 429 | Quota reached; wait the supplied `Retry-After`, not continuous retries. |
| HTTP 503 `protection_unavailable` | Restore Redis availability. |
| HTTP 503 `capacity_busy` | Workload admission is full; wait or investigate backend capacity. |

`TRUSTED_PROXY_HOPS` is currently `0`. Confirm how your ingress resolves client
addresses before changing it. Incorrect proxy trust can either combine unrelated
visitors into one IP bucket or allow spoofed forwarded headers. See
[Werkzeug proxy-trust guidance](https://werkzeug.palletsprojects.com/en/stable/middleware/proxy_fix/). Trust only the
verified number of sanitizing proxies; do not blindly set it to `1` or accept raw
`X-Forwarded-For` from arbitrary callers. Account/target limits still apply.

## 7. AI and speech accounts

**DeepSeek:** create a key in your DeepSeek account, enable funding/model access,
and put it in `DEEPSEEK_API_KEY` locally and as a production Secret Manager reference.
The current provider order is `deepseek,gemini,groq`. If you intend to use fallback
providers only, deliberately update the provider order/primary-secondary-tertiary
settings together; do not leave an unavailable primary and assume it is running.
Keep your configured model IDs unless changing the chosen stack intentionally.
See [the S2 deployment guide](S2_LOW_DEPLOYMENT.md) for provider/model settings.

**Gemini/Groq:** keys are already present. Verify their project/account access,
quotas and billing with a small test in the intended environment. Groq is required
for the configured Whisper speech-to-text route even when the LLM falls back to
Gemini. Do not move provider keys into `REACT_APP_*` variables.

**Google Standard TTS:** in the backend GCP project, enable billing and the
Cloud Text-to-Speech API. Confirm the Cloud Run runtime service account and its
API access; use its attached identity in production. The two local Google ADC
credential overrides are intentionally absent from the production file. Locally,
the configured credential file exists, but its permission to call TTS still needs
a real test. Start a practice session and verify spoken questions plus submitted
speech transcription. [Google setup](https://docs.cloud.google.com/text-to-speech/docs/get-started).

## 8. Payment webhook setup

1. In Razorpay, select the intended **Test or Live** mode, then open **Account &
   Settings > Webhooks** and add/edit the backend endpoint below.
2. Use this URL:

   ```text
   https://hrtech-628047232128.europe-west1.run.app/api/payment/webhooks/razorpay
   ```

3. Set a strong webhook signing secret. Put the exact same value in backend
   `RAZORPAY_WEBHOOK_SECRET` and a Cloud Run secret reference. It is separate from
   `RAZORPAY_KEY_SECRET`. Do not use the old local placeholder.
4. Enable the event types handled by the current payment service:
   `payment.captured`, `payment.failed`, `order.paid`, `refund.created`.
   Add an alert email and ensure the webhook is enabled.
5. Use matching API key ID/secret pairs for each mode. For local webhook testing,
   use an appropriate HTTPS test tunnel with **test** payment credentials; the
   provider cannot deliver to localhost directly. Never test fake signatures against
   the live wallet as evidence that webhook processing works.
6. Redeploy/restart after injecting the secret. Run a test-mode recharge and verify
   delivery logs, payment status and exactly one wallet credit when events repeat.
   HTTP 200 alone is insufficient: the current controller can acknowledge a
   processing failure, so also inspect application logs and wallet transactions.

These dashboard/signing steps follow [Razorpay's webhook guide](https://razorpay.com/docs/payments/dashboard/account-settings/webhooks/).

## 9. Interview and proctoring deployment

- **Second camera:** if offered/required, set `MOBILE_RECORDING_ENABLED=true` in the
  relevant backend environment and redeploy. A job's `dual_camera` toggle and this
  platform setting must agree. With the current false value, dual-camera jobs
  receive `mobile_recording_disabled` and cannot start. If intentionally offering
  single-camera interviews only, keep it false and do not require a second camera.
- **Object model:** use the existing local ONNX artifact. Validate/include it at
  `/app/models/proctoring/yolov8n.onnx` when building the image; optionally set
  `PROCTORING_OBJECT_MODEL_PATH` to that exact deployed path. Fresh CI/Git builds
  must provision or download the retained artifact before image assembly.
  Keep `PROCTORING_PROHIBITED_OBJECTS="cell phone,book"` with supported class names.
  The binary exists locally, but deployment presence/accuracy is unverified. Follow
  [the model provisioning guide](proctoring-model-setup.md), including its validation
  command/checksum. Do not download weights during a candidate's interview.
- **Optional identity continuity:** the flag is enabled but the selected environment
  lacks DeepFace/TensorFlow. For the current lean deployment, set
  `PROCTORING_IDENTITY_ENABLED=false` until a compatible, tested dependency/weight
  image is prepared. This optional live continuity check is separate from initial
  identity-card/face enrollment. To retain it, provision the exact VGG-Face runtime
  and weights in a separate tested build and measure CPU/memory/latency. Merely
  changing `.env` or installing an unpinned latest package is insufficient.
- **Head pose and other checks:** MediaPipe is absent from the selected environment.
  Head pose, eyeball tracking, voice detection and gaze heatmaps are separate
  capabilities. Reports can show partial/missing checks when their pipelines are
  unavailable. Enable only validated job checks; a zero-infraction report does not
  prove every detector ran. Some of this is runtime/pipeline work, not a missing key.
- **Kiosk release:** publish the rebuilt Windows installer through your existing
  download hosting workflow and verify the configured URL serves that version.
  Installation confirmation is a browser preference; it cannot detect an old app
  version. Candidates with an older speech protocol need the compatible update.
  Mac support needs its own build/signing/release and download URL.
- Test initial enrollment, camera/microphone permissions, second-camera pairing if
  used, a complete answer, disconnect/reconnect, completion and recruiter report.

## 10. Populated services that still need external confirmation

| Service | Steps you need to confirm | Evidence of success |
| --- | --- | --- |
| ZeptoMail | Confirm the selected account/agent, sender domain and account approval/credits. Add the exact DKIM and return-path/CNAME records shown by its console to your DNS and verify them there. The production file requires email verification. | A fresh verification email, password reset and recruiter invitation reach the intended test mailbox; links use `genhire.in`. |
| Google OAuth | Open the OAuth web client used by both apps. Confirm authorized JavaScript origins for `https://genhire.in`, used www/Vercel aliases and local origins. Confirm consent-screen publishing/test-user access. | Google login succeeds for an intended non-admin user in the deployed frontend. |
| MongoDB | Confirm the URI's database user/access, selected database and Atlas/network rules permit the actual Cloud Run egress. Preserve canonical identity records and existing unique indexes. | Healthy boot/database status, login and a persisted test application; no broad production access rule solely for convenience. |
| Cloud Storage | Confirm the configured bucket exists and the GCS signing account can upload/read/delete the needed objects. Inject its JSON/key through Secret Manager and keep the bucket private. The local key file and production JSON are present. | Upload a test CV/JD, preview/download through the app, and confirm the signed URL expires. |
| Cloud Run service | Confirm the deployed image/code, actual injected variables/secrets, runtime service account, one worker/instance and configured backend container port 8080. Do not add a custom `PORT` variable. Review the failing revision's logs. | Healthy revision and `/health` HTTP 200; authenticated API calls work from the frontend. |
| Vercel | Import only the frontend production settings; deploy a new build after changing build-time values. Confirm the custom domain and backend origin. | `genhire.in` calls the supplied backend, with no CORS/OAuth errors. |
| BigQuery cost reporting | The table setting is present. Confirm the Standard usage-cost export is enabled and the runtime identity has dataset Data Viewer plus project Job User access. Set dataset location only if needed to match the dataset. | Admin cost reporting retrieves export data when available; configured infrastructure estimates are not invoices. |

Use the current [ZeptoMail domain-verification instructions](https://www.zoho.com/zeptomail/help/domains.html)
for your account's exact DNS records. Its documentation currently redirects to
Zoho CPaaS; do not replace existing DNS with a generic SPF string from an example.
Existing records/account configuration may already satisfy these checks; the audit
could not inspect provider dashboards.

## 11. Protect credentials in deployment build contexts

The backend Dockerfile uses `COPY . /app`. Its current `.dockerignore` excludes
private `.env` files, local service-account/credential JSON files, virtual
environments and `.private/` cleanup records. These protections are now in place;
keep them when building from a local workspace. Relevant exclusions include:

```dockerignore
**/*service-account*.json
**/*credentials*.json
.private/
```

Git ignores the real key file, so a repository checkout normally omits it; a local
Docker context follows `.dockerignore`, not `.gitignore`. Inject the signing JSON
through Secret Manager or mount the key at runtime instead of baking it into an
image. Also inspect the selected upload/build context for other private files.
Keep the required ONNX artifact in the context or retrieve it during the build;
Git/gcloud ignore rules can exclude that binary too. Do not remove all ignore
rules just to get the model into the build.

## 12. Order to follow and completion checklist

1. Create/connect Redis; separate local/production namespaces; run the Redis probe.
2. Provide the DeepSeek key or intentionally select a supported fallback-only chain.
3. Configure the payment webhook and secret; verify it in test mode.
4. Decide single/dual-camera support and optional identity coverage; make job settings
   match the deployed capabilities. Include the existing object model in the image.
5. Confirm email DNS/delivery, Google speech/OAuth, MongoDB and GCS access.
6. Validate the production configuration; inject backend values/secrets into Cloud
   Run and frontend build settings into Vercel. Deploy through the normal workflow.
7. Verify the new healthy revision, kiosk release and complete interview/payment
   flows. Resolve the actual HTTP 503 cause using revision logs.

- [ ] Production Redis TCP/TLS connection works and quota probe passes.
- [ ] Production remains `RATE_LIMIT_REQUIRE_REDIS=true`.
- [ ] Development/staging quotas are isolated from production.
- [ ] Primary provider and Groq speech credentials have usable access/quota.
- [ ] Signed payment webhook updates the wallet exactly once.
- [ ] Camera requirements match platform flags and deployed detector capabilities.
- [ ] Object model is in the deployed image, not only on the local machine.
- [ ] Private key files are excluded from build contexts and injected only at runtime.
- [ ] Verification/reset/invitation emails and Google login succeed.
- [ ] CV/JD storage and signed downloads work.
- [ ] Cloud Run is healthy and the Vercel build uses the intended backend.
- [ ] Compatible kiosk installer is published and a complete interview is tested.
- [ ] Optional monitoring/cost reporting is enabled if you want those services.

Configuration and deployment import details remain in
[environment-configuration.md](environment-configuration.md). Real secrets should
stay in the ignored files or provider secret stores; this document contains none.


## Audit verification

- Eleven configuration/probe tests passed with synthetic credentials and a fake
  Redis client. No provider credentials or customer quota keys were used.
- Eight-file schema checks passed. Local configuration has no blocking errors;
  production still reports missing `REDIS_URL` plus the feature notices above.
- The real local Redis probe correctly reports the empty URL; an external Redis
  success check remains for after you configure that service.
- Environment values and deployed services were not changed during this audit.
