> ARCHIVED: OneCompiler was superseded by OnlineCompiler.io. Historical findings only; use [the final setup guide](OA_FINAL_SETUP.md).

# Which OneCompiler product GenHire needs

Reviewed 21 October 2026 against the supplied documentation and official pages.

## Decision for the current OA

Use **Code Execution API access to `POST /v1/run`**, called by the GenHire
backend, for programming, MySQL and PostgreSQL. Keep GenHire's existing editor,
hidden-test grading, MCQ scoring, scheduling, billing, reports and proctoring.
The required entitlement is execution access; Enterprise Challenges, Studio and
AI Interviews are not required for the present 3 coding + 2 SQL + 20 MCQ OA.

This recommendation concerns the required product capability, not a claim that
the saved key already has that entitlement or that a particular subscription is
active.

## What can be established about the saved key

- Both private backend profiles contain a saved key. Its value was not included
  in reports or transmitted to documentation/search services.
- The Code Execution guide's API Console link points to
  `https://onecompiler.com/api-console`. This is the relevant official console
  to inspect for execution credits/usage and account configuration.
- Both the execution and Enterprise documentation authenticate examples with
  `X-API-Key`. The documentation does not provide a reliable key-prefix rule
  that classifies the saved key as execution-only or Enterprise-enabled.
- There is no connected browser session available to inspect the user's
  signed-in account. The console's public page does not expose the account's
  plan or key permissions. The exact creation screen and account entitlements
  therefore remain unverified.

### Fresh live test

The saved local `.env` was retested with a minimal Python request using the
documented endpoint, JSON payload and header. The response was:

```text
POST https://api.onecompiler.com/v1/run
HTTP 403
Server: cloudflare
Content-Type: text/html; charset=UTF-8
Interactive Cloudflare challenge detected
```

This is an access-protection response, not OneCompiler's documented JSON
`E003: invalid access_token` response. It neither validates nor invalidates the
key, and it does not identify the key's product entitlements. Python execution
did not complete; batch and SQL tests were consequently not sent. No application
database, real candidate data, account users or challenges were modified.

Creating Enterprise users or challenges would not be a useful key-type probe:
it changes the account and still would not resolve the access challenge.

## How the products apply to GenHire

| Product | What it provides | Fit for our OA |
| --- | --- | --- |
| Code Execution API | Server-side execution with stdout/errors/metrics and batch stdin | **Use now.** Run candidate code and controlled SQL datasets through GenHire's backend. |
| Free Editor iframe | Embedded editor with visible execution and code-change/run events | Optional practice playground. It does not establish a trusted backend grading or hidden-test API. |
| Enterprise Challenges | Synced users, hosted challenges, submissions and plan-dependent reports/tracking | Consider only if deliberately replacing part of GenHire's assessment workflow with OneCompiler's hosted challenge system. |
| Studio | Persistent project/workspace environments, user-token integration and workspace-hour pricing | Consider for future full-stack/project assessments. Current stdin/stdout and SQL questions do not need it. |
| AI practice interviews | Hosted voice/chat interview sessions, user sync/tokens and session credits | Separate optional product; current OA execution does not need it. Preserve existing GenHire AI services. |

The Enterprise docs include useful capabilities such as challenge time limits,
tracking and submission management. They also add vendor user synchronization,
user-token storage, challenge lifecycle and report integration. Those are a
different integration scope from executing code for GenHire's own judge.

## Why the free iframe does not make hidden grading free

The documented free editor is a browser UI. It supports populating source,
triggering visible runs and receiving code-change events. The documentation does
not promise a free, trusted server-side hidden-test grading endpoint or API
quota for GenHire's backend.

Sending hidden inputs, expected outputs, reference solutions or seeds into a
candidate's iframe/postMessage/browser flow discloses them to that client.
`hideStdin`, `hideResult` and similar options control presentation; they do not
provide secrecy for data delivered to the browser. Browser events alone must
not set a final grade, wallet charge or application outcome.

If a practice iframe is added later, use an explicit postMessage target origin,
validate incoming `event.origin`, `event.source` and payload structure, and keep
assessment verdicts server-side. Do not blindly copy wildcard postMessage
examples. Never put GenHire's secret `ONECOMPILER_API_KEY` into iframe URLs.
The Enterprise example's `apiKey` URL parameter requires clarification of the
vendor's publishable account ID versus secret-key model before reuse.

