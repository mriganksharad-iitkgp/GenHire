"""Read-only by default. Explicit owner-authorized, checkpointable pilot adoption.

python scripts/migrations/migrate_hiring_workflows.py --job-id ID
Add --apply --actor-id VERIFIED_OWNER_ID only after reviewing the dry-run report.
No invented historical transitions, OA invitations, charges, or job deadline edits.
"""
import argparse
import json
from pathlib import Path
import sys
from bson import ObjectId

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from models.hiring_workflow import screening_only, WorkflowError
from services.workflow_service import WorkflowService
from repositories.workflow_repository import ensure_workflow_indexes


def migrate(db, job_id, apply=False, actor=None, after_id=None, limit=500):
    if not ObjectId.is_valid(job_id) or (after_id and not ObjectId.is_valid(after_id)):
        raise ValueError('A valid job ID/checkpoint is required.')
    if type(limit) is not int or not 1 <= limit <= 5000:
        raise ValueError('Limit must be from 1 to 5000.')
    job = db.jobs.find_one({'_id': ObjectId(job_id)})
    if not job:
        raise ValueError('Job not found.')
    service = WorkflowService(db)
    version = db.hiring_workflow_versions.find_one({'_id': ObjectId(job['workflow_version_id'])}) if job.get('workflow_version_id') else None
    if version is None:
        version = {'stages': screening_only()}
    if apply:
        service.require_enabled()
        service.job(job_id, actor or {}, write=True)
        ensure_workflow_indexes(db)
        if '_id' not in version:
            published = service.publish_version(job_id, actor, version['stages'], job.get('workflow_revision', 0), 'migration:screening-only:v1')
            version = db.hiring_workflow_versions.find_one({'_id': ObjectId(published['version_id'])})
    query = {'job_id': job_id}
    if after_id:
        query['_id'] = {'$gt': ObjectId(after_id)}
    report = {'mode': 'apply' if apply else 'dry_run', 'job_id': job_id, 'counts': {}, 'applications': [], 'next_after_id': after_id}
    for app in db.applications.find(query).sort('_id', 1).limit(limit):
        _, problem = service.adoption_preview(app, version)
        status = problem or 'eligible'
        if apply and not problem:
            try:
                service.adopt(str(app['_id']), actor, str(version['_id']), 'migration:application:v1')
                status = 'adopted'
            except WorkflowError as exc:
                status = exc.code
        report['counts'][status] = report['counts'].get(status, 0) + 1
        report['applications'].append({'id': str(app['_id']), 'classification': status})
        report['next_after_id'] = str(app['_id'])
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job-id', required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--actor-id')
    parser.add_argument('--after-id')
    parser.add_argument('--limit', type=int, default=500)
    args = parser.parse_args()
    if args.apply and (not args.actor_id or not ObjectId.is_valid(args.actor_id)):
        parser.error('--apply requires --actor-id for the verified job owner or authorized admin')
    from config.database import db_config
    # Avoid application startup/background jobs and its index-maintenance writes
    # for a dry run. Direct connection reads only; apply explicitly ensures indexes.
    from config.env_loader import load_environment
    from pymongo import MongoClient
    load_environment(require_database=True)
    client = MongoClient(db_config.uri)
    try:
        db = client[db_config.database_name]
        actor = db.users.find_one({'_id': ObjectId(args.actor_id)}) if args.actor_id else None
        print(json.dumps(migrate(db, args.job_id, args.apply, actor, args.after_id, args.limit), indent=2))
    finally:
        client.close()


if __name__ == '__main__':
    main()
