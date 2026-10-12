# GenHire technology and deployment context

Reviewed against the repository on 13 October 2026, with deployment identity/configuration last checked on 12 October; each bullet explains one responsibility.
Reported cloud access is distinguished from read-only inspection; production application health and runtime secret access still require verification.
This file contains architecture context and public identifiers only; credential values belong in private configuration or Secret Manager.

## 1. Product and application boundaries

- GenHire combines job publishing, CV screening, AI interviews, integrity reports, and credit billing for recruiting workflows.
- Candidates use the website to find jobs, maintain their profile, apply, practice, and review application progress.
- Recruiters use the website to manage openings, applicants, invitations, interview reports, and company information.
- Administrators use a separate protected portal to manage accounts, verification, credits, and cost reporting.
- The React website, Python backend, and Electron interview application are three separate applications in this repository.
- MongoDB persists business records; Cloud Storage persists document and recording artifacts; Redis persists shared request counters.
- The landing page establishes the purple accent, pale backgrounds, rounded surfaces, and typography used by portal components.
- [docs/README.md](docs/README.md) indexes detailed guides; [required setup](docs/required-setup-and-rate-limits.md) lists owner configuration steps.

## 2. Reported production infrastructure

- Vercel hosts the production frontend associated with the custom domain `https://genhire.in`.
- `https://gen-hire-gamma.vercel.app` is a reported Vercel alias; individual deployment preview URLs can change.
- Google Cloud project `hr-tech-2026` contains the reported backend deployment and related Google resources.
- Cloud Run service `hrtech` in `europe-west1` runs the containerized Python backend.
- `https://hrtech-628047232128.europe-west1.run.app` is the configured public backend origin.
- [python-backend/Dockerfile](python-backend/Dockerfile) builds on `python:3.11-slim` and installs the pinned Python dependencies.
- Gunicorn 23 uses one gthread worker with 32 native threads in the pending 12 October source fix, avoiding native vision/gRPC stalls in eventlet.
- Cloud Run supplies `PORT`; Docker uses `gunicorn.conf.py`, which binds that port and defaults to 5000 for local shell startup.
- The owner's deployment notes and earlier build screenshot describe a Google Cloud Build build, push, and Cloud Run deployment pipeline.
- The reported Cloud Build trigger is `genhire-main-deploy`; its complete trigger configuration is external to this repository.
- The 12 October deploy log identifies `genhire-backend@hr-tech-2026.iam.gserviceaccount.com` as the build's deploying identity.
- Cloud Build's deployer needs `roles/iam.serviceAccountUser` on the runtime account; the scoped grant resolved the 12 October attachment failure.
- [Deployment recovery](docs/backend-startup-and-login-recovery.md) contains the scoped IAM grant and retry steps; changing dotenv cannot repair this permission.
- The inspected image is stored in Artifact Registry `europe-west1-docker.pkg.dev/hr-tech-2026/cloud-run-source-deploy/hrtech/hrtech`.
- Google Cloud Logging holds worker-startup tracebacks and HTTP request logs needed to diagnose failed Cloud Run revisions.
- The repository's [keep-warm workflow](.github/workflows/keep-backend-warm.yml) pings `/health` every five minutes as a best-effort cold-start mitigation.
- Keep one Gunicorn worker and at most one Cloud Run instance until process-local interview and socket state is redesigned for shared execution.

## 3. Google identity, storage, and secret injection

- Bucket `gs://genhireuploads` is the configured application artifact bucket; `GCS_BUCKET_NAME` uses the name without `gs://`.
- `genhire-backend@hr-tech-2026.iam.gserviceaccount.com` is the runtime identity confirmed by read-only Cloud Run inspection on 12 October.
- Recovery revision `hrtech-00149-5dg` uses image `879f473…`, serves all traffic, and passes health/auth-preflight after removing the blank SDK credential override.
- Application Default Credentials, or ADC, lets Google SDKs authenticate using Cloud Run's attached identity without a bundled private key.
- The owner reports bucket-scoped `roles/storage.objectAdmin` for application object operations.
- The owner reports `roles/iam.serviceAccountTokenCreator` on the runtime account for IAM-backed signed URLs.
- IAM Credentials API supports signing file-access URLs when runtime credentials do not contain a local private signing key.
- The owner reports Cloud Run, Storage, IAM Credentials, Text-to-Speech, Speech, and Secret Manager APIs enabled.
- Upstash supplies the hosted Redis database accessed by the backend over TLS/TCP using a `rediss://` URL.
- Secret Manager secret `genhire-redis-url` stores the full Redis connection URL, including its authentication information.
- Cloud Run maps `genhire-redis-url` version `latest` to `REDIS_URL`, confirmed by read-only configuration inspection on 12 October.
- `REDIS_URL=""` in backend `.env.production` is intentional because the production credential is injected separately at runtime.
- Preserve that secret reference and remove any conflicting ordinary `REDIS_URL` assignment when importing production variables.
- Secret content must be the raw connection URL, without a `REDIS_URL=` prefix, dotenv quotes, or an added newline.
- The owner reports secret-scoped `roles/secretmanager.secretAccessor` for the intended runtime identity.
- Updating an environment-injected secret requires a new revision or instance using the selected version; verify the effective deployment after rotation.
- Production profiles retain blank Google credential placeholders; omit the SDK file override from Cloud Run because an empty value breaks ADC, and startup now normalizes blanks.
- Local `python-backend/gcs-service-account.json` is a private development credential file, excluded from Git and Docker; its contents do not belong here.

