# Candidate separation and portal UI audit

## Navigation and responsibilities

| Navbar section | Route | Purpose |
| --- | --- | --- |
| Open Positions | `/dashboard` | Search, filter, save and apply to jobs. |
| My Applications | `/applications` | Application status, job-specific CV/interview/proctoring scores, details, reports and shortlisted interview actions. |
| My Profile | `/profile` | Personal details, profile photo, uploaded CVs, manually entered CV details, identity document, application statistics and account settings. |
| Practice | `/practice` | Choose a role and difficulty, launch practice and review practice history. |
| Cost Statistics | `/candidate/cost-statistics` | Wallet balance, credit usage and recharge history. |
| Team | `/team` | The existing developer directory. |

CV management and personal details belong together in My Profile. My Applications
is now a focused workflow rather than another tab inside profile editing. Credit
usage remains separate because it describes the wallet rather than the candidate's
professional profile. CV scores remain on applications because they measure fit
for a particular job; an overall CV score would imply a different measurement.

Invite-only candidates retain the existing restricted navigation, plus My Profile;
Practice, Cost Statistics, Team and credit purchasing stay hidden for them.

Old `/profile#applications` and `/profile?tab=applications` bookmarks redirect to
`/applications` before profile/CV features mount. Other query parameters survive.
An explicit `#bio` takes precedence over a legacy query. The interview return link
and application-detail back buttons now use the canonical applications route.
Navbar selection follows the URL, including application and job detail routes;
normal browser back/forward works without maintaining a second tab state.

## How the UI now stays consistent

`PortalPageHeader` is shared by candidate jobs, applications, profile, practice,
usage and team, and recruiter overview, jobs, candidates, company profile, usage
and team. It provides the same pale lavender gradient, indigo eyebrow, slate
heading, responsive actions and restrained decorative circle.

`portal-theme.css` holds the common colors, purple gradient, borders, backgrounds
and shadows. Feature CSS remains scoped so it cannot replace the landing page's
layout or recolor unrelated pages. Candidate Dashboard and Practice's older
variables now belong to their page containers rather than the global root.

Cards use consistent rounded surfaces and quieter shadows. Primary actions use
purple; green, amber and red retain their meaning for status and scores. Desktop
form text is 14px, with 16px mobile inputs where needed to avoid automatic zoom.
Headers use 30px desktop and 26px small-screen text. The duplicate navbar offset
was removed from candidate jobs and practice; Layout already reserves 80px.

Candidate job cards use two columns on desktop and one on narrower screens.
Long descriptions have a three-line preview with full content available through
View Details. Filters and profile columns stack on small screens. My Profile
shows details/statistics first on mobile and CV management in the next section.
Practice role/difficulty choices support Enter and Space. Search/filter fields
and personal/company form fields have accessible names.

Recruiter company profile now has a summary view with company identity, labelled
information and description. Edit Profile opens the form; Save/Cancel preserve
the existing update flow. Jobs, candidates and overview retain their existing
functional actions within the shared visual style. Both roles use the same Team
and cost-statistics surfaces. CV selection and detail dialogs also use compact,
readable lavender headers and purple controls.

The landing source and CSS were not changed.

## Workflow fixes found during the audit

- Candidate usage API failure previously generated a zero-balance fallback. It
  now shows an error and Retry, with request cancellation and a 10-second timeout.
- Application fetch failures show Retry rather than a false empty applications
  screen. Profile fetch failure hides the save form until a successful retry.
- Repeated profile submissions share one pending save; failed saves preserve the
  candidate's field values. Failed manual CV-detail saves keep the editor open.
- A zero similarity score is now preserved as 0%. Applications retain their
  selected CV ID, so previews refer to the application CV rather than silently
  choosing the current primary CV.
- CV previews fetch authenticated blobs through the shared API client, open in a
  focused modal, and revoke temporary URLs on close. Tokens are not placed in
  preview URLs. Loading, timeout, missing-file and retry states are visible.
- Candidate jobs/practice/detail requests now use the shared API base, honoring
  `REACT_APP_API_BASE`, `REACT_APP_API_URL` or the relative `/api` fallback.
- Application pagination clamps its current page after list changes; invalid
  dates have a readable fallback. Global emergency timeline styles were removed
  from ApplicationView imports because they targeted other components by class
  substring as well as the timeline itself.

Application/profile hooks continue using CandidateDataContext caching and live
application updates. Separating pages does not introduce a separate store or
extra polling layer. Navbar still loads the basic account identity; applications
no longer mount profile editing, identity upload or the multi-CV management list.

## Verification

The portal regression script mounts the actual React pages, uses fixture API
responses, compiles their CSS modules and checks navigation, state and resolved
styles at 1366x768, 909x642 and 390x844. It covers canonical/legacy routes,
back/forward, profile/application separation, filters, zero scores, CV previews,
reports, kiosk guidance, recruiter tabs, company editing and recoverable errors.

Verification passed: 16 contract tests, 36 portal regression checks, lint, web
build, kiosk web build and `git diff --check`. The landing source/CSS diff is empty.
Commands and results are recorded in [the completed plan](ui-improvement-plan.md).
Browser
inventory has no connected apps or tabs. Real browser geometry, screenshots,
live account authentication, real PDF rendering, file uploads and kiosk launch
were not exercised. Fixture tests do not write to live accounts or production.

For a manual visual pass, open each navbar section on a desktop, at 909px width
and on a phone. Check long company/job names, empty lists, a real CV preview,
profile save/upload and an existing shortlisted application's installation guide.
