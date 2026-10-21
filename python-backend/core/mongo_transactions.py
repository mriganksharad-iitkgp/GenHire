"""Atomic domain writes. Never fall back to separate writes on unsupported MongoDB."""
from pymongo.errors import ConfigurationError, OperationFailure
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern
import random
import time


class AtomicityUnavailable(RuntimeError):
    pass


def atomic(db, callback, contention_backoff=False):
    """PyMongo retries transient transactions/unknown commits, not external side effects.

    Callbacks must contain database work only and may run multiple times. A replica
    set or mongos is required. Standalone servers fail closed before partial writes.
    """
    attempts = 0
    def invoke(session):
        nonlocal attempts
        # with_transaction has already aborted the previous attempt before
        # invoking this callback again. Wait before the first DB operation so
        # no server-side transaction/locks are held during the jitter. PyMongo
        # retains authority over retry labels, ambiguous commits and its deadline.
        if contention_backoff and attempts:
            time.sleep(random.uniform(0, min(.5, .01 * (2 ** min(attempts-1, 6)))))
        attempts += 1
        return callback(session)
    try:
        with db.client.start_session() as session:
            return session.with_transaction(
                invoke, read_concern=ReadConcern('snapshot'),
                write_concern=WriteConcern('majority'), max_commit_time_ms=10000,
            )
    except (ConfigurationError, NotImplementedError) as exc:
        raise AtomicityUnavailable('Atomic writes require MongoDB transaction support.') from exc
    except OperationFailure as exc:
        if exc.code in {20, 303}:
            raise AtomicityUnavailable('Atomic writes require a MongoDB replica set or mongos.') from exc
        raise