## 4. Repository and configuration conventions

- [python-backend/](python-backend/) contains the main Flask API, business services, interview engine, and payment module.
- [react-frontend/](react-frontend/) contains the website and the current React renderer built for the secure browser.
- [secure-browser-kiosk/](secure-browser-kiosk/) contains Electron process code, packaging configuration, security helpers, and legacy renderer files.
- [docs/](docs/) contains setup instructions, audits, architecture explanations, API references, and operational checklists.
- Root [scripts/check_environment.py](scripts/check_environment.py) validates dotenv syntax, key order, public/private boundaries, and required settings without printing values.
- Each application has `.env`, `.env.production`, `.env.example`, and `.env.production.example` with matching keys and order within that application.
- The current backend files each contain 180 assignments; the current frontend files each contain eight assignments.
- [config/env_loader.py](python-backend/config/env_loader.py) loads dotenv values with `override=False`, preserving platform-injected environment variables.
- `ENV_FILE` or `DOTENV_PATH` explicitly selects a backend dotenv file; production otherwise loads `.env.production` before `.env`.
- Frontend `REACT_APP_*` values are public build inputs embedded in JavaScript, so backend credentials must never be placed there.
- `REACT_APP_API_URL` is the backend origin; `REACT_APP_API_BASE` is that same origin followed by `/api`.
- Backend `FRONTEND_URL`, frontend `REACT_APP_FRONTEND_URL`, and backend allowed CORS origins must agree for the selected environment.
- `--allow-runtime-secrets` permits a blank production Redis URL during file validation and explicitly reports the required Secret Manager injection.
- [environment-configuration.md](docs/environment-configuration.md) explains Cloud Run/Vercel imports; [startup recovery](docs/backend-startup-and-login-recovery.md) explains the earlier GCS boot failure.

## 5. Frontend frameworks and build tools

- React 19 renders the website and current secure-browser interview UI using functional components and hooks.
- React DOM mounts the application through `createRoot`.
- React Router DOM 7 handles routes, navigation, query parameters, and redirects inside a router context.
- Vite 5 supplies the development server and optimized production builds, replacing the previous Create React App build workflow.
- `@vitejs/plugin-react` supplies React compilation and development refresh integration.
- esbuild transforms JavaScript/JSX and handles the repository's JavaScript files containing JSX.
- [vite.config.mjs](react-frontend/vite.config.mjs) preserves `REACT_APP_*` compatibility and outputs the website into `build/`.
- Vite development and preview servers use port 3000 in the repository configuration.
- [vite.kiosk.config.mjs](react-frontend/vite.kiosk.config.mjs) builds the shared interview renderer into `secure-browser-kiosk/web-app/`.
- ESLint and the React App ESLint configuration check frontend code; PostCSS is included in the frontend toolchain.
- `@react-oauth/google` supplies the Google sign-in integration using the public OAuth client ID.
- `socket.io-client` connects browser sessions to Flask-SocketIO for realtime updates and monitoring.
- Chart.js with `react-chartjs-2` renders administrator cost charts; `react-qr-code` renders phone-pairing QR codes.
- Lucide React supplies consistent modern icons; retained dependencies such as Axios and FFmpeg do not imply they are the current shared HTTP or interview implementation.

## 6. Shared design and frontend infrastructure

