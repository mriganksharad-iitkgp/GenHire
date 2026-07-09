# Manual Smoke Checklist

Run the subset touched by a change after each reorganization step; run the
full list before merging/deploying. Every flow must behave exactly as before
the reorganization — same pages, same redirects, same data.

> Local runs talk to the live database — stick to reads where possible and
> reuse existing test accounts instead of creating new data.

## 1. Auth & session
- Login as candidate, recruiter, and admin; each lands on its home
  (`/dashboard`, `/recruiter/dashboard`, `/admin`).
- Visiting a wrong-role URL redirects correctly (e.g. candidate → `/admin`
  bounces to candidate home; logged-out user → `/login`).
- Logout clears the session; expired session redirects to `/login?expired=1`.

## 2. Candidate core
- `/dashboard` loads jobs and applications.
- Open a job (`/job/:jobId`); CV list renders; apply flow opens (CV selection).
- `/profile` loads and CV management renders.

## 3. Practice
- `/practice` starts a practice session (mic/cam permission prompt appears).
- Practice history list renders past sessions.

## 4. Interview (needs mic + webcam)
- Open an interview link; pre-interview checklist and webcam preview work.
- First question TTS plays; an answer round-trips (STT transcribes).
- End interview → report generated; report modal renders.
- Mobile camera pairing: QR at `/mobile-cam/:sessionId` connects and streams.

## 5. Recruiter
- `/recruiter/dashboard` tabs all render (overview, jobs, candidates, activity).
- Job creation modal opens and validates; job edit modal saves.
- Invite-candidates modal opens; application view + interview report modal render.
- "Export Cleared" on a job card downloads the screening-cleared XLSX.

## 6. Admin portal
- `/admin` overview stats load.
- Candidates list → candidate detail; recruiters list → recruiter detail.
- Verification queue renders; cost statistics charts render.

## 7. Payments & subscription
- `/subscription` (recruiter) and `/candidate/subscription` render plans.
- Payment history renders. (Full payment flow only when explicitly testing.)

## 8. Public pages
- `/` landing page, `/register`, `/recruiter-signup`, `/verify-email`,
  `/forgot-password`, `/reset-password`, `/invite/redeem` all render.
- `/404` renders for unknown URLs.
