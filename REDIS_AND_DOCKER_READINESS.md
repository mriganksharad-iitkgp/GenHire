# Redis and Linux container verification — 22 October 2026

The existing Upstash connection now serves shared application caches as well as request/socket quotas. The Linux backend image builds and boots successfully. Nothing was deployed or pushed.

## What uses Redis

| Data | Expiry | Behavior |
| --- | --- | --- |
| HTTP/socket rate-limit counters | Existing policy windows | Atomic shared counters; required in production; outages reject protected work rather than creating local counters |
| Company name/logo displayed on jobs, saved jobs and application views | 60 seconds | Bulk Redis reads and bulk Mongo lookup for misses; only these two presentation fields are cached |
| Company-profile cache revisions | 1 hour | Profile edits change the revision across instances; readers finishing an old lookup cannot repopulate the new version with stale data |
| Interview preparation keywords/skill metadata | 10 minutes | Replaces the old 50-item process dictionary; keys hash the complete CV/JD and mode/model identity, rather than truncating documents; source CV/JD, answers and generated questions are not cached |
| OpenAI organization cost reads | 10 minutes | Credential/date-scoped cache, including valid zero values; shared fill lease limits duplicate provider reads |
| GCP BigQuery billing ranges/month totals | 10 minutes | Export-table/location/window-scoped cache and shared fill lease |
| DeepSeek account balance reads | 60 seconds | Credential/account-scoped shared cache and fill lease |

Unavailable OpenAI/GCP cost reads are cached for 15 seconds. A concurrent billing reader can receive an unavailable value while another instance fills the cache; callers retain their existing explicitly labeled fallback. These are provider cost displays, not the customer wallet or billing ledger.

The new cache shares the existing Redis client's bounded 32-connection pool, TLS/timeout settings and no-automatic-retry policy. No additional Redis URL or mandatory env field was added. JSON entries are limited to 256 KiB and TTLs to one hour. Keys have a version prefix and hash the environment, database, account/content inputs; raw credentials and candidate text do not appear in key names. Cache logs contain exception types only.

When the cache cannot reach Redis it bypasses caching and reads the source. It creates no process-local data cache. This does **not** bypass the existing production request-protection gate: Redis outages still produce 503 on protected requests. Cache invalidation outages may leave company presentation fields stale until their 60-second TTL; eligibility and authorization are never decided from those fields.

## State intentionally kept elsewhere

- MongoDB remains authoritative for wallets, payments, permissions, applications, invitation eligibility, OA answers/submissions/grades, executor acceptance and durable worker tasks. Caching these without transactional invalidation would create correctness problems.
- Interview checkpoints remain in MongoDB. Live WebSocket connections, media streams, model/client objects, thread locks and per-process resource semaphores remain local runtime objects. Redis JSON cannot replace those objects. This change does not make the interview engine stateless or approve unrestricted horizontal scaling.
- The three-second health memo remains local so every container checks its own dependencies. A shared cached healthy result could hide a broken container.
- Process configuration/secrets and initialized SDK/model clients remain local; secrets are not written to Redis.

## Verified

- Actual saved Upstash URL: TLS connection, independent-client cache reads, positive TTL, invalidation and shared atomic quota counters passed. Temporary synthetic keys were deleted.
- Actual built Linux image to Upstash: TLS cache write/read/delete passed, without loading application data or calling providers.
- Backend regression suite: **493 tests, 490 passed and 3 opt-in skips**. Includes ten cache tests covering cross-client sharing, expiry, corruption/size limits, hashed scopes, outage bypass, concurrent fill leases, owner-safe lease release, profile invalidation, credential rotation and full-document key separation.
- Environment tooling: **24 tests passed**; production env audit has zero errors with runtime-secret injection allowed.
- `docker build --platform linux/amd64 --tag genhire-backend:redis-20261022 --file python-backend/Dockerfile python-backend` passed.
- Image: **linux/amd64**, local image ID `sha256:c20274fcd7d005bc659de58ff51bf8f57e30c8c1d9793800ca42ef04bd9ecad8`.
- Production Gunicorn startup, HTTP health, Linux `pip check`, cross-process Redis cache sharing, missing-authentication 401, and Redis-outage readiness 503 all passed inside Docker.
- Dotenv and developer harness files are excluded from the image. The local ONNX artifact is present and inference passes with the Linux OpenCV runtime; SHA-256: `be7980683b0c4d7c86529e37953b363cfef67f8ec44c32ccfcc62736c7de7404`.

The container smoke used an internal Docker network, disposable MongoDB/Redis, synthetic signing credentials, explicitly disabled email and background jobs, and no published ports. It used no production database or cloud/provider operations. Its temporary containers, anonymous volumes and network were removed. The separate Upstash checks used only synthetic expiring keys.

Logs: `.tmp/redis-docker-build.log`, `.tmp/redis-container-smoke.log`, `.tmp/redis-full-backend-tests.log`, `.tmp/redis-environment-tests.log`.

## Repeat the container check

With Docker on PATH:

```powershell
docker build --platform linux/amd64 -t genhire-backend:redis-check python-backend
python-backend/venv/Scripts/python.exe python-backend/scripts/dev/check_container.py --image genhire-backend:redis-check
```

On this machine Docker Desktop's CLI is not on the current shell PATH. Its installed location is:

```text
C:/Users/NikhilGupta/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe
```

Pass that path through the smoke script's `--docker` argument. The readiness GitHub workflow now builds the Linux image and runs this same isolated smoke after backend checks; the hosted workflow itself will run after you push.

## Production rollout

1. Deploy the new source/image and preserve the Cloud Run **`REDIS_URL`** Secret Manager reference to Upstash. The local saved URL was verified; the deployed secret reference was not inspected. Continue using `rediss://` and the production shared-store requirement. No credential edits are required by this change.
2. Keep the existing pool timeout settings unless measured deployment latency warrants a change. Watch Upstash command usage, storage and connection errors as traffic grows. Cache entries expire automatically; bulk company reads use MGET. Leave headroom for quota keys and do not flush the shared database or use cache eviction in a way that silently discards protection counters.
3. In Upstash's data browser, new application entries have prefix **`genhire:cache:v1:`** and include buckets such as `company-display`, `interview-preparation` and `gcp-billing`. Billing entries appear only when those configured admin views are requested. Cache keys are environment/database-scoped; verification keys are intentionally removed.
4. The local image contains the Git-ignored ONNX model. A GitHub-source Cloud Build still needs the existing model provisioning or mount step; a Git push alone does not include that binary. Preserve the Aiven CA mount and other runtime secrets.
5. After rollout, check the deployed `/health`, an authenticated jobs view, a company-profile edit reflected in another session, and the admin cost view. Then perform the existing staging OA/provider/device acceptance checks. Local Docker success does not establish cloud IAM, provider account permissions or candidate-device acceptance.

Follow-up: both heuristic and model-derived interview preparation now use Redis with separate keys. The newer `genhire-backend:oa-refinement-20261022` image also passed the isolated container smoke. Frontend and kiosk UI were subsequently refined and the installer rebuilt; see [OA UI refinement](OA_UI_REFINEMENT.md) and [the deployment handoff](DEPLOYMENT_BUILD_CHECK.md) for current artifacts.
