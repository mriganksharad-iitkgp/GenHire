"""
Credit lifecycle for interviews: charge at start, refund when the interview
never actually happened.

Refund policy
-------------
Credits are debited when an interview starts (recruiter wallet for real
interviews, candidate wallet for practice). The charge is REVERSED — always
idempotently — when the session produces zero substantive answers:

  * session creation failed right after the debit,
  * the candidate was blocked by identity verification,
  * the candidate abandoned the tab / browser crashed before answering,
  * /end was called without a single non-empty answer.

Once at least one real (non-empty) answer exists the charge stands. A stale
real-interview session that still has its in-memory state and real answers is
auto-FINALIZED into a normal scored report instead of refunded — the recruiter
paid for a screening signal and gets one.

Idempotency & retries
---------------------
Every refund uses ``refund:<original-debit-key>`` as its idempotency key, so
sweeper passes and /end retries can never double-refund. Each real-interview
refund also increments ``interview_refund_count`` on the application; the next
/start derives a FRESH debit key from that counter (``...:r<n>``), because
replaying the original key after a refund would return the old transaction and
the retry would never actually be charged.
"""

import datetime
import logging
import os
import threading
import time
from typing import Any, Dict, Optional

from bson import ObjectId

from payment_module.services.wallet_service import WalletService

logger = logging.getLogger(__name__)


def get_abandon_ttl_minutes() -> int:
    try:
        return max(15, int(os.getenv("INTERVIEW_ABANDON_TTL_MINUTES", "120")))
    except ValueError:
        return 120


def get_sweep_interval_minutes() -> int:
    try:
        return max(5, int(os.getenv("INTERVIEW_REFUND_SWEEP_INTERVAL_MINUTES", "15")))
    except ValueError:
        return 15


def real_interview_debit_key(application_id: str, refund_count: int) -> str:
    """Debit idempotency key for a real interview start.

    The base key keeps historical behavior (retrying /start for the same
    application never double-charges). After a refund the counter changes the
    key so the next genuine attempt is charged again.
    """
    base = f"real-interview:{application_id}"
    return base if int(refund_count or 0) <= 0 else f"{base}:r{int(refund_count)}"


def count_answered_questions(session, fallback_doc: Optional[Dict[str, Any]] = None) -> int:
    """Number of substantive (non-empty) answers for a session.

    Prefers the in-memory session's interview_data; falls back to the
    ``questions_answered_count`` persisted on the interview document so a
    server restart doesn't misread a genuinely-answered interview as empty.
    """
    in_memory = 0
    if session is not None and getattr(session, "interview_data", None):
        in_memory = sum(
            1
            for qa in session.interview_data
            if str((qa or {}).get("answer") or "").strip()
        )
    persisted = int((fallback_doc or {}).get("questions_answered_count") or 0)
    return max(in_memory, persisted)


def _credits_from_deduction(deduction: Optional[Dict[str, Any]]) -> int:
    txn = (deduction or {}).get("transaction") or {}
    try:
        return abs(int(txn.get("delta_credits") or 0))
    except (TypeError, ValueError):
        return 0


def refund_recruiter_debit(
    db,
    applications_collection,
    *,
    application_id: str,
    recruiter_id: str,
    deduction: Optional[Dict[str, Any]],
    debit_key: Optional[str],
    session_id: Optional[str],
    reason: str,
) -> Optional[Dict[str, Any]]:
    """Reverse a real-interview recruiter debit. Returns the wallet result, or
    None when there is nothing refundable."""
    credits = _credits_from_deduction(deduction)
    if credits <= 0 or not recruiter_id or not application_id:
        return None
    if not (deduction or {}).get("success"):
        return None

    debit_key = debit_key or f"real-interview:{application_id}"
    result = WalletService(db).credit_wallet(
        owner_id=str(recruiter_id),
        audience="recruiter",
        credits=credits,
        transaction_type="real_interview_refund",
        reference_type="application",
        reference_id=str(application_id),
        metadata={
            "reason": reason,
            "session_id": session_id,
            "refunded_debit_key": debit_key,
        },
        idempotency_key=f"refund:{debit_key}",
    )

    # Bump the application's refund counter exactly once per actual refund so
    # the NEXT start attempt derives a fresh debit key and is charged again.
    if result.get("success") and not result.get("idempotent_replay"):
        try:
            applications_collection.update_one(
                {"_id": ObjectId(str(application_id))},
                {
                    "$inc": {"interview_refund_count": 1},
                    "$set": {"updated_at": datetime.datetime.utcnow()},
                },
            )
        except Exception:
            logger.warning(
                "Refund succeeded but interview_refund_count bump failed for application %s",
                application_id,
                exc_info=True,
            )
        logger.info(
            "[interview-credits] refunded %s credits to recruiter %s for application %s (%s)",
            credits,
            recruiter_id,
            application_id,
            reason,
        )
    return result


