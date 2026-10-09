# Current-theme auth and recruiter improvement plan

Keep the current landing page theme throughout auth and both portals. The latest reference
uses indigo/purple gradients, pale lavender backgrounds, white cards and dark
slate text. The landing page itself is outside this change.

## Steps

- [x] Reproduce and fix blank candidate applications and recruiter portal; ensure the root error screen can render.
- [x] Correct router-driven candidate sections and recruiter tabs, including direct links and browser history.
- [x] Put recruiter Overview, Jobs, Candidates, Company profile, Cost statistics and Team in the shared navbar; support mobile navigation.
- [x] Match login and candidate/recruiter signup to the existing landing palette, with shared illustration, typography, controls and responsive layout.
- [x] Refine recruiter overview, job cards, candidate filters/cards, company profile and dialogs with one compact, accessible style.
- [x] Mount actual pages/dialogs with fixture data, verify navigation and resolved styles, and run lint, contracts and production builds.
- [x] Document what changed, why the pages failed, how navigation/styles work and verification limits.

## Audit findings

`interviewScore(null)` throws while reading `evaluation`. Candidate Profile and
RecruiterDashboard both render a closed report dialog with a null report. The
root ErrorBoundary then renders a router Link above BrowserRouter, producing
the `basename` error shown in the screenshots and hiding the original crash.

Candidate profile follows native hashchange events, but router links update
history without that event. Recruiter tab state retains its previous value when
the query is removed, and the legacy recruiter redirect drops query parameters.

Login currently uses a separate navy palette. Signup is a centered legacy form.
Recruiter CSS contains multiple conflicting rules for the same cards/filters,
with different colors and oversized padding. These are the scoped UI targets.


## Final audit - 9 October 2026

- Landing source and CSS remain unchanged; the new variables only affect the scoped auth/recruiter components.
- Closed reports, older evaluation formats and structured feedback render safely. Root error recovery works above the router.
- Candidate applications follow router hash/query changes. Local profile buttons also navigate through the router.
- Recruiter sections use the navbar, query-based selection and normal browser history. The unused second tab bar was removed.
- View Candidates now filters by the selected job ID, matching the actual filter contract.
- Login, candidate signup and recruiter signup share lavender artwork, 14px desktop input text and 49px controls. Mobile inputs use 16px text to avoid automatic zoom.
- Recruiter overview, jobs, candidates, company profile, cost statistics, team and job/invite dialogs use compact spacing and readable headings.
- Temporary account verification and usage failures show Retry. Invalid sessions redirect to login. Failed usage requests no longer display invented zero balances.

Verification: 15 contract tests, 25 portal regression checks, lint, web build and
kiosk web build passed. Portal checks mount the real components with fixture APIs
and compiled styles, including responsive rules at 1366x768, 909x642 and 390x844.
Local frontend responds 200 and the unauthenticated API responds 401 as expected.
Browser inventory has no connected apps/tabs, so real browser screenshot/layout
review and sign-in with a real account remain unverified. No accounts, messages,
payments, backend credentials or deployments were changed.

See [the implementation explanation](auth-recruiter-ui-audit.md) for causes,
navigation/style design, commands and a short manual browser review checklist.

## Candidate separation and portal theme follow-up

The landing page stays unchanged. Both portals will use its indigo/purple
gradients, lavender surfaces, rounded white cards and dark slate typography.

- [x] Create a dedicated /applications page for filters, application actions and reports.
- [x] Keep /profile for personal details, photo, CVs, identity upload and application statistics; add My Profile to the navbar.
- [x] Redirect older profile application links and preserve browser navigation.
- [x] Use a shared responsive page header for both portals and improve recruiter company profile, jobs, candidates, overview, usage and team.
- [x] Standardize candidate jobs, applications, profile, practice, usage, team and detail pages; remove duplicate navbar offsets.
- [x] Audit loading/error/empty states and keyboard access; verify actual components, navigation and compiled styles.
- [x] Update this checklist and explain the final flow and verification limits.

Audit: the existing profile mounts CV/profile features on the applications view.
Candidate Dashboard and Practice add their own navbar spacing inside Layout,
which already reserves 80px. Candidate feature CSS still uses blue controls and
green primary actions instead of the landing palette. Recruiter company profile
uses disabled form controls even when simply viewing company information.


## Follow-up final audit - 9 October 2026

The dedicated applications/profile routes, legacy redirects and shared headers
are implemented. Recruiter company profile now distinguishes viewing from
editing. Candidate jobs, practice, profile, applications, detail pages, usage,
team and CV dialogs use the landing palette. The landing itself is unchanged.

Final verification completed:

- `npm test`: 16 contract tests passed.
- `npm run test:portals`: 36 actual-component regression checks passed, including repeated profile saves, failed-save field preservation, CV preview retries and compact candidate CV dialog headers.
- `npm run lint:ci`: passed.
- `npm run build`: passed.
- `npm run build:kiosk`: passed.
- `git diff --check`: passed.
- Landing source/CSS diff: empty.

The component checks use fixture APIs and compiled styles at 1366x768, 909x642
and 390x844. No browser is connected, so real browser geometry/screenshots, live
account login, real PDF rendering, file uploads and kiosk launch remain unverified.
No live accounts, backend credentials or deployments were changed.

See [the candidate/portal implementation explanation](candidate-portal-ui-audit.md)
for the routes, responsibilities, shared styling, fixes and verification limits.

## Interview, kiosk and remaining surfaces

The shared theme now also covers interview setup, active interview, result/report
states, the mobile companion and kiosk entry. Job create/edit/view dialogs use
professional wording and consistent monitoring controls. Account recovery, billing
returns/recharge screens and admin navigation/headers are aligned. The latest
verification includes 44 portal checks and 16 frontend contracts.

See [the backend and remaining UI audit](interview-theme-runtime-plan.md) for the
startup fix, commands, index protection, full test results and kiosk packaging.

## Interview and application usability follow-up

- [x] Separate spoken and typed answers so typing cannot trigger the voice silence timer.
- [x] Protect unsent recordings and typed drafts when changing answer format.
- [x] Show the backend question deadline without changing timing or billing rules.
- [x] Add camera/microphone/connection recovery and phone QR refresh for the existing interview session.
- [x] Make recording upload failures and unsafe leaving clear, with themed confirmations.
- [x] Refresh applications after returning from the secure browser; retain cards on refresh failure.
- [x] Add application overview, status-specific next steps and useful empty states.
- [x] Improve shared dialog focus, keyboard, nesting, fullscreen and scroll behavior.
- [x] Verify real-component behavior, responsive styles, lint and web/kiosk compilation.

See [the interview usability explanation and release checklist](interview-usability-improvements.md)
for the flow changes, verification limits and the installer rebuild required for
users of an already installed secure browser. The landing theme and environment
files remain unchanged.
