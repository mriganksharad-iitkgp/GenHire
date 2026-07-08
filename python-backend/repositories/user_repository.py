"""User lookups and writes.

find_by_email / find_by_identifier hold the email-normalization,
invite-account-exclusion, and legacy-record fallback logic moved verbatim
from AuthController's private helpers — this is the single place user
resolution lives now.
"""

import re

from repositories.base_repository import BaseRepository


def normalize_email(email):
    return str(email or '').strip().lower()


class UserRepository(BaseRepository):
    def find_by_identifier(self, identifier):
        """Resolve a user by email (if it contains '@') or by Invite ID otherwise.
        Email lookup intentionally skips invite-only burner accounts so a real
        candidate can keep using their email after they've been invited."""
        if not identifier:
            return None
        s = str(identifier).strip()
        if '@' in s:
            return self.find_by_email(s)
        s_lower = s.lower()
        # Invite ID lookup. Fall back to legacy `username_lower` for old data.
        return self.col.find_one(
            {'$or': [{'invite_id_lower': s_lower}, {'username_lower': s_lower}]}
        )

    def find_by_email(self, email):
        """Lookup a real (non-invite-only) account by email. Burner accounts
        are excluded so login-by-email never resolves to a temp invite account."""
        normalized_email = normalize_email(email)
        if not normalized_email:
            return None

        not_invite = {'is_invite_only': {'$ne': True}}

        user = self.col.find_one({
            '$and': [
                not_invite,
                {'$or': [
                    {'email_lower': normalized_email},
                    {'email': normalized_email},
                    {'email': str(email or '').strip()},
                ]},
            ]
        })
        if user:
            return user

        # Fallback for legacy records with mixed case or accidental spaces in `email`.
        escaped = re.escape(normalized_email)
        user = self.col.find_one({
            '$and': [
                not_invite,
                {'email': {'$regex': f'^\\s*{escaped}\\s*$', '$options': 'i'}},
            ]
        })
        if user:
            return user

        # Last-resort normalization query using Mongo expressions.
        return self.col.find_one({
            '$and': [
                not_invite,
                {'$expr': {
                    '$eq': [
                        {'$toLower': {'$trim': {'input': {'$ifNull': ['$email', '']}}}},
                        normalized_email,
                    ]
                }},
            ]
        })
