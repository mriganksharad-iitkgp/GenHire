> ARCHIVED: OneCompiler was superseded by OnlineCompiler.io. Historical findings only; use [the final setup guide](OA_FINAL_SETUP.md).

# OneCompiler key check and OA cost estimate

Checked 21 October 2026 for an OA containing **3 coding questions, 2 SQL
questions and 20 MCQs**.

The key's exact account product and billing model remain unverified. The figures
below assume direct pay-as-you-go credits. The separately advertised P1-P4
monthly subscriptions have different allowance-based economics; see
[the product and plan comparison](ONECOMPILER_OA_PRODUCT_DECISION.md). A fresh
local-profile execution retest still received the Cloudflare HTTP 403 challenge.

## Live check result

### Exact supplied-key diagnostic

The key explicitly supplied in chat was tested directly against `/v1/run`; it
differs from the current saved local `.env` value. No env file was overwritten.
An otherwise identical request without any API key was also sent as a control.
Both returned HTTP 403, `server: cloudflare`, `cf-mitigated: challenge`, and the
HTML title `Just a moment...`. Neither returned an API authentication result.

Cloudflare Ray IDs for provider support:

- Supplied-key request: `a4e19ff47a61937a-MAA`.
- No-key control: `a4e19ff59b2d937a-MAA`.

The established failure is an interactive edge-access challenge for this
request path/network, not a confirmed bad-key error. Actual key validity and
entitlement remain unknown until an API JSON response can be obtained.

- The saved `python-backend/.env.production` now contains a nonempty
  `ONECOMPILER_API_KEY`. Its value was not printed or copied into this report.
- The saved local `python-backend/.env` now also contains a nonempty key. It was
  retested directly after the owner saved it.
- The initial sandbox request was blocked by local network permissions before
  reaching OneCompiler. After using authorized external network access, the
  request to `https://api.onecompiler.com/v1/run` received **HTTP 403**.
- A minimal diagnostic request confirmed a Cloudflare HTML challenge titled
  **“Just a moment…”**, rather than a OneCompiler JSON API response.
- Therefore **key validity remains unconfirmed**. This response does not prove
  that the key is invalid. Python execution, batch execution and SQL could not
  be verified. SQL tests were not dispatched after the initial request failed.
- The local-profile retest returned `HTTP 403`, `server: cloudflare`,
  `content-type: text/html; charset=UTF-8`, and a confirmed interactive
  Cloudflare challenge. The attached official documentation confirms the same
  `/v1/run` endpoint, JSON body and `X-API-Key` header used by this request.
  No additional documentation is needed to diagnose this particular access block.
- No application database was accessed and no production acceptance record was
  created. The responses did not report credit consumption.

### What to do about the 403

Ask OneCompiler support to confirm that `https://api.onecompiler.com/v1/run` is
the correct direct API endpoint for your key and that server-to-server POSTs
from your backend are allowed without an interactive Cloudflare challenge.
Provide the HTTP status and approximate request time; keep the API key private.

Suggested support message:

> We are integrating OneCompiler server-side using the documented
> POST https://api.onecompiler.com/v1/run endpoint with Content-Type:
> application/json and X-API-Key. A minimal Python execution request receives
> HTTP 403, server: cloudflare, text/html, and a "Just a moment..." interactive
> challenge instead of a JSON API response. Please confirm the direct endpoint
> for our account and allow legitimate server-to-server API requests without
> an interactive challenge. We can supply backend egress details privately.

The result above applies to this test environment's outbound network. Test from
the deployed GCP backend as well to establish whether its outbound traffic has
the same restriction. After API access works, run the actual acceptance command
in [the activation checklist](ONECOMPILER_NEXT_STEPS.md). SQL still needs the
reviewed isolation-policy ID and real `sql_verified: true` acceptance.

## Estimated OneCompiler cost per candidate

This is the **execution-provider cost**, separate from GenHire wallet credits,
AI generation, backend hosting, proctoring and storage.

Assumptions for the current implementation:

