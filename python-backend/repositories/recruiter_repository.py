"""Recruiter-scoped queries.

Recruiters are rows in the users collection (user_type='recruiter'); this
repository names the recruiter-specific query patterns.
"""

from repositories.base_repository import BaseRepository


class RecruiterRepository(BaseRepository):
    def find_pending(self):
        """Recruiters awaiting verification (not yet rejected), newest first."""
        query = {
            "user_type": "recruiter",
            "is_verified": False,
            "$or": [
                {"rejection_reason": None},
                {"rejection_reason": {"$exists": False}}
            ]
        }
        return self.col.find(query).sort("created_at", -1)
