"""Daemon thread that purges dormant invite-only (burner) accounts.

An account is eligible for deletion when ALL of these are true:
  - is_invite_only == True
  - temp_password_set_at is older than the cutoff (default: 30 days ago)
  - last_redeemed_at is None (the user never set their own password)
  - The user has no application carrying a real CV (cv_snapshot is None)
    -- so anyone who actually engaged with a job survives.

When eligible, we cascade-delete the user's applications and invite_tokens,
then the user document itself.

Scheduling is intentionally simple: a daemon thread that sleeps in short
intervals and runs the purge once per INVITE_CLEANUP_INTERVAL_HOURS. This
mirrors the existing services/background_processor.py pattern.
"""

import datetime as _dt
import logging
import os
import threading
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def run_cleanup_once(db_collections: Dict[str, Any], *, max_age_days: int = 30) -> Dict[str, int]:
    """Run a single cleanup pass. Returns a stats dict.

    Safe to call from a CLI as well as the daemon.
    """
    users = db_collections["users"]
    applications = db_collections["applications"]
    _invite_tokens_col = db_collections.get("invite_tokens")
    invite_tokens = _invite_tokens_col if _invite_tokens_col is not None else users.database["invite_tokens"]

    cutoff = _dt.datetime.utcnow() - _dt.timedelta(days=max_age_days)

    candidate_query = {
        "is_invite_only": True,
        "temp_password_set_at": {"$lt": cutoff},
        "$or": [
            {"last_redeemed_at": None},
            {"last_redeemed_at": {"$exists": False}},
        ],
    }

    deleted_users = 0
    deleted_apps = 0
    deleted_tokens = 0
    skipped_engaged = 0

    for user in users.find(candidate_query):
        user_id_str = str(user["_id"])
        try:
            # Engagement exemption: skip users whose applications hold a real CV.
            engaged = applications.find_one(
                {
                    "student_id": user_id_str,
                    "cv_snapshot": {"$ne": None},
                }
            )
            if engaged:
                skipped_engaged += 1
                continue

            apps_result = applications.delete_many({"student_id": user_id_str})
            tokens_result = invite_tokens.delete_many({"user_id": user["_id"]})
            users.delete_one({"_id": user["_id"]})

            deleted_users += 1
            deleted_apps += apps_result.deleted_count or 0
            deleted_tokens += tokens_result.deleted_count or 0
        except Exception as e:
            logger.error(
                f"[invite-cleanup] failed to delete user {user_id_str}: {e}",
                exc_info=True,
            )

    stats = {
        "deleted_users": deleted_users,
        "deleted_applications": deleted_apps,
        "deleted_tokens": deleted_tokens,
        "skipped_engaged": skipped_engaged,
        "cutoff_iso": cutoff.isoformat(),
    }
    logger.info(f"[invite-cleanup] pass complete: {stats}")
    return stats


class InviteCleanupScheduler:
    def __init__(self, db_collections: Dict[str, Any]):
        self.db_collections = db_collections
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        try:
            self.interval_hours = max(1, int(os.getenv("INVITE_CLEANUP_INTERVAL_HOURS", "24")))
        except ValueError:
            self.interval_hours = 24

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            logger.warning("[invite-cleanup] scheduler already running")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info(
            f"[invite-cleanup] scheduler started (interval={self.interval_hours}h)"
        )

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _run(self) -> None:
        # On boot, wait briefly so we don't compete with other startup work.
        time.sleep(60)
        sleep_seconds = self.interval_hours * 3600
        while not self._stop_event.is_set():
            try:
                run_cleanup_once(self.db_collections)
            except Exception as e:
                logger.error(f"[invite-cleanup] tick failed: {e}", exc_info=True)
            # Sleep in 60s slices so stop() is responsive.
            slept = 0
            while slept < sleep_seconds and not self._stop_event.is_set():
                time.sleep(60)
                slept += 60


_scheduler: Optional[InviteCleanupScheduler] = None


def get_invite_cleanup_scheduler(db_collections: Dict[str, Any]) -> InviteCleanupScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = InviteCleanupScheduler(db_collections)
    return _scheduler