- [portal-theme.css](react-frontend/src/shared/styles/portal-theme.css) centralizes portal colors, surfaces, borders, and shared visual conventions.
- CSS Modules scope component and page styles to avoid accidental collisions between feature areas.
- `PortalPageHeader` provides a consistent page title, introductory copy, and action area.
- `Navbar` and `Layout` provide the common authenticated shell and role-aware navigation.
- Shared `Modal` provides a reusable dialog surface; interview launch/report dialogs use body portals where necessary to escape stacking contexts.
- `Toast` communicates transient outcomes; `EmptyState` explains empty data views and appropriate next actions.
- `Loading` and `SkeletonCard` expose loading states instead of leaving pages blank.
- `ConfirmDialog` and account-deletion dialogs request confirmation for consequential actions.
- `ErrorBoundary` catches rendering errors; `NotFound` handles unmatched routes.
- `AuthShell`, `AuthBrand`, and `AuthStory` give login and signup pages a shared presentation aligned with the landing theme.

## 7. Frontend routing, authentication, and networking

- [app/routes.jsx](react-frontend/src/app/routes.jsx) declares public, candidate, recruiter, interview, payment, and administrator routes.
- `ProtectedRoute` checks session/role access before rendering a protected page; backend authorization remains authoritative.
- `AppProviders` supplies Google OAuth context, shared candidate data, and the rendering error boundary.
- `SessionExpiredHandler` responds to the global session-expired event and navigates to login from inside the router.
- [shared/api/client.js](react-frontend/src/shared/api/client.js) uses Fetch as the common authenticated JSON/FormData request layer.
- The shared HTTP client adds bearer authorization, handles empty responses, and standardizes session-expiry and network errors.
- `shared/api/retry.js` interprets retry timing so rate-limit responses can produce useful wait messages.
- `shared/utils/session.js` centralizes token/user storage and supports the configured browser session keys.
- `shared/components/layout/navigation.js` defines candidate and recruiter tabs and their active-state rules.
- Candidate navbar tabs separate Open Positions, My Applications, My Profile, Practice, Cost Statistics, and Team.
- Legacy `/profile#applications` or profile tab links redirect to `/applications` before mounting profile/CV features.
- Recruiter Overview, Jobs, Candidates, and Company Profile use dashboard query tabs; cost and team pages use separate routes.
- Invite-only candidates receive a restricted navigation set appropriate to their scoped accounts.
- Login, signup, recruiter onboarding, email verification, password recovery, and invite redemption each have dedicated pages.

## 8. Candidate portal responsibilities

- `Dashboard` provides job search, filters, saved openings, and application entry points.
- `useJobs` manages job-list requests; `useSavedJobs` manages bookmarking and saved-job state.
- `JobDetails` presents role description, requirements, benefits, company details, and application actions.
- `Applications` presents application history without combining it with profile editing or CV management.
- `ApplicationView` presents an individual application and its associated progress/details.
- `ApplicationsList` and application-history components render status, scores, filters, and interview/report actions.
- `Profile` owns personal information, CV management, profile-related statistics, and identity-card setup.
- `BioForm` edits candidate details; `SidebarProfile` presents profile information where that layout is used.
- `CVManagement`, `CVList`, and `CVSelector` organize multiple CVs and select the appropriate CV for an operation.
- `CVViewer`, `CVDetailsModal`, and `CVDetailsForm` expose document previews and structured CV information.
- `IdentityCardUpload` supplies the candidate's one-time identity-reference upload workflow.
- `CandidateDataContext` shares candidate data; profile/application hooks separate loading and mutations by responsibility.
- `useRealtimeApplications` responds to application updates instead of requiring every status change to be manually refreshed.
- `Practice` offers role-based preparation; candidate cost statistics and subscription pages explain usage and credit options.

## 9. Recruiter and administrator portals

- `RecruiterDashboard` composes overview metrics, openings, candidate review, and company-profile panels.
- `OverviewMetrics` summarizes recruiting activity; `RecentActivity` presents recent actions and outcomes.
- `JobsGrid` presents openings with applicant counts, status, and management actions.
- `JobCreateModal` supports templates, AI-assisted drafting, job metadata, skills, and interview-monitoring options.
- `JobEditModal` updates existing job settings while retaining the same form/theme conventions.
- `JobDetailsModal` exposes a recruiter-facing view of a posting's full details.
- Invitation UI and `inviteApi` handle recruiter-created invitation batches and delivery results.
- `jobExportApi` downloads screening-cleared candidate exports for subsequent hiring rounds.
- Recruiter cost/subscription components present credit usage, plans, and upgrade actions.
- `AdminLayout` keeps a persistent administrator shell while route outlets switch content.
- Administrator account pages manage candidates, recruiters, and administrators with reusable tables and detail dialogs.
- Administrator Verification and `IdentityCardPanel` support account/identity review and permitted identity-reference management.
- Administrator Credit Statistics and Cost Statistics separate wallet activity from estimated or fetched provider spending.
- Team pages describe platform contributors; their presence does not itself implement an enterprise collaboration system.

