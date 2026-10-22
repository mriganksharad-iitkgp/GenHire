"""Resolve a job's company name/logo from the recruiter who owns it.

Job documents carry a denormalized copy of the recruiter's company details,
snapshotted when the job was created. That copy goes stale as soon as the
recruiter edits their company profile, and jobs created before the profile was
filled in were historically stamped with a literal placeholder name. The
recruiter record is the source of truth, so read paths re-resolve these two
fields from it using a single bulk lookup rather than one query per job.
"""

from bson import ObjectId
import uuid
from services.shared_cache import cache, MISSING


def invalidate_company(users_collection, owner_id):
    # Versioned entries fence concurrent readers that started before the edit.
    cache.set('company-revision', [users_collection.database.name, str(owner_id)], uuid.uuid4().hex, 3600)


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

    object_ids = list(dict.fromkeys(object_ids))
    scope = users_collection.database.name
    parts = [[scope, str(owner)] for owner in object_ids]
    versions = cache.get_many('company-revision', parts)
    keys = [part + [version if version is not MISSING else '0'] for part, version in zip(parts, versions)]
    hits = cache.get_many('company-display', keys)
    result, missing, key_by_id = {}, [], {}
    for owner, key, hit in zip(object_ids, keys, hits):
        if isinstance(hit, dict) and set(hit) <= {'company_name', 'company_logo'}:
            result[str(owner)] = hit
        else:
            missing.append(owner)
            key_by_id[str(owner)] = key
    if not missing:
        return result
    for user in users_collection.find(
            {'_id': {'$in': missing}},
            {'company_name': 1, 'company_logo': 1},
        ):
        identifier = str(user['_id'])
        display = {key: user.get(key) for key in ('company_name', 'company_logo')}
        result[identifier] = display
        cache.set('company-display', key_by_id[identifier], display, 60)
    return result


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
