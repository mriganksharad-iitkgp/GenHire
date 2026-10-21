"""Read-only workflow/ledger reconciliation. Never repairs or changes records."""
import argparse
import json
from pathlib import Path
import sys
from bson import ObjectId
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def audit(db, job_id=None, owner_id=None, audience='recruiter'):
    report = {'workflow_issues': [], 'billing_issues': [], 'applications_checked': 0, 'wallets_checked': 0}
    if job_id:
        if not ObjectId.is_valid(job_id):
            raise ValueError('Invalid job ID.')
        for app in db.applications.find({'job_id': job_id, 'workflow_version_id': {'$type': 'string', '$ne': ''}}):
            report['applications_checked'] += 1
            sid = str(app['_id'])
            workflow = app['workflow']
            views = {s['stage_id']: s for s in db.application_stages.find({'application_id': sid})}
            for stage in workflow['stages']:
                view = views.get(stage['stage_id'], {})
                if view.get('revision') != workflow['revision'] or any(view.get(k) != v for k, v in stage.items()):
                    report['workflow_issues'].append({'application_id': sid, 'issue': 'stage_projection_mismatch', 'stage_id': stage['stage_id']})
            revisions = [e['revision'] for e in db.stage_events.find({'application_id': sid}, {'revision': 1}).sort('revision', 1)]
            if revisions != list(range(workflow['revision'] + 1)):
                report['workflow_issues'].append({'application_id': sid, 'issue': 'event_revision_gap'})
    if owner_id:
        if audience not in {'candidate', 'recruiter'}:
            raise ValueError('Invalid audience.')
        identity = {'owner_id': str(owner_id), 'audience': audience}
        wallet = db.credit_wallets.find_one(identity)
        if wallet:
            report['wallets_checked'] += 1
            ledger_balance = sum(t.get('delta_credits', 0) for t in db.credit_transactions.find(identity, {'delta_credits': 1}))
            reserved = sum(op['credits'] for op in db.billing_operations.find(dict(identity, state='reserved'), {'credits': 1}))
            if ledger_balance != wallet['balance']:
                report['billing_issues'].append({'issue': 'ledger_balance_mismatch', 'wallet_balance': wallet['balance'], 'ledger_balance': ledger_balance})
            if reserved != wallet.get('reserved_credits', 0):
                report['billing_issues'].append({'issue': 'reservation_mismatch', 'wallet_reserved': wallet.get('reserved_credits', 0), 'operation_reserved': reserved})
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job-id')
    parser.add_argument('--owner-id')
    parser.add_argument('--audience', choices=['candidate', 'recruiter'], default='recruiter')
    args = parser.parse_args()
    if not (args.job_id or args.owner_id):
        parser.error('Scope the read-only audit with --job-id and/or --owner-id')
    from config.database import db_config
    from pymongo import MongoClient
    client = MongoClient(db_config.uri)
    try:
        print(json.dumps(audit(client[db_config.database_name], args.job_id, args.owner_id, args.audience), indent=2))
    finally:
        client.close()


if __name__ == '__main__':
    main()
