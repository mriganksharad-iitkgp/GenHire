import os
from pymongo import MongoClient
from config.env_loader import load_environment

load_environment()

class DatabaseConfig:
    def __init__(self):
        self.uri = os.getenv('MONGODB_URI')
        self.database_name = os.getenv('DATABASE_NAME', 'hrtech')
        self.client = None
        self.db = None
    
    def connect(self):
        """Establish connection to MongoDB and return database instance"""
        self.client = MongoClient(
            self.uri,
            maxPoolSize=50,
            minPoolSize=0,  # Don't pre-open connections; Atlas closes idle ones causing SSL resets
            connectTimeoutMS=10000,
            socketTimeoutMS=30000,
            serverSelectionTimeoutMS=10000,
        )
        self.db = self.client[self.database_name]
        self._ensure_indexes()
        return self.db

    def _ensure_indexes(self):
        """Create critical indexes used by auth and query paths."""
        try:
            users = self.db['users']
            # Email uniqueness applies ONLY to non-invite-only docs (regular
            # candidates / recruiters / admins). Invite-only burner accounts
            # are allowed to share an email so a single invitee can hold
            # multiple Invite IDs from different (or the same) recruiter.
            #
            # Drop any pre-existing unique index on email or email_lower whose
            # name isn't the partial-filtered one we want. The legacy schema
            # had unique indexes on both fields; both block invite-only docs
            # from sharing an email, so both must go.
            target_email_index = 'uq_users_email_lower_real'
            try:
                for idx_name, idx_spec in users.index_information().items():
                    keys = idx_spec.get('key') or []
                    key_fields = [k for k, _ in keys] if keys else []
                    if key_fields not in (['email'], ['email_lower']):
                        continue
                    if idx_name == target_email_index:
                        continue
                    is_unique = bool(idx_spec.get('unique'))
                    has_partial = 'partialFilterExpression' in idx_spec
                    if is_unique and not has_partial:
                        try:
                            users.drop_index(idx_name)
                            print(f"[startup] dropped legacy unique index '{idx_name}' on {key_fields}")
                        except Exception as drop_err:
                            print(f"Warning: could not drop legacy index {idx_name}: {drop_err}")
            except Exception as e:
                print(f"Warning: could not inspect indexes: {e}")
            # Use a sparse unique index on email_lower instead of a partial index.
            # - sparse=True: only indexes docs that HAVE a non-null email_lower field,
            #   so invite-only users with email_lower=null are excluded automatically.
            # - unique=True: enforces uniqueness among indexed docs (real users).
            # This avoids the need for partialFilterExpression entirely, which has
            # compatibility issues with some Atlas versions ($not / $exists: false).
            try:
                existing_indexes = users.index_information()
                if target_email_index in existing_indexes:
                    old_spec = existing_indexes[target_email_index]
                    # Drop if it's a partial-filter index (old approach) so we can
                    # recreate it as a sparse index.
                    if 'partialFilterExpression' in old_spec:
                        users.drop_index(target_email_index)
                        print(f"[startup] dropped old partial-filter index '{target_email_index}' — recreating as sparse")
            except Exception as _check_err:
                print(f"Warning: could not check/migrate email index: {_check_err}")

            try:
                users.create_index(
                    'email_lower',
                    unique=True,
                    sparse=True,  # Skips docs where email_lower is null/missing (invite-only users)
                    name=target_email_index,
                )
            except Exception:
                pass # suppress duplicate key error on email_lower

            users.create_index('email', unique=False, sparse=True, name='idx_users_email')
            # Legacy username field (older invite docs). Kept harmless.
            users.create_index('username_lower', unique=True, sparse=True, name='uq_users_username_lower')
            # New: invite_id is the login identifier for invite-only burner accounts.
            users.create_index('invite_id_lower', unique=True, sparse=True, name='uq_users_invite_id_lower')
            users.create_index('is_invite_only', sparse=True, name='idx_users_is_invite_only')
        except Exception as e:
            # Do not block startup when legacy duplicate data exists.
            pass # Suppress noisy index errors

        try:
            invite_tokens = self.db['invite_tokens']
            invite_tokens.create_index('token_hash', unique=True, name='uq_invite_tokens_hash')
            invite_tokens.create_index('user_id', name='idx_invite_tokens_user')
            invite_tokens.create_index(
                'expires_at', expireAfterSeconds=0, name='ttl_invite_tokens_expires_at'
            )
        except Exception as e:
            print(f"Warning: failed to ensure invite_tokens indexes: {e}")

        try:
            invite_batches = self.db['invite_batches']
            invite_batches.create_index('recruiter_id', name='idx_invite_batches_recruiter')
            invite_batches.create_index('job_id', name='idx_invite_batches_job')
            invite_batches.create_index('created_at', name='idx_invite_batches_created_at')
        except Exception as e:
            print(f"Warning: failed to ensure invite_batches indexes: {e}")

        try:
            applications = self.db['applications']
            # Matches the recruiter dashboard's applications query exactly
            # (job_id $in [...] + is_visible) — was previously unindexed.
            applications.create_index(
                [('job_id', 1), ('is_visible', 1)], name='idx_applications_job_visible'
            )
            # Matches the very common "does this candidate already have an
            # application for this job" lookup used throughout
            # application_controller.py / invite_service.py.
            applications.create_index(
                [('job_id', 1), ('student_id', 1)], name='idx_applications_job_student'
            )
        except Exception as e:
            print(f"Warning: failed to ensure applications indexes: {e}")
    
    def get_db(self):
        """Get database instance, connecting if needed"""
        if self.db is None:
            self.connect()
        return self.db
    
    def get_collections(self):
        """Return dictionary of collection objects"""
        if self.db is None:
            self.connect()
        return {
            'users': self.db['users'],
            'jobs': self.db['jobs'],
            'applications': self.db['applications'],
            'interviews': self.db['interviews'],
            'practice_sessions': self.db['practice_sessions'],
            'invite_tokens': self.db['invite_tokens'],
            'invite_batches': self.db['invite_batches']
        }
    
    def close_connection(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()

# Global database instance
db_config = DatabaseConfig()
