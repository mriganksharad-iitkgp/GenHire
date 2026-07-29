"""Candidate job bookmarks ("Saved Jobs").

A saved job is a lightweight pointer — {candidate_id, job_id, saved_at} — not a
copy of the job. The listing endpoint joins back to `jobs` at read time so a
saved card always reflects the job's current title, company and status rather
than whatever it looked like on the day it was bookmarked.
"""

import datetime
import logging

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from utils.company_resolver import attach_company_info

logger = logging.getLogger(__name__)


class SavedJobController:
    def __init__(self, db_collections):
        self.saved_jobs_collection = db_collections['saved_jobs']
        self.jobs_collection = db_collections['jobs']
        self.applications_collection = db_collections['applications']
        self.users_collection = db_collections['users']

    @staticmethod
    def _as_object_id(job_id):
        try:
            return ObjectId(str(job_id))
        except Exception:
            return None

    def save_job(self, candidate_id, job_id):
        """Bookmark a job. Idempotent — saving twice is a no-op, not an error."""
        job_object_id = self._as_object_id(job_id)
        if not job_object_id:
            return {'error': 'Invalid job id'}, 400

        job = self.jobs_collection.find_one({'_id': job_object_id}, {'_id': 1})
        if not job:
            return {'error': 'Job not found'}, 404

        now = datetime.datetime.utcnow()
        try:
            self.saved_jobs_collection.update_one(
                {'candidate_id': str(candidate_id), 'job_id': str(job_id)},
                {'$setOnInsert': {
                    'candidate_id': str(candidate_id),
                    'job_id': str(job_id),
                    'saved_at': now,
                }},
                upsert=True,
            )
        except DuplicateKeyError:
            # Two concurrent saves raced past the upsert lookup; the row the
            # caller wanted exists either way, so this is still success.
            pass

        return {'saved': True, 'job_id': str(job_id), 'message': 'Job saved'}, 200

    def unsave_job(self, candidate_id, job_id):
        """Remove a bookmark. Unsaving something not saved is also a no-op."""
        if not self._as_object_id(job_id):
            return {'error': 'Invalid job id'}, 400

        result = self.saved_jobs_collection.delete_one(
            {'candidate_id': str(candidate_id), 'job_id': str(job_id)}
        )
        return {
            'saved': False,
            'job_id': str(job_id),
            'removed': result.deleted_count > 0,
            'message': 'Job removed from saved list',
        }, 200

    def list_saved_jobs(self, candidate_id):
        """Saved jobs, newest first, joined to live job data.

        Each entry carries `saved_at`, `has_applied` and `can_apply` so the UI
        can render an Apply button without a second round trip.
        """
        saved_rows = list(
            self.saved_jobs_collection.find({'candidate_id': str(candidate_id)})
            .sort('saved_at', -1)
        )
        if not saved_rows:
            return {'saved_jobs': [], 'count': 0}, 200

        saved_at_by_job = {}
        object_ids = []
        for row in saved_rows:
            job_id = str(row.get('job_id'))
            saved_at_by_job[job_id] = row.get('saved_at')
            object_id = self._as_object_id(job_id)
            if object_id:
                object_ids.append(object_id)

        jobs = list(self.jobs_collection.find({'_id': {'$in': object_ids}}))
        attach_company_info(self.users_collection, jobs)

        # A job the recruiter has since deleted can never be applied to, so drop
        # the dangling bookmark instead of showing a card that goes nowhere.
        live_job_ids = {str(job['_id']) for job in jobs}
        orphaned = [jid for jid in saved_at_by_job if jid not in live_job_ids]
        if orphaned:
            try:
                self.saved_jobs_collection.delete_many(
                    {'candidate_id': str(candidate_id), 'job_id': {'$in': orphaned}}
                )
            except Exception as e:
                logger.warning(f"Could not prune deleted jobs from saved list: {e}")

        applied_job_ids = {
            str(app.get('job_id'))
            for app in self.applications_collection.find(
                {'student_id': str(candidate_id), 'job_id': {'$in': list(live_job_ids)}},
                {'job_id': 1, 'cv_snapshot': 1, 'processing_status': 1},
            )
            # An invite skeleton row is not a real application — the candidate
            # still needs the Apply button. Mirrors the JobDetails check.
            if app.get('cv_snapshot')
            and app.get('processing_status') != 'awaiting_candidate'
        }

        saved_jobs = []
        for job in jobs:
            job['_id'] = str(job['_id'])
            job.pop('created_by', None)
            job['saved_at'] = saved_at_by_job.get(job['_id'])
            job['has_applied'] = job['_id'] in applied_job_ids
            job['can_apply'] = (
                not job['has_applied']
                and str(job.get('status') or 'active').strip().lower() == 'active'
            )
            saved_jobs.append(job)

        # find() returns in index order, not the order we asked for — restore
        # newest-saved-first.
        saved_jobs.sort(
            key=lambda j: j.get('saved_at') or datetime.datetime.min, reverse=True
        )

        return {'saved_jobs': saved_jobs, 'count': len(saved_jobs)}, 200
