"""Resolve a job's company name/logo from the recruiter who owns it.

Job documents carry a denormalized copy of the recruiter's company details,
snapshotted when the job was created. That copy goes stale as soon as the
recruiter edits their company profile, and jobs created before the profile was
filled in were historically stamped with a literal placeholder name. The
recruiter record is the source of truth, so read paths re-resolve these two
fields from it using a single bulk lookup rather than one query per job.
"""

from bson import ObjectId


def load_company_map(users_collection, owner_ids):
    """Map str(recruiter_id) -> {'company_name': ..., 'company_logo': ...}."""
    object_ids = []
    for owner in owner_ids:
        if not owner or owner == 'system':
            continue
        try:
            object_ids.append(ObjectId(str(owner)))
        except Exception:
            continue

    if not object_ids:
        return {}

    return {
        str(user['_id']): user
        for user in users_collection.find(
            {'_id': {'$in': object_ids}},
            {'company_name': 1, 'company_logo': 1},
        )
    }


def attach_company_info(users_collection, jobs):
    """Overwrite `company`/`logo` on each job dict from its owning recruiter.

    Must be called BEFORE `created_by` is stripped for candidate responses.
    An owner with no company name blanks the field, so the UI renders
    "not specified" instead of naming a company that does not exist.
    """
    if not jobs:
        return jobs

    owners_by_id = load_company_map(
        users_collection, {job.get('created_by') for job in jobs}
    )

    for job in jobs:
        owner = owners_by_id.get(str(job.get('created_by')))
        if not owner:
            continue
        job['company'] = str(owner.get('company_name') or '').strip()
        company_logo = owner.get('company_logo')
        if company_logo:
            job['logo'] = company_logo

    return jobs