## 10. Backend framework and composition

- Flask 3.1 provides the main HTTP application; Werkzeug supplies request/response handling, password utilities, and HTTP errors.
- [app.py](python-backend/app.py) is the local entry point and exports the WSGI application used by Gunicorn.
- [core/factory.py](python-backend/core/factory.py) composes extensions, security, database access, routes, and background services.
- `core/bootstrap.py` performs early runtime initialization before modules with import-time setup.
- `core/config.py` centralizes configuration access; `core/runtime.py` handles runtime concerns used by startup.
- `core/extensions.py` owns the shared Socket.IO instance and avoids circular imports through the app entry point.
- Flask-SocketIO 5.5 connects backend socket handlers to realtime clients.
- Flask-SocketIO explicitly selects threading with simple-websocket; the inspected deployed image still used eventlet before the pending source deployment.
- Flask-CORS handles allowed cross-origin browser API calls; CORS does not make an unavailable worker healthy.
- Flask-Talisman applies security headers and configured HTTPS enforcement, with a deliberate HTTP exception for `/health` probes.
- `ObjectIdSafeJSONProvider` serializes MongoDB ObjectIds into JSON-compatible responses.
- The application-wide request-body limit is 16 MB; particular upload and speech routes can impose smaller limits.
- `middleware/auth_middleware.py` validates authentication and enforces permitted account roles.
- `middleware/input_validator.py` and utility validators normalize and reject invalid request input.
- `middleware/rate_limiter.py` installs route budgets, admission protection, shared counters, and socket-event limits; configured Redis failures fail closed.
- Auth, profiles, jobs, applications, CVs, files, invitations, identity, practice, interviews, speech, admin, and cost features have separate route modules.
- `routes/system_routes.py` provides the root response, dependency-aware health checks, and authenticated GridFS serving.
- Health checks report MongoDB/Redis readiness with a short three-second process-local cache, not complete provider/OAuth/bucket verification.
- Sentry's Flask integration is optional error monitoring enabled by a configured `SENTRY_DSN`.

## 11. Persistent data and concurrency

- PyMongo 4.13 is the main MongoDB driver; `MONGODB_URI` identifies the deployed database service.
- dnspython supports DNS resolution used by MongoDB SRV connection URLs.
- [config/database.py](python-backend/config/database.py) configures connection pooling, wait timeouts, server selection, and required indexes.
- User records hold account roles, profile data, verification state, and references to identity/face files.
- Job records hold role metadata, screening thresholds, posting status, and monitoring requirements.
- Application records persist candidate/job association, CV screening results, interview state, and recruiting outcomes.
- Partial unique email indexes distinguish normal accounts from invitation-only accounts that may share an email.
- Application identity indexes reduce duplicate applications; migrations reconcile older data/index conventions.
- GridFS stores identity-card images and captured reference faces inside MongoDB.
- CV background processing uses Mongo-persisted work state, atomic leases, and a bounded worker pool.
- `bounded_executor.py` constrains notification/background submission instead of spawning unlimited work.
- Python locks and context propagation coordinate per-process interview/evaluation activity; they do not provide cross-instance synchronization.
- MongoDB durability and Redis counters do not automatically externalize the active interview engine or Socket.IO rooms.

## 12. File storage, validation, and exports

- [gcs_service.py](python-backend/services/gcs_service.py) provides Google Cloud Storage uploads, downloads, URI parsing, deletion, and signed links.
- The main application requires configured GCS credentials/bucket at startup; it has no general local-upload storage fallback.
- Stored CVs, job documents, profile photos, recordings, and gaze artifacts can use `gs://` references rather than public permanent URLs.
- Time-limited signed URLs provide temporary access to protected documents and recordings.
- GCS client initialization confirms usable credential resolution; an actual object operation is still needed to test bucket permissions.
- IAM-backed signing uses the attached Google identity; local development can sign with its private development credential file.
- `file_controller.py` checks uploaded file signatures through `filetype` rather than trusting the browser's extension/MIME declaration alone.
- PyPDF2 extracts CV PDF content in `pdf_parser_service.py`; pypdf is also used by the interview document processor.
- Temporary local files can support parsing or transfer work, while persistent application artifacts remain in their configured storage service.
- Existing GridFS file/photo compatibility paths support older records; identity images remain an intentional GridFS use case.
- Identity-card uploads accept JPEG, PNG, or WebP and enforce a five-megabyte limit in the identity service.
- `screening_export_service.py` uses openpyxl to produce XLSX candidate exports; CSV exports support simpler downstream tools.

