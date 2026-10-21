# Authored OA template validation - 21 October 2026

These results cover repository-authored starter content only. They do not grant
managed execution/security acceptance or publish an assessment.

## Template contents

| Role preset | Complete question set |
| --- | --- |
| SDE | 3 coding + 20 MCQ |
| Frontend, backend, full stack | 2 coding + 20 MCQ |
| Data Analyst | 2 SQL + 20 MCQ |
| Data Science / ML | 2 coding + 1 SQL + 20 MCQ |
| DevOps / SRE | 1 coding + 25 MCQ |
| QA | 1 coding + 20 MCQ |
| Product, Business Analyst, Security, Finance | 25 MCQ |
| UX, Marketing, Sales, HR, Customer Support | 20 MCQ |

Actual private content lives in `python-backend/services/role_assessment_templates.py`.
Frontend templates contain role metadata only. Each preset exactly matches its
section counts, per-question marks and difficulty distribution. Every coding task
uses 16 cases; SQL uses six independent disposable fixtures per question. Questions
are reusable starters and should be reviewed for the actual position and candidate
level. The preset difficulty slots are editorial labels, not empirical calibration.

## Trusted local program checks

Command from repository root:

```powershell
python-backend/venv/Scripts/python.exe python-backend/scripts/dev/verify_role_template_programs.py
```

The script executes only trusted repository-authored code in `.tmp`, never candidate
submissions or an AI-generated program. It makes no Sphere/GCP requests. The current
machine used Python 3.12.10, Node.js 24.20.0 and GCC 16.2.0 with C++20 and `-O2`.
Node 24 is a local correctness check, not proof of the approved Node 22 runtime.

| Coding starter | Python reference | JS reference | C++ reference | Native naive baseline |
| --- | --- | --- | --- | --- |
| Sum of the first N integers (easy) | 16/16 | 16/16 | 16/16 | Not performance-filtered |
| Count divisible identifiers (medium) | 16/16 | 16/16 | 16/16 | 6/16; 10 timed out |
| Sum periodic remainders (medium) | 16/16 | 16/16 | 16/16 | 6/16; 10 timed out |
| Count all set bits (hard slot) | 16/16 | 16/16 | 16/16 | 6/16; 10 timed out |

All 192 reference case executions matched expected outputs. Each naive baseline
uses direct O(N) enumeration; all 48 baseline executions were checked with a
one-second per-case process timeout. Six small cases complete and the ten large
cases time out for each of the three tasks. Local process timeout includes process
startup, unlike judge CPU timing. These results cannot guarantee a pass limit for
every program, runtime, hardware, alternative algorithm or hardcoded solution.
The reproducible raw report is `.tmp/role-template-verification/report.json`.

Small-case expected values are also checked with independent enumeration in unit
tests. The SQL queries match the expected columns and rows for all 12 fixtures
under SQLite's common SQL semantics. That is an additional oracle, not PostgreSQL
17 or MySQL 8.4 execution acceptance. MCQs and wording need recruiter review.

## Remaining real-provider checks

- Run every allowed reference language through the configured Sphere validator.
  Java 21 was not installed locally; the four-language source still requires its
  real pinned-runtime execution checks. Confirm Python 3.12, Node 22 and C++20 too.
- Re-run the known naive baselines on the managed runtime and confirm the desired
  six-case limit under provider timing before treating it as a performance gate.
- Validate each SQL question on isolated PostgreSQL 17/MySQL 8.4 Cloud Run fixtures.
- Review answers, role relevance, constraints, examples, resource limits and difficulty;
  approve each validated question and then explicitly publish the assessment.

New AI requests require 15-20 cases and request large adversarial cases targeting
naive algorithms. Generated problems still require independent semantic review
and actual execution; the prompt is not benchmark evidence.
