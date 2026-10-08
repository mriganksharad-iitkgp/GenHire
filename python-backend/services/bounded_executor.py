"""Bound best-effort application notifications; never spawn a thread per applicant."""
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from middleware.rate_limiter import env_int

logger = logging.getLogger(__name__)
_pool = None
_slots = None
_init_lock = threading.Lock()


def submit_notification(func, *args):
    global _pool, _slots
    with _init_lock:
        if _pool is None:
            workers = env_int('NOTIFICATION_WORKERS', 4)
            _pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix='notification')
            _slots = threading.BoundedSemaphore(workers + env_int('NOTIFICATION_QUEUE_SIZE', 128))
    if not _slots.acquire(blocking=False):
        logger.warning('Notification capacity reached; application remains saved')
        return False

    def send():
        try:
            func(*args)
        except Exception:
            logger.warning('Application notification failed', exc_info=True)
        finally:
            _slots.release()
    try:
        _pool.submit(send)
    except Exception:
        _slots.release()
        logger.warning('Notification dispatch unavailable')
        return False
    return True

_invite_slots = None


class InvitePermit:
    def __init__(self, slots):
        self.slots = slots
        self.transferred = False
        self.released = False
        self.lock = threading.Lock()

    def release(self):
        with self.lock:
            if not self.released:
                self.released = True
                self.slots.release()

    def dispatch(self, func, *args):
        self.transferred = True
        def run():
            try:
                func(*args)
            finally:
                self.release()
        try:
            threading.Thread(target=run, daemon=True, name='invite-dispatch').start()
        except Exception:
            self.release()
            raise


def reserve_invite_dispatch():
    global _invite_slots
    with _init_lock:
        if _invite_slots is None:
            _invite_slots = threading.BoundedSemaphore(env_int('INVITE_BACKGROUND_MAX_INFLIGHT', 2, maximum=32))
    return InvitePermit(_invite_slots) if _invite_slots.acquire(blocking=False) else None