def refund_practice_debit(
    db,
    practice_doc: Dict[str, Any],
    *,
    reason: str,
) -> Optional[Dict[str, Any]]:
    """Reverse a practice-session candidate debit. Practice debit keys are
    per-session, so no attempt counter is needed."""
    deduction = practice_doc.get("usage_deduction")
    credits = _credits_from_deduction(deduction)
    user_id = practice_doc.get("user_id")
    session_id = practice_doc.get("session_id")
    if credits <= 0 or not user_id or not session_id:
        return None
    if not (deduction or {}).get("success"):
        return None

    debit_key = f"practice-session:{session_id}"
    result = WalletService(db).credit_wallet(
        owner_id=str(user_id),
        audience="candidate",
        credits=credits,
        transaction_type="practice_interview_refund",
        reference_type="practice_session",
        reference_id=str(session_id),
        metadata={"reason": reason, "refunded_debit_key": debit_key},
        idempotency_key=f"refund:{debit_key}",
    )
    if result.get("success") and not result.get("idempotent_replay"):
        logger.info(
            "[interview-credits] refunded %s practice credits to candidate %s for session %s (%s)",
            credits,
            user_id,
            session_id,
            reason,
        )
    return result


def refund_stale_real_interview(collections, doc: Dict[str, Any], *, reason: str):
    """Refund + mark a real interview document as abandoned."""
    db = collections["users"].database
    now = datetime.datetime.utcnow()
    refund = refund_recruiter_debit(
        db,
        collections["applications"],
        application_id=doc.get("application_id"),
        recruiter_id=doc.get("recruiter_id"),
        deduction=doc.get("usage_deduction"),
        debit_key=doc.get("debit_idempotency_key"),
        session_id=doc.get("session_id"),
        reason=reason,
    )
    collections["interviews"].update_one(
        {"_id": doc["_id"]},
        {
            "$set": {
                "status": "abandoned",
                "abandoned_reason": reason,
                "credits_refund": refund,
                "updated_at": now,
            }
        },
    )
    return refund


def finalize_stale_real_interview(collections, interview_manager, doc, session) -> bool:
    """Score an abandoned-but-substantive real interview from its in-memory
    state so the recruiter still gets a report (no refund — the screening
    signal was delivered). Light version of /end: no emails, no gaze plots."""
    interviews = collections["interviews"]
    applications = collections["applications"]
    jobs = collections["jobs"]
    now = datetime.datetime.utcnow()

    try:
        session.is_complete = True
        final_evaluation = interview_manager._generate_final_evaluation(session)
    except Exception as exc:
        logger.error(
            "[interview-credits] auto-finalize evaluation failed for %s: %s",
            doc.get("session_id"),
            exc,
            exc_info=True,
        )
        final_evaluation = {"error": "Failed to generate AI evaluation.", "final_score": 0}

    qs = (final_evaluation or {}).get("quantitative_scores", {})
    answer_score = qs.get("answer_score")
    language_score = qs.get("language_score")
    if answer_score is not None or language_score is not None:
        interview_score = round(
            (float(answer_score or 0) * 0.7 + float(language_score or 0) * 0.3) * 100
        )
    else:
        interview_score = int(final_evaluation.get("final_score") or 0)

    transcript = []
    for qa in getattr(session, "interview_data", []) or []:
        if qa.get("question"):
            transcript.append({"role": "assistant", "text": qa.get("question", "")})
        if qa.get("answer"):
            transcript.append(
                {
                    "role": "user",
                    "text": qa.get("answer", ""),
                    "ai_probability": (qa.get("evaluation") or {}).get("ai_probability"),
                }
            )

    proctoring_score = doc.get("proctoring_score")
    proctoring_status = "complete" if isinstance(proctoring_score, (int, float)) else "incomplete"

    interviews.update_one(
        {"_id": doc["_id"]},
        {
            "$set": {
                "status": "completed",
                "evaluation": final_evaluation,
                "final_score": interview_score,
                "proctoring_status": proctoring_status,
                "transcript": transcript,
                "auto_finalized": True,
                "auto_finalized_reason": "abandoned_with_answers",
                "updated_at": now,
            }
        },
    )

    application_id = doc.get("application_id")
    if application_id:
        try:
            existing_app = applications.find_one({"_id": ObjectId(str(application_id))})
            if existing_app:
                previous_status = str(existing_app.get("status", "pending")).lower()
                applications.update_one(
                    {"_id": existing_app["_id"]},
                    {
                        "$set": {
                            "interview_score": interview_score,
                            "proctoring_score": proctoring_score,
                            "proctoring_status": proctoring_status,
                            "status": "interviewed",
                            "updated_at": now,
                        }
                    },
                )
                # Keep recruiter job-card counters in sync, mirroring /end.
                status_counters = [
                    "pending",
                    "interviewed",
                    "screening_cleared",
                    "selected",  # legacy counter field on unmigrated job docs
                    "rejected",
                ]
                counter_update = {}
                if previous_status in status_counters and previous_status != "interviewed":
                    counter_update[previous_status] = -1
                if previous_status != "interviewed":
                    counter_update["interviewed"] = counter_update.get("interviewed", 0) + 1
                if counter_update:
                    jobs.update_one(
                        {"_id": ObjectId(str(existing_app["job_id"]))},
                        {"$inc": counter_update},
                    )
        except Exception:
            logger.error(
                "[interview-credits] auto-finalize application update failed for %s",
                application_id,
                exc_info=True,
            )

    logger.info(
        "[interview-credits] auto-finalized stale interview %s (score=%s)",
        doc.get("session_id"),
        interview_score,
    )
    return True