## 13. Redis, quotas, and actual caches

- redis-py 8 connects to Upstash through TCP/TLS; an Upstash HTTPS REST URL cannot replace the required Redis connection URL.
- Redis currently stores shared rate-limit counters, not a general application response cache.
- Atomic Lua scripts combine counter increment, first expiry, and TTL inspection for consistent quota windows.
- Policy-specific identities and configured windows scope budgets by verified account, authentication target, or network as appropriate.
- `RATE_LIMIT_NAMESPACE` separates local and production counter keys so development checks do not consume production budgets.
- `RATE_LIMIT_REQUIRE_REDIS=true` requires a working Redis PING during production startup.
- A working quota exceeded returns HTTP 429 with `Retry-After`; `capacity_busy` denotes a distinct workload-admission rejection.
- Local development can use bounded memory counters when Redis is blank and shared-store enforcement is disabled.
- `REDIS_CONNECT_TIMEOUT_MS=5000` and `REDIS_SOCKET_TIMEOUT_MS=2000` are the current connection/read defaults, with automatic Redis retries disabled.
- Health and HTTP OPTIONS requests are exempt from quota consumption so readiness and preflight requests remain usable.
- `scripts/check_rate_limit_setup.py` verifies Redis connectivity and optional enforcement without displaying its credential.
- Redis is not currently a Celery broker, Socket.IO message queue, session store, or shared LLM-response cache.
- Backend health results, JWT-secret resolution, DeepSeek balance results, and GCP billing queries have separate process-local caches.
- The React interview UI caches question speech audio in memory to reduce repeated synthesis for the same question.
- DeepSeek prompt-cache usage reported by the provider is upstream token caching and is independent of GenHire's Redis counters.

## 14. Authentication, invitations, and email

- PyJWT signs and validates bearer access tokens using the backend JWT signing secret.
- Google authentication validates OAuth identity against the configured backend web-client ID and resolves the matching application account.
- Frontend and backend Google OAuth client IDs must match; Google Cloud's authorized origins require their own dashboard setup.
- Password-based authentication uses Werkzeug hashing utilities rather than storing plaintext passwords.
- Email verification and password-reset workflows use dedicated endpoints, tokens, and transactional emails.
- `REQUIRE_EMAIL_VERIFICATION` controls the verification requirement; a populated email-provider key alone does not confirm delivery permissions.
- `invite_service.py` creates scoped invitation accounts/tokens and manages invitation batches.
- openpyxl reads spreadsheet invitation inputs; invitation parsing also supports simpler candidate lists.
- `invite_email_templates.py` provides invitation messages and links to the redemption page.
- `invite_cleanup_scheduler.py` handles expiry-related cleanup for invitation accounts/workflows.
- `EmailService` selects the configured provider; the current private configuration selects ZeptoMail.
- ZeptoMail sends transactional email using its API key and configured sender; verified sender/domain setup is external to this repository.
- A noop email adapter supports explicitly configured non-delivery scenarios; a retained Mailgun adapter is legacy support rather than the active deployment choice.
- Status-notification emails communicate automatic screening and recruiter changes through bounded background submission.

## 15. LLM providers and orchestration

- [llm_fallback_service.py](python-backend/services/llm_fallback_service.py) centralizes provider ordering, model selection, response normalization, cooldowns, and usage recording.
- The current configured priority is DeepSeek, then Gemini, then Groq through `LLM_PROVIDER_PRIORITY=deepseek,gemini,groq`.
- `DEEPSEEK_API_KEY`, `GOOGLE_API_KEY`, and `GROQ_API_KEY` authenticate those three providers in backend-only configuration.
- `LLM_DEEPSEEK_MODEL=deepseek-flash` is the current configured primary model name, not a guarantee of provider account availability.
- `LLM_GEMINI_MODEL=gemini-3.1-flash-lite` configures the Google fallback model.
- `LLM_GROQ_MODEL=openai/gpt-oss-20b` configures Groq's text model; its model name does not mean an OpenAI API key is used.
- The OpenAI Python SDK and LangChain OpenAI adapter remain dependencies for DeepSeek's OpenAI-compatible API interface.
- LangChain Core supplies chat abstractions; LangChain Groq and Google GenAI adapters connect the other providers.
- Google GenAI and Groq SDKs supply provider integrations for supported chat, vision, and speech operations.
- Failed or unavailable providers can fall through the configured chain; model overrides allow task-specific choices.
- JSON-mode handling normalizes structured outputs and tolerates common Markdown/code-fence wrapping.
- Vision tasks require image-capable models; Groq vision fallback is opt-in through `FACE_MATCH_GROQ_MODEL`.
- Legacy OpenAI provider code still exists, but OpenAI credentials were removed from the active dotenv schema and priority.

