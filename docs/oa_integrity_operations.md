# OA integrity operations — Step 7

This is an implementation/runbook, not a production security certification or deployment. Real `.env` is unchanged. Keep launch/capture approvals off until the actual deployed web/native builds, devices, storage, retention and detector behavior pass acceptance. No live OA, camera capture, paid external execution, installer publication or cloud resource change occurred during implementation.

## Rollout and runtime boundaries

New OA starts now require all existing runtime/evaluation/security approvals **and** `GENHIRE_OA_INTEGRITY_ENABLED=true`. Integrity defaults off. Existing pre-integrity attempts keep their original read/recovery behavior; new integrity-enabled attempts require scoped preflight for question reads and answer/Run/Submit operations. Normal account credentials alone cannot operate those attempts. Disabling new starts does not reset accepted timers or release reservations.

Native source/package version is **1.3.0**. Configure `GENHIRE_OA_KIOSK_RELEASE_ID` to the actual reviewed released version. The native build keeps sandbox/context isolation, local bundled assets, navigation restrictions, shortcut handling and emergency exit. Monaco's generated dotted worker filename is now served through the same bounded asset allowlist. OA microphone permission is denied; the camera dialog accurately describes sampled images. Screening retains its original camera/microphone flow.

**Runtime metadata is client-reported, not device attestation.** A matching version/kiosk flag does not prove an untampered binary, trusted OS or absence of external devices. No cheat-proof, screen-capture-prevention or OS escape-prevention claim is made. Actual Windows/macOS packaging/signing and OS behavior were not tested or published here. Emergency exit explicitly says the OA timer continues; it does not auto-submit, reject or refund.

The launch flow uses an authenticated candidate's five-minute opaque capability. Only its hash is persisted; no account JWT enters the OA deep link. Redemption binds a nonce and issues an `aud=genhire-oa` session capability. `Authorization: OA <token>` works only on an explicit OA route allowlist and only for that invitation/attempt. Account APIs reject that audience/prefix. Session tokens stay in a separate tab/native-session storage key and never overwrite the dashboard login. Renewed tokens remain bounded to the accepted deadline plus 15 minutes. A new redeemed device session revokes the previous one; answer revisions and server deadlines remain authoritative.

The browser must show monitoring/retention consent and complete device preflight before starting. Preflight does not reserve credits/start the timer. Required camera/companion readiness uses a recent server-received frame, not just a browser readiness checkbox. A fresh launch/redeem/preflight is needed after policy/accommodation changes. Failed/replayed/malformed launch messages do not log decoded credentials.

## Monitoring policy and honest evidence

| Tier | Delivered behavior |
|---|---|
| Basic | Visible/focus/fullscreen/network-gap/blocked-external-paste observations and server-received heartbeats, batched with idempotency and rate/volume limits. These are client signals, not proof of native lockdown. |
| Camera | Basic plus bounded sampled JPEG images from the desktop camera and existing lazy server-side face/object/pose analysis where available. Missing models/errors remain unknown coverage. No face-identity-continuity score is claimed. |
| Dual | Camera plus a phone companion opened through an opaque camera-only capability in the URL fragment/QR code. Phone access cannot read questions/answers, change accounts or submit attempts. The required recent phone sample is checked before accepted start. |

These tiers collect **sampled camera images**, not continuous video, microphone audio, desktop screenshots or clipboard contents. Sampling is every 15 seconds in the supplied client, server admission at most once per 10 seconds/source, maximum 250 KB/JPEG, 4000 samples/session and a bounded distributed analysis lease. CPU/model behavior and lease sizing still need real deployed measurement; this is not a measured production capacity guarantee. Clients stop capture on completion/exit; server rejects late/terminal/withdrawn participation capture independently.

Existing screening's process-local proctoring sessions are not reused as OA state. OA session/event/upload/evidence records are durable Mongo data. Frames are analyzed server-side and uploaded only to private GCS under `oa-evidence/<session>/<opaque-id>.jpg`; source code, hidden tests, screen content and clipboard text are never part of the image/event API. Upload intent precedes cloud writes, so ambiguous uploads still have a cleanup path. No local filesystem media fallback exists.

Server summaries distinguish client observations, sampled frames, analyzed samples and review signals. Missing/sparse coverage is unknown; no numerical OA proctoring score or cheating verdict is invented. Native restrictions, event counts, face/object detections and code overlap never change objective marks, terminate an attempt, automatically reject a candidate or advance company rounds. Reviewers can record `reviewed_clear`, `needs_followup` or `insufficient_evidence` with a reason and revision. Company decisions/result release remain Step 8.

## Accommodations and verified extra time

The verified owner recruiter/authorized admin can approve browser mode, camera waiver and 0–180 extra minutes before start, using a current revision and documented functional reason. Medical details are not required. Browser accommodation permits assistive clipboard use; normal kiosk mode permits editor-internal copy/paste and blocks external paste in the supplied editor. Keyboard navigation/find/editing remain available; no in-assessment AI coding assistant is added.

