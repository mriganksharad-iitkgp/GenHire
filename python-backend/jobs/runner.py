"""Background job lifecycle.

Owns starting/stopping the three long-lived daemon workers that app.py used
to start inline at import time:

- background processor  — async CV scoring queue
- invite cleanup        — purges dormant burner accounts
- refund sweeper        — refunds/finalizes abandoned interview credit debits

start_all() honors GENHIRE_DISABLE_JOBS=1 (set by tooling such as
scripts/route_manifest.py) so importing the app for inspection doesn't spawn
worker threads. Note: with a single Gunicorn worker these are in-process
threads; they do not scale across multiple workers/containers.
"""

import logging

from core import config

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
_ch = logging.StreamHandler()
_ch.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(_ch)

_handles = {}


def start_all(collections, interview_manager):
    """Start every background worker; returns the handle dict."""
    if config.jobs_disabled():
        logger.info("[jobs] GENHIRE_DISABLE_JOBS=1 — background workers not started")
        return _handles

    from services.background_processor import get_background_processor
    from services.invite_cleanup_scheduler import get_invite_cleanup_scheduler
    from services import interview_credit_service

    background_processor = get_background_processor()
    background_processor.start()
    logger.info("[OK] Background processor started for async CV scoring")

    invite_cleanup_scheduler = get_invite_cleanup_scheduler(collections)
    invite_cleanup_scheduler.start()
    logger.info("[OK] Invite cleanup scheduler started")

    interview_refund_sweeper = interview_credit_service.get_interview_refund_sweeper(
        collections, interview_manager
    )
    interview_refund_sweeper.start()
    logger.info("[OK] Interview credit-refund sweeper started")
    from services.interview_integrity_service import IntegrityWatchdog
    integrity_watchdog = IntegrityWatchdog(collections)
    integrity_watchdog.start()

    from jobs.oa_authoring import LocalAuthoringWorker, enabled as local_oa_enabled
    if local_oa_enabled() and not _handles.get('oa_authoring'):
        _handles['oa_authoring']=LocalAuthoringWorker(collections['jobs'].database)
        _handles['oa_authoring'].start()
        logger.info('[OK] Local OA authoring worker started (production uses the standalone worker)')

    _handles.update(
        background_processor=background_processor,
        invite_cleanup_scheduler=invite_cleanup_scheduler,
        interview_refund_sweeper=interview_refund_sweeper,
        integrity_watchdog=integrity_watchdog,
    )
    return _handles


def stop_all():
    """Stop every started worker (dev-server shutdown path)."""
    if _handles.get("oa_authoring"):
        _handles.pop("oa_authoring").stop()
    if _handles.get("integrity_watchdog"):
        _handles["integrity_watchdog"].stop()
    background_processor = _handles.get("background_processor")
    if background_processor is not None:
        logger.info("Shutting down background processor...")
        background_processor.stop()
        logger.info("Background processor stopped")
    try:
        invite_cleanup_scheduler = _handles.get("invite_cleanup_scheduler")
        if invite_cleanup_scheduler is not None:
            invite_cleanup_scheduler.stop()
            logger.info("Invite cleanup scheduler stopped")
    except Exception:
        pass
    try:
        interview_refund_sweeper = _handles.get("interview_refund_sweeper")
        if interview_refund_sweeper is not None:
            interview_refund_sweeper.stop()
            logger.info("Interview refund sweeper stopped")
    except Exception:
        pass