- Each coding question contains 16 tests: two public samples and 14 hidden tests.
  Final coding grading executes the 14 hidden tests in the candidate's selected
  language, rather than running all available languages.
- Each SQL question has two weighted datasets: one sample and one hidden.
  Final SQL grading executes both datasets.
- Each small successful execution is estimated at one OneCompiler credit.
  This remains an estimate until reconciled with the actual account's billing.
- Currency conversion uses the project's configured `INR_PER_USD=96` in both
  backend profiles. It is a planning conversion, not a quoted bank settlement rate.

| Part | Execution count | Standard-tier estimate |
| --- | ---: | ---: |
| 3 coding questions x 14 hidden tests | 42 | INR 2.016 |
| 2 SQL questions x 2 datasets | 4 | INR 0.192 |
| 20 MCQs, graded by GenHire | 0 OneCompiler executions | INR 0 |
| **Final grading total** | **46** | **INR 2.21** |

The formula is:

```text
Execution credits ~= 3 x hidden coding tests per question
                   + 2 x SQL datasets per question
                   + paid public practice runs

Rupee estimate = execution credits x 96 / credits purchased per USD
```

The current final-grading dispatcher executes each test/dataset separately.
Five executable questions do not mean only five provider executions. Reference
validation can batch stdin cases; a batch also does not establish that multiple
test executions are billed as one credit.

### Practice runs and purchase tiers

The configured maximum is ten public runs **per question**. Across three coding
and two SQL questions, that allows up to 50 additional executions. Public Run
executes one selected sample/custom-input case per request, so this example is
46 final executions + 50 practice executions = **96 execution credits**.

| Advertised purchase tier | Credits per USD | Final grading: 46 credits | With all 50 practice runs: 96 credits |
| --- | ---: | ---: | ---: |
| Standard | 2,000 | **INR 2.21** | **INR 4.61** |
| USD 100 or higher purchase | 4,000 | INR 1.10 | INR 2.30 |
| USD 500 or higher purchase | 6,000 | INR 0.74 | INR 1.54 |

The discounted rates depend on the credits actually purchased for the account;
they are not automatically applied to every account. Introductory free credits
can cover some initial usage, but they are not a sustainable per-candidate price.

If a coding question instead has 13-18 hidden tests (15-20 total tests with two
samples), final grading would be approximately **43-58 credits**, or
**INR 2.06-2.78** at the standard tier, with the same SQL dataset assumptions.
Actual saved question content determines the execution count.

## Additional costs outside the candidate execution estimate

- **Reference validation when authoring questions:** for example, three coding
  questions x four languages x 16 cases, plus two SQL questions x two datasets,
  estimates 196 execution credits, or **INR 9.41** at the standard tier. This is
  question-set setup work that can be shared across candidates, not an automatic
  INR 9.41 charge on each candidate attempt. Edits/revalidation add further work.
- **Live acceptance and renewal:** the operator checks also execute code/SQL.
  Account for them separately and amortize shared setup costs across candidates.
- **AI generation/feedback:** depends on provider, model, tokens, generation
  frequency and reuse. Twenty MCQs have no OneCompiler grading charge, but their
  AI generation can still incur an AI-provider charge.
- **Hosting, Redis/MongoDB, email, media/proctoring and storage:** depend on actual
  deployment and usage. They are not measured by this API connectivity check.
- **Taxes, card/foreign-exchange fees, additional datasets/tests, large stdin,
  paid reruns and provider-specific charging rules** can increase the cost.

For a brand-new question set using the four-language validation example, setup
plus one final candidate grading is approximately **INR 11.62 in OneCompiler
credits alone**, before practice runs and the other services above. Once that
set is validated and reused, the example's incremental final grading estimate
is INR 2.21 per candidate.

The documented execution response does not establish a per-request debit field.
The integration keeps estimated credits separate from actual-credit unknowns
and remaining-balance snapshots. **An exact all-in rupee cost cannot be claimed
without actual provider billing and infrastructure/AI usage data.**

Source checked for advertised credit tiers, batching and large-stdin charging:
[OneCompiler code execution API](https://onecompiler.com/apis/code-execution).
