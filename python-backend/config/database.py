import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

class DatabaseConfig:
    def __init__(self):
        self.uri = os.getenv('MONGODB_URI')
        self.database_name = os.getenv('DATABASE_NAME', 'hrtech')
        self.client = None
        self.db = None
    
    def connect(self):
        """Establish connection to MongoDB and return database instance"""
        self.client = MongoClient(self.uri)
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
            users.create_index(
                'email_lower',
                unique=True,
                partialFilterExpression={'is_invite_only': {'$exists': False}},
                name=target_email_index,
            )
            users.create_index('email', unique=False, sparse=True, name='idx_users_email')
            # Legacy username field (older invite docs). Kept harmless.
            users.create_index('username_lower', unique=True, sparse=True, name='uq_users_username_lower')
            # New: invite_id is the login identifier for invite-only burner accounts.
            users.create_index('invite_id_lower', unique=True, sparse=True, name='uq_users_invite_id_lower')
            users.create_index('is_invite_only', sparse=True, name='idx_users_is_invite_only')
        except Exception as e:
            # Do not block startup when legacy duplicate data exists.
            print(f"Warning: failed to ensure DB indexes: {e}")

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