## 16. CV, job description, and document processing

- `cv_structured_parser_service.py` extracts normalized CV fields through the shared LLM chain.
- `cv_scoring_service.py` evaluates CV/job compatibility and returns the screening score used by application workflows.
- The job's configured minimum CV score drives automatic shortlist/rejection decisions after scoring completes.
- Recruiter templates and AI-generated descriptions provide initial job data from instructions or uploaded documents for review before saving.
- `utils/job_standards.py` normalizes job metadata; frontend job taxonomy constants keep filters and forms consistent.
- `utils/company_resolver.py` resolves company information across linked recruiter/job records.
- `interview/document/processor.py` uses pypdf and NLTK for document text and keyword processing.
- NLTK supplies sentence/word tokenization, stopword handling, and part-of-speech tools where the processor uses them.
- `interview/document/loader.py` loads CV/JD/reference inputs and optionally uses LlamaIndex's `SimpleDirectoryReader` for reference documents.
- LlamaIndex-related packages in requirements support document integrations; their presence does not establish a deployed vector database or universal RAG pipeline.
- Structured CV data and selected CV references connect application screening to subsequent interview preparation.

## 17. Interview engine and participant experience

- [interview/core/session_manager.py](python-backend/interview/core/session_manager.py) owns active interview state, questions, responses, evaluation, and final results.
- `InterviewConfig` and `LLMConfig` organize interview settings and provider configuration.
- `direct_question_generator.py` generates first and later questions from CV, JD and previous Q/A only; no question banks, retrieval or embeddings run on this path.
- Prompt modules separate greeting, structure explanation, technical, experiential, HR, skill-assessment, and closing instructions.
- `services/interview_flow_service.py` connects persisted session records with runtime interview actions and normalized result payloads.
- Cached answer results and request identity support retry/idempotency handling so a repeated submission need not duplicate evaluation work.
- `evaluation_model/rubrics_eval/evaluation_system.py` coordinates rubric-based answer evaluation and communication scoring.
- Rubric generation, answer generation/evaluation, and communication evaluation are separate modules in that evaluation package.
- `answer_classifier.py` distinguishes answer types and uses langdetect when language detection is available.
- pandas supports evaluation data processing; matplotlib supports evaluation visualizations where those utilities are invoked.
- MongoDB source snapshots and engine checkpoints restore owned interviews with their question, answers and deadline without another debit.
- `interview_integrity_service.py` persists interruption episodes/counts by type and runs a five-second coverage watchdog without automatic termination.
- Phone monitoring requires a front camera, microphone, visible page and fresh frames; wake lock helps but a website cannot block OS app switching.
- [Chat.jsx](react-frontend/src/features/interview/pages/Chat.jsx) is the current shared interview UI for the website and packaged kiosk renderer.
- Pre-interview phases guide device access, microphone/speaker checks, face capture, and optional paired-phone readiness before answering.
- MediaPipe Tasks Vision and bundled BlazeFace/WASM assets guide local automatic capture with a 1.2-second stable hold, review and retake.
- Voice-only answers use reconnecting, buffered PCM captions through the configured provider; whole-recording transcription supplies the final answer.
- Recording/transcription and submission failures preserve retryable answers instead of discarding the participant's work immediately.
- Tab, network and phone gaps show 1.8-second notices; actual laptop device loss offers recording recovery, and final reports include weighted interruption counts.
- `KioskLaunchGuide` remembers installation confirmation in browser storage and offers reinstall help; browsers cannot reliably prove native installation.
- The interview layout places live question/answer history on the left, camera and voice sphere on the right, with responsive stacking and GPU/audio cleanup.

## 18. Speech and recording