For SQL, a visible browser sandbox likewise does not prove fresh independent
datasets or trustworthy typed result sets. Keep the existing live SQL acceptance
requirement. Studio workspaces would need their own candidate isolation/reset
and cost design if adopted later.

## The pricing pages describe different billing models

The execution guide advertises direct credits: USD 1 buys 2,000 credits, with
higher-volume purchase tiers. The separate pricing page lists monthly P1-P4
call allowances and Enterprise plans. Do not assume all of these prices apply
to the same key, contract or billing channel. Marketplace credentials/endpoints
also need their own documented authentication; do not assume a direct-console
key authenticates a marketplace subscription, or the reverse.

The earlier INR 2.21 final-grading estimate remains a **conditional direct-credit
estimate**: 46 execution credits, USD 1 per 2,000 credits, and the project's
configured INR 96/USD conversion. It is not a verified invoice for this account.

For comparison, the official INR pricing page currently lists:

| Plan | Advertised monthly fee | Monthly calls | Allocated cost for 46 calls at full quota utilization |
| --- | ---: | ---: | ---: |
| P1 | INR 420 | 10,000 | INR 1.93 |
| P2 | INR 840 | 30,000 | INR 1.29 |
| P3 | INR 2,100 | 100,000 | INR 0.97 |
| P4 | INR 4,200 | 300,000 | INR 0.64 |

These are allocation examples, not an entitlement or purchase confirmation.
The INR and USD price pages are not numerically identical under our configured
exchange rate; confirm the currency/amount offered to the actual account.
For a monthly subscription, the bill is the subscription fee rather than
46 times a fictional pay-as-you-go charge. At only 100 OAs per month, P1's
INR 420 fee would allocate INR 4.20 per OA before other costs, assuming those
OAs and shared validation fit the call allowance.

The 46-call example assumes 14 hidden tests for each of three coding questions
and two datasets for each of two SQL questions. Twenty MCQs are graded by
GenHire. Practice runs, reference validation and acceptance checks consume
additional executions/allowance. Confirm actual batch charging and overage rules
for the purchased plan before treating allowance estimates as exact.

## What is needed to finish identifying the account and activate execution

1. Inspect the signed-in official API Console for the selected key's enabled
   APIs/permissions, billing product, credit balance or monthly allowance, and
   any restrictions shown. If the UI does not expose product permissions,
   OneCompiler support must confirm execution entitlement for that account.
2. Confirm direct Code Execution access to `/v1/run` for Python, C/C++, Java,
   Node.js, MySQL and PostgreSQL. Enterprise extras are optional unless their
   hosted challenge features are deliberately selected later.
3. Resolve the interactive Cloudflare challenge for legitimate backend API
   traffic. Ask support to confirm the correct direct endpoint and access
   restrictions for the account. A plan upgrade alone is not evidence that
   this challenge will disappear.
4. Retest from the intended GCP backend network as well. A result from this
   agent's outbound network does not establish what GCP will receive.
5. Once a JSON execution response succeeds, complete batch, runtime-version,
   resource-evidence and controlled MySQL/PostgreSQL dataset checks, followed
   by the reviewed production acceptance procedure.

To verify the exact subscribed product here, supply a connected signed-in
browser session or an API Console screenshot showing product/plan/permissions
and balances with **keys and tokens hidden**. Never paste the secret key.
The earlier screenshot shows the env assignment, which cannot establish the
console product, subscription or permissions.

## Official references

- [API overview and console link](https://onecompiler.com/apis)
- [Code Execution API](https://onecompiler.com/apis/code-execution)
- [Enterprise API](https://onecompiler.com/apis/enterprise)
- [Free embedded editor](https://onecompiler.com/apis/embed-editor)
- [Embedded challenges](https://onecompiler.com/apis/embed-challenges)
- [USD plans](https://onecompiler.com/apis/pricing)
- [INR plans](https://onecompiler.com/apis/pricing-inr)

Also see [the live check and execution-cost report](ONECOMPILER_CHECK_AND_COST.md)
and [activation checklist](ONECOMPILER_NEXT_STEPS.md).
