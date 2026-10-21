import os
from pymongo import MongoClient
from middleware.rate_limiter import env_int
from config.env_loader import load_environment
from config.indexes import ensure_application_identity_index

load_environment()

class DatabaseConfig:
    def __init__(self):
        self.uri = os.getenv('MONGODB_URI')
        self.database_name = os.getenv('DATABASE_NAME', 'hrtech')
        self.client = None
        self.db = None
    
    def connect(self):
        """Establish connection to MongoDB and return database instance"""
        if self.db is not None:
            return self.db
        if not isinstance(self.uri, str) or not self.uri.strip().startswith(('mongodb://', 'mongodb+srv://')):
            raise RuntimeError('MONGODB_URI must be explicitly configured; refusing MongoDB localhost defaults.')
        self.client = MongoClient(
            self.uri,
            maxPoolSize=env_int('MONGO_MAX_POOL_SIZE', 50),
            waitQueueTimeoutMS=env_int('MONGO_WAIT_QUEUE_TIMEOUT_MS', 2000),
            minPoolSize=0,  # Don't pre-open connections; Atlas closes idle ones causing SSL resets
            connectTimeoutMS=10000,
            socketTimeoutMS=30000,
            serverSelectionTimeoutMS=env_int('MONGO_SERVER_SELECTION_TIMEOUT_MS', 5000),
        )
        self.db = self.client[self.database_name]
        self._ensure_indexes()
        return self.db

    def _ensure_indexes(self):
        """Create critical indexes used by auth and query paths."""
        from config.workflow import workflow_enabled
        if workflow_enabled():
            from repositories.workflow_repository import ensure_workflow_indexes
            ensure_workflow_indexes(self.db)
            from services.job_setup_service import ensure_setup_indexes
            ensure_setup_indexes(self.db)
            from services.assessment_authoring_service import ensure_authoring_indexes
            ensure_authoring_indexes(self.db)
            from services.assessment_generation_service import ensure_generation_indexes
            ensure_generation_indexes(self.db)
            from services.hiring_progression_service import ensure_progression_indexes
            ensure_progression_indexes(self.db)
            from services.assessment_runtime_service import ensure_runtime_indexes
            ensure_runtime_indexes(self.db)
            from services.assessment_evaluation_service import ensure_evaluation_indexes
            ensure_evaluation_indexes(self.db)
            from services.assessment_integrity_service import ensure_integrity_indexes
            ensure_integrity_indexes(self.db)
            from services.company_hiring_service import ensure_company_indexes
            ensure_company_indexes(self.db)
            from services.practice_assessment_service import ensure_practice_assessment_indexes
            ensure_practice_assessment_indexes(self.db)
        try:
            self.db['ai_provider_requests'].create_index(
                [('occurred_at', 1), ('provider', 1)], name='idx_provider_usage_timeline'
            )
        except Exception as e:
            print(f"Warning: failed to ensure provider usage index: {e}")

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
            invalid_identity = applications.find_one({
                '$or': [
                    {'job_id': {'$type': 'array'}},
                    {'student_id': {'$type': 'array'}},
                    {'job_id': {'$not': {'$regex': '^[0-9a-f]{24}$'}}},
                    {'student_id': {'$not': {'$regex': '^[0-9a-f]{24}$'}}},
                ],
            }, {'_id': 1})
            if invalid_identity:
                raise ValueError('Noncanonical legacy application identities require review')
            applications.create_index(
                [('job_id', 1), ('is_visible', 1)], name='idx_applications_job_visible'
            )
            # Matches the very common "does this candidate already have an
            # application for this job" lookup used throughout
            # application_controller.py / invite_service.py.
            ensure_application_identity_index(applications)
            applications.create_index(
                [('processing_status', 1), ('scoring_next_retry_at', 1), ('scoring_lease_until', 1)],
                name='idx_applications_scoring_work',
            )
        except Exception as e:
            raise RuntimeError(
                "Critical application indexes could not be ensured. Audit legacy duplicates "
                "with scripts/admin/audit_application_duplicates.py before rollout. "
                f"Cause: {type(e).__name__}; database code: {getattr(e, 'code', 'not available')}."
            ) from None

        try:
            saved_jobs = self.db['saved_jobs']
            # A candidate can bookmark a job at most once — the unique index is
            # what makes the save endpoint safely idempotent under double-click.
            saved_jobs.create_index(
                [('candidate_id', 1), ('job_id', 1)],
                unique=True,
                name='uq_saved_jobs_candidate_job',
            )
            # Backs the "my saved jobs, newest first" listing.
            saved_jobs.create_index(
                [('candidate_id', 1), ('saved_at', -1)], name='idx_saved_jobs_candidate_saved_at'
            )
        except Exception as e:
            print(f"Warning: failed to ensure saved_jobs indexes: {e}")

        try:
            # Outbound email audit log (see EmailService._log_send) — the
            # admin cost page counts successful sends per timeline window.
            email_log = self.db['email_log']
            email_log.create_index(
                [('sent_at', 1), ('success', 1)], name='idx_email_log_sent_at_success'
            )
        except Exception as e:
            print(f"Warning: failed to ensure email_log indexes: {e}")
    
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
            'invite_batches': self.db['invite_batches'],
            'saved_jobs': self.db['saved_jobs']
        }
    
    def close_connection(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()

# Global database instance
db_config = DatabaseConfig()
