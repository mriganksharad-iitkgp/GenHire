"""
Backfill each job's denormalized `company`/`logo` from its owning recruiter.

Why this is needed:
    Job documents snapshot the recruiter's company details at create time, and
    the create path used to fall back to the literal placeholder
    "TechCorp Solutions" when the recruiter had not filled in a company name
    yet. Jobs created that way kept the placeholder forever — editing the
    company profile afterwards updated only the `users` document, so candidates
    saw a company that did not exist.

    The read paths now re-resolve these fields from the recruiter (see
    utils/company_resolver.py), so this migration is not required for correct
    display. It exists to clean the stored copies, which is what any future
    direct consumer of `jobs.company` will read.

Jobs owned by 'system' (legacy seed data) and jobs whose owner no longer exists
are left untouched — there is no recruiter to resolve them from.

Usage (run from python-backend/):
    python scripts/migrations/migrate_job_company_names.py --dry-run
    python scripts/migrations/migrate_job_company_names.py
"""

import argparse
import os
import sys

from bson import ObjectId
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config.database import db_config  # noqa: E402


def migrate(dry_run=False):
    collections = db_config.get_collections()
    jobs_collection = collections['jobs']
    users_collection = collections['users']

    jobs = list(jobs_collection.find({}, {'_id': 1, 'title': 1, 'company': 1, 'logo': 1, 'created_by': 1}))
    print(f"Scanning {len(jobs)} job(s)...\n")

    owner_ids = set()
    for job in jobs:
        owner = job.get('created_by')
        if owner and owner != 'system':
            try:
                owner_ids.add(ObjectId(str(owner)))
            except Exception:
                continue

    owners = {
        str(user['_id']): user
        for user in users_collection.find(
            {'_id': {'$in': list(owner_ids)}}, {'company_name': 1, 'company_logo': 1}
        )
    }

    updated = skipped_no_owner = already_correct = 0

    for job in jobs:
        owner = owners.get(str(job.get('created_by')))
        if not owner:
            skipped_no_owner += 1
            continue

        company = str(owner.get('company_name') or '').strip()
        logo = owner.get('company_logo')

        changes = {}
        if job.get('company') != company:
            changes['company'] = company
        if logo and job.get('logo') != logo:
            changes['logo'] = logo

        if not changes:
            already_correct += 1
            continue

        title = str(job.get('title') or '(untitled)')[:45]
        print(f"  {title:47} {job.get('company')!r} -> {company!r}")

        if not dry_run:
            jobs_collection.update_one({'_id': job['_id']}, {'$set': changes})
        updated += 1

    print(
        f"\n{'[DRY RUN] would update' if dry_run else 'Updated'}: {updated}"
        f" | already correct: {already_correct}"
        f" | skipped (no resolvable owner): {skipped_no_owner}"
    )
    return updated


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true', help='report changes without writing')
    args = parser.parse_args()

    migrate(dry_run=args.dry_run)
