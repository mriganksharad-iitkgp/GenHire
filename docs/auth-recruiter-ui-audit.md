# Auth and recruiter UI: implementation and verification

Updated 9 October 2026 after the UI revert. The current landing/candidate palette
is the reference: indigo/purple gradients, lavender surfaces, white cards and
slate text. Landing layout, content and stylesheet were kept.

## Why both portals went blank

Both Candidate Profile and RecruiterDashboard mount an interview report modal
while it is closed. Its initial report is `null`. The modal still calculates
scores before returning `null`, and `interviewScore(null)` tried to read
`evaluation`, which throws. The root ErrorBoundary then tried to render a React
Router Link outside BrowserRouter. That produced the `basename` error in the
screenshots and hid the first error.

The score helper now returns an unavailable score for missing reports. A shared
parser accepts JSON objects and older text reports, and normalizes JSON null and
arrays. The modal guards its transcript/question collections and renders
structured feedback as text. Actual zero scores remain zero. The error boundary
uses a normal home anchor, so it can recover even when the router has failed.

## How navigation now works

The shared navbar uses one definition in
`react-frontend/src/shared/components/layout/navigation.js` for both desktop and
mobile links. Recruiters have Overview, Jobs, Candidates, Company profile, Cost
statistics and Team. Dashboard selection comes directly from `?tab=...`;
removing an invalid/missing query selects Overview. Browser back/forward and
bookmarked URLs use the same state. The duplicate content-area recruiter tabs
were removed. Legacy recruiter URLs preserve their query during redirect.

Candidate Profile observes React Router's location instead of native hashchange
listeners. Navbar links and local tab buttons now select the same section, even
when the user is already on Profile. Both `#applications` and
`?tab=applications` work; an explicit hash takes precedence.

View Candidates had another mismatch: it saved a job title as the selected
filter, while filtering compared job IDs. It now passes the actual ID, including
when different postings share the same title.

## How the UI stays consistent

`shared/styles/portal-theme.css` defines the scoped palette. It introduces new
variables without rewriting existing landing/candidate style rules.
`features/auth/components/AuthStory`, `AuthBrand` and `AuthShell` provide the
shared illustration and signup composition. Login uses the same artwork.

Login and both signup forms use 13px labels, 14px desktop input text and 49px
controls. On phones, 16px input text avoids automatic browser zoom. Forms have
bounded widths, the illustration adapts to shorter desktop viewports, and long
signup forms can scroll normally. The decorative panel is hidden on phones,
where a compact brand appears above the form. Reduced motion is supported.

RecruiterDashboard's conflicting repeated rules were replaced by a single
scoped stylesheet. Overview metrics, job cards, candidate filters/cards and
company fields now share spacing, borders, action styles and typography.
Candidate cards stack on narrow screens, and long values can wrap. Job creation,
edit/details, JD and invitation dialogs use readable light headers, compact
controls and viewport-bounded scrolling. Primary actions retain visible white
text on hover. Disabled company values remain readable; missing CV actions are
disabled instead of opening an invalid URL. Cost statistics and recruiter Team
reuse the same navbar and page scale.

## Recoverable loading failures

Account verification now uses the central API client with cancellation and a
10-second timeout. A network error, server failure or incomplete response shows
Retry without deleting the session. A genuine 401 clears the session and routes
to login. The recruiter usage page follows the same pattern, using the configured
API base and cancelling requests when unmounted. Failed usage requests show an
error instead of a fabricated empty wallet/dashboard.

## Verification

Run from `react-frontend`:

```powershell
npm test
npm run test:portals
npm run lint:ci
npm run build
npm run build:kiosk
```

- 15 contract tests passed, including unavailable/zero scores, older report formats and navigation rules.
- 25 portal regression checks passed. These mount actual React components with fixture API responses and compiled CSS. They cover populated candidate applications, every recruiter section, direct/legacy links, router history, mobile navigation, exact job filters, incomplete candidate cards, reports, five recruiter dialogs, auth form sizing, hover contrast and retry/401 behavior.
- Responsive CSS rules were checked at 1366x768, 909x642 and 390x844. These are DOM/style checks, not browser geometry or screenshots.
- Lint and both production web bundles passed. Lint reports an existing stale Browserslist database notice.
- Local frontend responds 200; `/api/me` without a token responds 401, which is expected.

The computer-use inventory has no connected browser or native app. Real browser
layout and sign-in with actual credentials could not be verified in this session.
The smoke suite uses fixture accounts only and stubs sockets/chart drawing; it
does not verify live authentication, socket delivery, charts or payments.

For a browser review, refresh once, check login and both signup forms at desktop
and phone widths, then sign in as each role. Open My Applications while already
on Profile; switch every recruiter navbar section; test browser back/forward;
open a job's View Candidates action and create/edit/details dialogs. Check that
all controls remain reachable by scrolling and that no horizontal content is
cut off. This review is the remaining visual validation, not a deployment step.