- [google_speech_service.py](python-backend/services/google_speech_service.py) exposes the configured speech transcription and synthesis integrations.
- The current `STT_PROVIDER=groq` uses Groq Whisper transcription instead of the former Google streaming-token workflow.
- `GROQ_STT_MODEL=whisper-large-v3-turbo` selects the configured transcription model for recorded answers.
- Google Cloud Text-to-Speech supplies question audio and SSML word timestamps; captions follow actual playback with explicit audio retry/fallback.
- The current speech implementation restricts TTS to Standard voices and defaults to `en-US-Standard-C`.
- Google Cloud Speech remains an SDK/alternate transcription path; retired streaming endpoints should not be treated as the current interview route.
- Browser `getUserMedia` requests camera/microphone access; permissions and a secure browser context are required on participant devices.
- MediaRecorder records answer audio and session video using supported browser formats.
- Web Audio analysers drive Three.js 0.180.0 dotted `VoiceSphere` states from real microphone/AI playback amplitude; an AudioWorklet produces 16 kHz mono caption packets.
- `/api/speech/transcribe` handles final answers; `/api/speech/synthesize` returns timed audio; end endpoints return HTTP 202 while owned report work completes.
- Electron's restricted speech IPC forwards requests to authenticated backend endpoints without embedding Google or Groq secrets in the installer.
- `speech_cost_tracker.py` and provider telemetry estimate speech usage separately from chat token usage.

## 19. Proctoring, identity, and phone pairing

- [security_check.py](python-backend/security_check.py) decodes camera frames and runs available face, object, pose, and identity checks.
- NumPy represents image arrays; OpenCV headless provides image decoding, face detection, and ONNX inference utilities.
- `models/proctoring/yolov8n.onnx` supplies optional object-detection weights; its checksum manifest supports artifact validation.
- The ONNX binary is gitignored, so deployment builds must deliberately provision it rather than assume Git supplies the weights.
- `scripts/provision_proctoring_model.py` provides model-artifact provisioning support.
- MediaPipe head-pose and DeepFace identity-continuity checks are optional heavy capabilities requiring additional runtime dependencies/weights.
- Default production requirements do not install the complete TensorFlow/DeepFace/MediaPipe/PyTorch stack; enabling a flag alone cannot supply it.
- `face_verification_service.py` checks captured-face quality and compares against stored canonical faces according to the configured verification mode.
- `face_match_service.py` separately compares a live face with an uploaded identity-card image using image-capable LLM providers.
- Identity-reference comparison and repeated account-face verification are different checks with distinct availability and failure behavior.
- `identity_card_service.py` stores reference images in GridFS; candidate replacement is locked after upload while administrators have management actions.
- `proctoring_service.py` scores confirmed observations and persisted interruption types; face deduplication/four-frame confirmation reduce false multiple-face warnings.
- Mobile pairing tokens are HMAC-signed and scoped to session/account; readiness checks confirm the required second-camera connection.
- `MobileRecorder` runs on the paired phone; mobile/proctoring socket handlers authenticate sessions and validate access to their events.
- `MOBILE_RECORDING_ENABLED=true` now enables signed phone pairing locally; Cloud Run must also enable it for dual-camera jobs.
- `gaze_recorder_service.py` analyzes supplied gaze points and persists related artifacts; collection support must be checked in the actual active renderer.
- Integrity signals and answer-pattern review support human review and should not be interpreted as conclusive proof of cheating or AI use.

## 20. Electron secure browser

- [secure-browser-kiosk/package.json](secure-browser-kiosk/package.json) declares version 1.2.6, Electron 40, and electron-builder packaging with explicit media consent.
- `main.js` owns windows, single-instance handling, protocol registration, speech IPC, and kiosk lifecycle controls.
- The `secure-interview://` custom protocol carries validated interview launch context from the website into the installed app.
- `runtime-security.js` validates launch/external URLs and renderer paths; installer code signing is not enforced by the current build configuration.
- A loopback HTTP server uses an automatically selected port to serve the packaged `web-app/` renderer.
- `react-frontend/src/kiosk.jsx` mounts the shared React Chat page, initializes launch context, and handles return to the website.
- A renderer-ready handshake prevents launch data from being lost before the React application subscribes.
- A single-instance lock focuses the existing app and prevents replacing active interview credentials with another launch.
- The BrowserWindow disables Node integration and enables context isolation, web security, and the sandbox.
- `preload.js` exposes a restricted `electronAPI` through Electron's contextBridge rather than exposing unrestricted Node APIs.
- Kiosk mode applies fullscreen/window controls and shortcut restrictions; app-switch and display checks provide additional monitoring signals.
- Windows packaging uses NSIS with selectable installation directory and desktop/Start Menu shortcuts.
- macOS packaging declares universal DMG/ZIP targets; producing and testing a supported Mac release requires appropriate build infrastructure.
- Build scripts rebuild the React kiosk renderer before Electron packaging; distributing frontend changes requires publishing a rebuilt installer.
- Installers are configured to download from the public `genhire-downloads` bucket URL; that distribution bucket is separate from private `genhireuploads` artifacts.