Initial extra time is added once to the accepted full duration; section allocations distribute it proportionally while preserving the total. An active attempt can receive a separate reasoned extension for a verified disruption. Initial plus later approved extra time is capped at 180 minutes. The extension changes the current/future section windows, own deadline, access and companion expiry; it does not reopen completed sections, reset start time or revive an expired/submitted attempt. It records an audit/stage event and deduplicated deadline-change notice. Email delivery still uses the default-off hiring email flag.

The candidate can request evidence deletion review from the submitted workspace. Recruiter controls expose accommodations, summaries/reviews, verified extra time, paged evidence samples, signed sample links, preservation and deletion scheduling. Functional reasons are required. Reviewer-only evidence/overlap reads are access-audited; candidates/phones cannot request raw media links or private reviewer notes.

## Retention and storage acceptance

| Setting | Default / range |
|---|---|
| `GENHIRE_OA_RAW_RETENTION_DAYS` | 30 / 1–90 |
| `GENHIRE_OA_SUMMARY_RETENTION_DAYS` | 180 / 30–730 |
| `GENHIRE_OA_MEDIA_ENABLED` | false |
| `GENHIRE_OA_MEDIA_ACCEPTED` | false |
| `GENHIRE_OA_VARIANTS_ENABLED` | false |
| `GENHIRE_OA_SIMILARITY_ENABLED` | false |
| `GENHIRE_CAMERA_PROCTORING_CREDITS` | 10, server configurable |

Policy/consent and retention are frozen for each accepted attempt. Effective submission/deadline/cancellation time starts retention, including delayed deadline processing; a late worker does not silently restart the clock. Abandoned preflight images are scheduled for cleanup after one hour. Session/mobile capability records expire by database TTL; consent version/hash/time is also pinned in the core attempt history. Scores, submitted answers, publication data, billing and application history have separate policies and are not deleted by raw-media cleanup.

The explicit worker, from `python-backend`, is:

```
venv/Scripts/python.exe scripts/workers/assessment_retention_worker.py
```

`--once` performs one bounded pass. It loads that backend's `.env`/database: do not run it against the application database just to check imports. Supervise/restart it in the intended deployment. It closes participation after recorded withdrawal/terminal lifecycle without inventing a technical refund, deletes due media through a durable `deleting` journal, retries storage failures and treats cloud NotFound as already deleted. It never marks a failed deletion successful. It expires summaries/events and similarity reports separately, preserving core scores/history.

Preservation requires an authorized owner, reason and expiry (maximum 180 days per approval). Transactional lifecycle fencing prevents a newly approved hold from racing a deletion claim; a hold cannot restore expired/deleting data. Purge refuses an active hold or active attempt. Candidate deletion requests record review requests, not an immediate destructive action. Reviewer media listing is paged; downloads use five-minute private signed URLs and explicit authorization/access audit. Signing/storage failures return an unavailable error rather than a leaked traceback or public fallback.

Before media rollout, verify private bucket IAM, attached service identity, signed-URL permission, access audit, retention worker restart/failure behavior, due-deletion alerts, holds, actual capture consent, per-candidate storage limits, regional/privacy requirements and costs. Retention changes require process restart and apply to new policy snapshots. Capture acceptance flags are operator approvals, not substitute evidence of those checks. Monitor `assessment_media` states/due ages, upload failures, session/frame counts, summary expirations, preservation expiry and access audit; storage failures can delay physical deletion and require operational response.

Incident response: disable new starts/media admission, preserve only specifically authorized evidence with bounded reasoned holds, revoke affected security/mobile sessions, retain immutable submissions/billing/journals, and reconcile private object access/deletion. An incident/coverage gap does not establish misconduct or permit silent score changes. Do not delete or release unknown judge reservations as an integrity cleanup shortcut.

## Quoted optional integrity features

Reviewed pools are prepared **before activation** for a saved setup with `variant_count` 2–5. Select that exact number of published, currently validated/human-approved assessment versions belonging to the setup. Their configuration/marks/counts/difficulty must match and content hashes must be distinct; human review still determines meaningful equivalence and quality. A quoted purchase captures `GENHIRE_EXTRA_VARIANTS_CREDITS` (default 10) per additional reviewed batch. It does not secretly generate questions or replace separately approved authoring/regeneration costs. Balanced assignment occurs transactionally for future invitations; existing invitations/accepted attempts keep their version. Option/question order shuffles once per accepted integrity-enabled attempt and persists; stable answer IDs still grade correctly. Exposure records track accepted recruitment questions; practice never reads this pool.

