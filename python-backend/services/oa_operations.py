"""Read-only aggregate operations snapshot. No answers, identities or credentials.

The snapshot is observational, not transactionally consistent across collections.
Run from an operator shell, never expose as an unauthenticated health endpoint.
"""
from datetime import datetime, timedelta, timezone


QUEUES = {
    'execution': 'assessment_execution_tasks',
    'evaluation': 'assessment_evaluation_jobs',
    'authoring_generation': 'assessment_generation_jobs',
    'practice_generation': 'practice_generation_jobs',
    'practice_feedback': 'practice_feedback_jobs',
    'notifications': 'hiring_outbox',
    'company_email': 'company_messages',
}


def snapshot(db, now=None):
    now = now or datetime.now(timezone.utc)
    result = {'observed_at': now.isoformat(), 'queues': {}, 'alerts': []}
    for label, name in QUEUES.items():
        counts = {str(row['_id']): row['count'] for row in db[name].aggregate([
            {'$group': {'_id': '$state', 'count': {'$sum': 1}}}], maxTimeMS=5000)}
        age_field = 'due_at' if label == 'notifications' else 'created_at'
        oldest = db[name].find_one({'state': 'queued', age_field: {'$type': 'date', '$lte': now}},
                                   {age_field: 1}, sort=[(age_field, 1)], max_time_ms=5000)
        age = None
        if oldest:
            created = oldest[age_field]
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            age = max(0, round((now-created).total_seconds()))
        result['queues'][label] = {'states': counts, 'oldest_queued_seconds': age}
        if counts.get('unknown', 0) or counts.get('dispatch_unknown', 0):
            result['alerts'].append(label+':ambiguous_external_call')
        if counts.get('blocked', 0) or counts.get('needs_review', 0):
            result['alerts'].append(label+':operator_review_required')
        stale = db[name].count_documents({'$or': [
            {'state': {'$in': ['dispatching', 'preparing', 'generating', 'validating']}, 'lease_until': {'$lt': now}},
            {'state': 'dispatching', 'dispatched_at': {'$lt': now-timedelta(minutes=5)}},
            {'state': 'dispatching', 'dispatch_started_at': {'$lt': now-timedelta(minutes=5)}}]}, maxTimeMS=5000)
        result['queues'][label]['expired_external_leases'] = stale
        if stale:
            result['alerts'].append(label+':expired_external_lease_do_not_blindly_retry')
        if age is not None and age > 300:
            result['alerts'].append(label+':queued_over_5m')
    capacity = db.assessment_execution_capacity.find_one({'_id': 'global'}) or {}
    queued = db.assessment_execution_capacity.find_one({'_id': 'queue'}) or {}
    held = db.assessment_execution_tasks.count_documents({'slot_held': True}, maxTimeMS=5000)
    actual_queue = result['queues']['execution']['states'].get('queued', 0)
    result['execution_capacity'] = {'active': capacity.get('active', 0), 'held_tasks': held,
                                    'queued_counter': queued.get('count', 0), 'queued_tasks': actual_queue}
    if held != capacity.get('active', 0) or actual_queue != queued.get('count', 0):
        result['alerts'].append('execution:capacity_counter_mismatch_recheck_before_repair')
    return result
