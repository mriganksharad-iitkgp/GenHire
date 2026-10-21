# Website content and UX update

20 October 2026. Reviewed the frontend route inventory, public landing/metadata,
authentication, candidate and recruiter pages, practice, wallet, assessment,
company-stage and admin surfaces for the screening-only product description.

## Changes applied

| Surface | Update |
|---|---|
| Landing hero, feature cards and workflow preview | Present CV fit, AI screening, coding/SQL/MCQ OAs and recruiter-controlled next rounds together. The dashboard illustration is explicitly an example. |
| Candidate/recruiter journeys | Separate real screening from practice, explain optional OA invitations and company-led later rounds. Animation changes every 2 seconds instead of 4. Selecting a step pauses it; explicit pause/resume, reduced motion and hidden-page pause are supported. Steps are keyboard-accessible buttons. |
| Landing role section and FAQ | Explain software, data, product/DevOps use cases, manual/AI/hybrid questions, weighted tests, optional rounds and paid practice. Replace placeholder testimonials, company logos and unsupported usage figures with product capabilities and role examples. |
| Credits and recharge descriptions | Explain setup, accepted recruitment attempts, mock generation and optional extras with server prices. Remove blanket completion-only/refund promises and unlimited-practice wording. |
| Public navigation/footer | Link to actual sections and account routes, removing placeholder social/API/legal destinations. Add skip-to-content, visible keyboard focus, mobile expanded state, inert closed drawer and Escape-to-close with focus return. |
| Login, registration and recruiter onboarding | Describe screening, online assessments, practice and company rounds together. Update shared authentication illustration captions. |
| Candidate jobs, applications and job details | Explain stages and deadlines without promising that screening clearance guarantees another round. Job details explain where next-round invitations appear. |
| Practice | Distinguish interview and mock OA preparation. Style the mode switcher with pressed states, focus rings and wrapping controls; preserve other query parameters when switching modes. |
| Recruiter dashboard/jobs/candidates | Describe combined role setup, thresholds, OA results and company-stage decisions. Update the team description. |
| Candidate/recruiter wallet pages | Describe OA activity quotes and use the server-configured signup bonus. Remove hardcoded paid fallback offers after a plan-service failure. Retry restores authoritative packs. |
| Search/social/install metadata | Update HTML title, descriptions, Open Graph, social descriptions, relevant keywords, JSON-LD application/FAQ content and install manifest. |

Assessment editors, runtime, result reports and admin operations already describe
their specific OA actions; their operational terminology and existing feature
gates remain in place. Interview-only controls still describe interviews.

## Important UX defects corrected

1. Job-detail fetch failure previously constructed a fake job with invented skills,
   responsibilities and an Apply button. It now shows an error, Retry and a link
   back to open positions. A successful retry restores the real job.
2. Both wallet pages previously offered hardcoded recharge packs during service
   failures. They now withhold paid packs and show a retryable unavailable-price
   message. The informational signup bonus uses the server catalog, not a fixed
   100-credit claim. Checkout/backend credit rules were not changed.
3. A closed mobile landing drawer is now inert and excluded from accessibility
   navigation. Workflow steps can be selected from the keyboard, and animation
   respects reduced motion, with a static fallback if matchMedia is unavailable.
4. Longer OA credit descriptions wrap on narrow screens; hero actions can wrap
   instead of forcing a single overflowing row.

## Validation and limits

Final results: **53 portal checks, 5 landing checks and 9 practice OA checks
passed**. ESLint and the final production build exited successfully. JSON-LD,
manifest JSON and `git diff --check` validation passed.

- New offline landing checks cover product copy, working section anchors, 2-second
  rotation, pause/manual selection, reduced motion, mobile Escape/focus handling
  and price-catalog retry. Added to `npm run check:oa`.
- Portal regression coverage adds job failure/recovery and both wallets' price
  outage/recovery, including a nondefault server signup bonus.
- Existing mock OA tests exercise public pricing and practice purchase/report
  behavior. Fixtures make no live purchases or account changes.
- ESLint and production build are run for this change. Builds retain existing
  large-chunk/Browserslist notices; dependency upgrades are outside this change.
- No connected interactive browser was available. A headless Chrome screenshot
  attempt exited before producing an image. Component/interaction and responsive
  CSS checks are automated; a real desktop/mobile visual review remains pending.
- No production deployment, provider activation or backend environment changes
  are part of this website update.

## Subsequent job-authoring update

The owner's subsequent request explicitly opted into all 17 OA switches in both
private backend profiles. Those file edits supersede earlier disabled-profile
notes; they do not establish live acceptance or change GCP deployments.

Create/edit share 19 searchable, keyboard-accessible job starters and 16 OA
presets. Both show the optional OA card immediately. First-time enabling infers
the role from the current title and fills counts, difficulty, marks, time and
topic instructions. Existing customized plans and off/on toggles preserve edits;
an explicit reset applies current role defaults. Legacy OA-off versions with the
untouched SDE default now initialize the correct role when first enabled.

Catalog/saved-settings failures offer retry while preserving the job fields.
Unavailable/disabled assessment settings are visible rather than silently
removing all mention of OAs. Dialog headings and inputs have distinct IDs,
standalone core labels link to inputs, template lists scroll within a bounded
area, and the create form's completion count measures its actual seven core
fields. Templates intentionally avoid inventing salary bands or employer benefits.


## 21 October 2026: operational panel styling

The mock OA form, billing history and company pipeline had native unstyled
controls because their components did not import a stylesheet. A scoped
OperationalPanels CSS module now supplies portal cards, typography, controls,
focus/hover/pressed feedback, alerts, accordions and light/dark presentation.
Practice settings and company filters use responsive grids; comparison and
evaluation tables have keyboard-focusable horizontal scroll containers. The
practice route now has a bounded content wrapper shared by both practice modes.
The same styles cover related candidate results, recruiter reviews, integrity
controls and support panels. No global native-control reset or kiosk stylesheet
change was introduced. API contracts and explicit paid/email approvals remain.

Validation: full frontend lint; production web build; 83 rendered fixture checks
across portal (53), practice (9), company hiring (8), evaluation (3), progression
(6), and integrity (4). These checks do not establish real-device visual or
production acceptance.