## 21. Payments, plans, and credit accounting

- [payment_module/](python-backend/payment_module/) isolates plan, subscription, payment, wallet, and transaction models/services/controllers.
- Razorpay's Python SDK creates gateway orders and verifies checkout/payment signatures.
- Frontend `useRazorpay` starts checkout using server-issued payment data and handles success/failure responses.
- Razorpay webhook processing verifies its configured signing secret; the webhook secret is distinct from the API key secret.
- `wallet_service.py` maintains credit balances and ledger transactions with idempotency keys.
- Signup bonuses are granted during registration; the pending startup fix moves duplicate historical account scans to `scripts/migrations/backfill_signup_bonuses.py`.
- `credit_service.py` connects business operations to credit charging/refunding conventions.
- `interview_credit_service.py` manages interview debit/refund lifecycle and abandon handling with refund keys that prevent double refunds.
- `interview_quota_service.py` tracks plan/free interview usage; practice quotas have a separate candidate service.
- Plans and subscriptions determine allowances; configured credit rules are application policy rather than provider billing prices.
- AI drafting, invitations, practice, and real-interview monitoring can have separate configured credit costs.
- Payment Success/Cancel pages communicate checkout outcomes; Payment History displays prior transactions.
- Test/live Razorpay keys and verified webhook setup must match the intended environment before real purchases are offered.

## 22. Usage, costs, and observability

- `usage_telemetry_service.py` records normalized feature usage without including full prompt content in its usage records.
- `provider_usage_service.py` records provider/model requests and token/audio usage for administrative reporting.
- `ai_pricing_service.py` and interview pricing/cost trackers turn configured unit prices and usage into estimates, not guaranteed invoices.
- `deepseek_billing_service.py` retrieves balance information and briefly caches results in process memory.
- `gcp_billing_service.py` queries a configured Google billing export through BigQuery and caches results in process memory.
- BigQuery reporting requires an enabled billing export, the correct table/location, and runtime query/read permissions.
- Infrastructure monthly-cost environment fields are manual reporting estimates, not evidence those services are deployed.
- LangSmith/LangChain tracing is optional and controlled by configuration; enabling it can export model interactions to the configured tracing service.
- Sentry reports exceptions when configured; normal application logging and Cloud Run logs remain separate observability paths.

## 23. Verification, operations, and legacy boundaries

- Python unittest/pytest suites cover authentication, request protection, jobs/applications, credits, invitations, interview behavior, and startup boundaries.
- requirements-dev adds pytest tooling and Locust; requirements-test supplies lighter isolated dependencies such as mongomock and fakeredis.
- mongomock simulates MongoDB in tests; fakeredis with Lua support exercises Redis behavior without a live quota service.
- Node's built-in test runner checks frontend retry/session/navigation helpers and Electron runtime-security helpers.
- jsdom-based `portal-smoke.mjs` and `interview-usability-smoke.mjs` check targeted frontend rendering/usability scenarios.
- Frontend `npm run build`, kiosk renderer builds, and appropriate tests verify code/build behavior; they do not confirm a participant's physical devices.
- `scripts/route_manifest.py` inventories backend routes; smoke scripts exercise configured email/billing services when intentionally run.
- Migration scripts reconcile legacy account, wallet, job-counter, screening-status, invitation, and background-processing data.
- Administrative utility scripts can create or modify privileged accounts and data; review their arguments and target database before running them.
- A healthy `/health` endpoint plus successful allowed-origin auth preflight distinguishes worker recovery from the earlier secondary CORS symptom.
- Test GCS upload/download/signed links, login, email, payments, and kiosk launch separately after deploying a new revision.
- Standalone `cv_jd_processing/` contains a FastAPI service and separate dependencies; `.dockerignore` excludes it from the main Flask image.
- Standalone `gpu_intensive_task/` contains alternative/heavier processing code and is also excluded from the main backend image.
- Legacy Electron `index.html`/`renderer.js` reference WebGazer, VAD, ONNX Runtime Web, and related browser libraries; the packaged current entry uses the React renderer.
- Legacy gaze demo/report helpers and deprecated speech routes are not proof that the active React interview collects every historic signal.
- No shared Redis application cache, distributed interview state, or queued multi-instance worker architecture is currently established by this implementation.
- Treat deployed IAM/secret settings as owner-reported until checked remotely; no deployment, secret rotation, or IAM change is performed by writing this context file.