def run_refund_sweep_once(collections, interview_manager) -> Dict[str, int]:
    """One sweep over stale sessions. Safe to call repeatedly (idempotent)."""
    db = collections["users"].database
    ttl_minutes = get_abandon_ttl_minutes()
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(minutes=ttl_minutes)

    stats = {
        "real_finalized": 0,
        "real_refunded": 0,
        "practice_refunded": 0,
        "practice_closed": 0,
    }

    # --- Real interviews stuck in a non-terminal state past the TTL ---
    stale_real = collections["interviews"].find(
        {
            "status": {"$in": ["active", "identity_blocked"]},
            "created_at": {"$lt": cutoff},
        }
    )
    for doc in stale_real:
        try:
            session = interview_manager.sessions.get(doc.get("session_id"))
            answered = count_answered_questions(session, doc)
            if session is not None and answered > 0:
                finalize_stale_real_interview(collections, interview_manager, doc, session)
                stats["real_finalized"] += 1
            else:
                reason = (
                    "identity_blocked"
                    if doc.get("status") == "identity_blocked"
                    else "abandoned_no_answers"
                )
                refund_stale_real_interview(collections, doc, reason=reason)
                stats["real_refunded"] += 1
            # Drop finished/abandoned sessions from memory either way.
            interview_manager.sessions.pop(doc.get("session_id"), None)
        except Exception:
            logger.error(
                "[interview-credits] sweep failed for interview %s",
                doc.get("session_id"),
                exc_info=True,
            )

    # --- Practice sessions ---
    stale_practice = collections["practice_sessions"].find(
        {"status": "active", "created_at": {"$lt": cutoff}}
    )
    for doc in stale_practice:
        try:
            answered = sum(
                1
                for qa in (doc.get("qa_pairs") or [])
                if str((qa or {}).get("answer") or "").strip()
            )
            now = datetime.datetime.utcnow()
            if answered > 0:
                # Substantive practice that was never ended: close it without a
                # refund (the LLM session was consumed); per-answer feedback is
                # already stored on the doc.
                collections["practice_sessions"].update_one(
                    {"_id": doc["_id"]},
                    {
                        "$set": {
                            "status": "abandoned",
                            "abandoned_reason": "abandoned_with_answers",
                            "updated_at": now,
                        }
                    },
                )
                stats["practice_closed"] += 1
            else:
                refund = refund_practice_debit(db, doc, reason="abandoned_no_answers")
                collections["practice_sessions"].update_one(
                    {"_id": doc["_id"]},
                    {
                        "$set": {
                            "status": "abandoned",
                            "abandoned_reason": "abandoned_no_answers",
                            "credits_refund": refund,
                            "updated_at": now,
                        }
                    },
                )
                stats["practice_refunded"] += 1
        except Exception:
            logger.error(
                "[interview-credits] sweep failed for practice session %s",
                doc.get("session_id"),
                exc_info=True,
            )

    if any(stats.values()):
        logger.info("[interview-credits] sweep complete: %s", stats)
    return stats


class InterviewRefundSweeper:
    """Daemon thread running run_refund_sweep_once on an interval — same
    pattern as services/invite_cleanup_scheduler.py."""

    def __init__(self, collections, interview_manager):
        self.collections = collections
        self.interview_manager = interview_manager
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            logger.warning("[interview-credits] sweeper already running")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info(
            "[interview-credits] sweeper started (interval=%sm, ttl=%sm)",
            get_sweep_interval_minutes(),
            get_abandon_ttl_minutes(),
        )

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _run(self) -> None:
        # Brief boot delay so we don't compete with startup work.
        time.sleep(90)
        while not self._stop_event.is_set():
            try:
                run_refund_sweep_once(self.collections, self.interview_manager)
            except Exception as exc:
                logger.error("[interview-credits] sweep tick failed: %s", exc, exc_info=True)
            sleep_seconds = get_sweep_interval_minutes() * 60
            slept = 0
            while slept < sleep_seconds and not self._stop_event.is_set():
                time.sleep(30)
                slept += 30


_sweeper: Optional[InterviewRefundSweeper] = None


def get_interview_refund_sweeper(collections, interview_manager) -> InterviewRefundSweeper:
    global _sweeper
    if _sweeper is None:
        _sweeper = InterviewRefundSweeper(collections, interview_manager)
    return _sweeper