Similarity is a separate **post-evaluation, per-report** quoted purchase using `GENHIRE_PLAGIARISM_CHECK_CREDITS` (default 10). It is a transparent literal-token five-gram overlap/Jaccard aid, not an AI plagiarism or authorship verdict. It compares nonempty coding answers for the same question/language within the same authorized workflow/owner cohort, excluding an unchanged literal starter. Limits are 100 completed attempts and 2 MB of comparison source. At least two comparable submissions are required before purchase. Common algorithms/templates/short answers can overlap and superficial changes can evade literal comparison; reviewers must assess source and context. Reports contain bounded peer overlap metadata, not source text, private fixtures or fingerprints. No external similarity provider receives source code.

Quotes expire after ten minutes, validate current content/cohort/prices and require explicit cost approval. Report/pool creation and reserve/capture share one transaction. Failed/disabled/uncomparable work is not charged; replayed purchases do not debit twice. Similarity reports are frozen snapshots, not continuous or automatically refreshed cohort scans, and expire through the integrity retention worker. The JD's earlier planned similarity/enriched-analytics flags remain nonactivatable: use the explicit post-evaluation quoted report; fuller pricing/UI consolidation is Step 9. Enriched analytics, audio/AI-authorship detection and unimplemented extras are not sold.

## API and access map

| API | Access / intent |
|---|---|
| `POST /api/assessment-invitations/:id/secure-launch` | Own candidate account; opaque launch code for the approved mode. |
| `POST /api/assessment-launches/redeem` | Short-lived capability/nonce and runtime metadata; no account credential in payload. |
| `POST /api/assessment-invitations/:id/preflight` | Scoped OA session; disclosed consent/readiness before start. |
| `POST /api/assessment-invitations/:id/session-refresh` | Same scoped session only; no broader account rights. |
| `POST /api/assessment-invitations/:id/mobile-pair`, `/camera-frame` | Scoped desktop pairing; frame endpoint also accepts the camera-only companion capability. |
| `POST /api/assessment-invitations/:id/accommodation` | Verified owner/admin application write permission, reason and revision. |
| `POST /api/assessment-attempts/:id/integrity-events` | Own scoped candidate; bounded idempotent observations without text/clipboard contents. |
| `GET /api/assessment-attempts/:id/integrity` | Own candidate status only; owner/reviewer summary with access audit. |
| `POST /api/assessment-attempts/:id/integrity-review`, `/time-extension` | Authorized owner/admin, reason and expected revision; no client score accepted. |
| `GET /api/assessment-attempts/:id/evidence[?after=…]`, `/evidence/:mediaId` | Authorized reviewer only; paged metadata or short-lived signed export link. |
| `POST /api/assessment-attempts/:id/evidence-privacy` | Own candidate request, or authorized reviewer purge/preservation; active attempts/holds enforced. |
| `POST /api/assessment-integrity-quotes`, `/assessment-integrity-purchases` | Verified owner/admin optional purchase with explicit approval and current content/prices. |
| `GET /api/assessment-attempts/:id/similarity` | Authorized reviewer only with access audit; never changes objective score. |

All responses use private/no-store caching policy. No scoped OA/mobile credential can call recruiter, account, billing, job configuration or other-invitation APIs. Standard account authentication remains required for owner/reviewer mutations. No worker was started against the application database during implementation.

## Acceptance and rollback

Local tests exercise real isolated Mongo transactions, fake image/analyzer/GCS fixtures, rendered React and native policy modules. Web and kiosk asset builds plus a worker-file resolver check are not a passed real-browser or native runtime test.

Before enabling, perform actual Electron 1.3.0 installer/build signing/release checks, Windows/macOS shortcut/emergency-exit/relaunch behavior, Monaco worker startup and keyboard/assistive navigation, camera and phone permissions/loss/recovery, capture/storage/signing/deletion/hold drills, actual detector quality/unknown states, live provider evaluation and production load/cost checks. Keep all corresponding approval flags false until those pass. Neither the API capability nor client-reported kiosk metadata proves OS/device trust.

Rollback disables new starts/new optional purchases/media admission, preserves accepted deadlines/answers/consents, and continues authorized recovery, evaluation settlement and evidence deletion/reconciliation. Do not delete accepted records, release unknown execution slots, replace live questions, publish unvalidated code/SQL, auto-release candidate results or auto-send company emails. Step 8 supplies company-stage/results/bulk communication workflows; Step 9 adapts this integrity engine to separate paid practice pools.


## Kiosk UI update (21 October 2026)

The renderer now confirms final submission and leaving an active attempt, keeps
timer/save state visible during scrolling, and warns before replacing edited code
on a language change. Reloading server answers fetches successfully before clearing
local drafts; failed reloads preserve local answers and recovery keys. Monitoring
and deadline rules are unchanged. Preflight privacy details are expandable and
phone pairing has a visible busy state. Rebuild the kiosk renderer and installer
before distributing the changes; a web deployment alone does not update an already
installed packaged renderer. Confirm device, focus/fullscreen and clipboard behavior
on the signed installer as part of existing acceptance.
