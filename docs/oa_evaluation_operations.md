# OA evaluation operations

Coding and SQL execution use the backend OnlineCompiler.io adapter. See
[configuration, live acceptance and resource retirement](../OA_FINAL_SETUP.md).
The migration updates all four backend environment profiles; deployment and live
acceptance remain separate. Synthetic tests cannot enable production cohorts.

## Configuration and workers

`OA_MAX_CONCURRENT_EXECUTIONS` controls distributed active slots (default 2,
range 1-100). `GENHIRE_OA_EXECUTION_QUEUE_LIMIT` retains its 1000 default and
1-5000 range. `GENHIRE_OA_GRADING_CASE_LIMIT` bounds grading fixtures per attempt.
`OA_MAX_PRACTICE_RUNS_PER_QUESTION` defaults to 10 public runs per question.
`OA_EXECUTION_TIMEOUT_MS` defaults to a 30000 ms provider HTTP timeout.

Existing workflow, evaluation, security and integrity acceptance requirements
remain in force. SQL additionally requires unexpired live `sql_verified`
acceptance. After reviewing the intended environment, supervise these backend
workers (each supports `--once`):

```powershell
python scripts/workers/assessment_runtime_worker.py
python scripts/workers/assessment_evaluation_worker.py
```

Web handlers enqueue work. Mongo admission and fencing preserve global capacity
across workers. Provider calls run outside transactions. Journals, accepted
submissions, deadlines and wallet reservations remain durable across restarts.

## States and reconciliation

Tasks move from queued to dispatching, then running to complete. A pre-dispatch
configuration failure blocks without a paid call. An ambiguous paid POST becomes
`dispatch_unknown`, retains its identity and slot, and is never retried
automatically. Provider operation/API errors do not create a candidate zero.

The existing administrator-only operations and reconciliation APIs remain:

| Route | Purpose |
| --- | --- |
| `GET /api/assessment-evaluation-operations` | Queue/capacity state and OnlineCompiler.io usage aggregates by purpose, language, hidden/public status and request state. Unknown execution outcome counts are explicit. |
| `POST /api/assessment-executions/:id/reconcile` | Authorized admin action with a stable operation key and reason. |
| `GET /api/assessment-attempts/:id/evaluation` | Scoped report/status; recruitment results remain withheld from candidates until release. |
| `POST /api/assessment-attempts/:id/platform-failure` | Verified administrator platform-failure settlement; cannot undo a usable captured evaluation. |

`bind_provider` can bind only the original task's completed OnlineCompiler.io journal;
it cannot bind an arbitrary external submission. `resume_poll` retries local
journal collection without a POST. `retry_confirmed` remains limited to known
pre-dispatch blocks or completed infrastructure failures with no held slot,
at most twice. It cannot retry an ambiguous POST or a candidate wrong answer.
OnlineCompiler.io has no documented lost-response lookup: retain unknown outcomes for
provider/operator reconciliation instead of guessing a result or debit.

Never export hidden outputs, seeds, sources, private diagnostics or credentials
in logs/tickets. Candidate-visible diagnostics come only from public runs and
are bounded/redacted. A new account/profile invalidates previous attestations.

## Scoring, release and billing

MCQs use exact sets for multiple correct answers, no negative marks, and the saved question marks. Unanswered finalized questions are zero. Coding partial credit uses only hidden test weights for the selected language. SQL uses all explicitly weighted validated datasets, including samples. Section percentage is earned/possible; overall percentage uses the saved section weights. Decimal arithmetic avoids accumulating floating-point rounding errors; display values round to four decimal places. Infrastructure-ungraded questions keep the overall score unavailable.

A private report records the objective threshold recommendation. It does not establish proctoring clearance, publish candidate results, advance company stages or automatically reject a candidate. Canonical OA completion remains pending recruiter release; Step 7 supplies integrity evidence and Step 8 supplies release/advancement controls.

A usable finalized evaluation captures the original recruiter reservation in the same transaction as the report, attempt/submission state and canonical stage event. Unanswered/wrong/compile/time/memory/output-limit answers are usable grading outcomes and are not platform refunds. Exhausted confirmed infrastructure failure returns the reservation and records no final score. Ambiguous/pending execution keeps the hold until recovery or a reasoned administrator platform-failure action. Candidate withdrawal does not manufacture a technical refund. Existing general billing refund primitives remain available to financial operations; this milestone does not expose a new post-capture customer refund policy.

## Monitoring and migration

Monitor queue age, global slots, unknown dispatches, review flags, usage estimates,
unknown execution outcomes, vendor console balances, evaluation latency and
report-versus-ledger settlement. Remaining-balance snapshots are not actual
per-request credit debits. No fixed USD purchase-tier price is used for scoring.

Drain and reconcile old provider work before deploying. Existing public jobs
without the current execution-task identity are marked for retired-provider
review and never resubmitted. Retain all journals and database history. Stopping
new starts must preserve accepted saves/deadlines and settlement workers.
The migration removes repository SQL workers/provisioning; cloud resource
retirement still requires an explicit inventory and approved deletion plan.
