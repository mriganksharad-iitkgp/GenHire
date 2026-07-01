from werkzeug.security import generate_password_hash, check_password_hash
import jwt as pyjwt
import datetime
import os
import re
from bson import ObjectId
import secrets
from pymongo.errors import DuplicateKeyError
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import requests as http_requests
from services.email_service import EmailService
from payment_module.services.wallet_service import WalletService
from middleware.input_validator import validate_email, validate_password, validate_name

class AuthController:
    def __init__(self, db_collections):
        self.users_collection = db_collections['users']
        self.secret_key = os.getenv('JWT_SECRET_KEY', 'your-secret-key-here')
        self.google_client_id = os.getenv('GOOGLE_CLIENT_ID')
        self.email_service = EmailService()
        self.require_email_verification = os.getenv('REQUIRE_EMAIL_VERIFICATION', 'true').lower() == 'true'
        self.wallet_service = WalletService(self.users_collection.database)

    def _normalize_email(self, email):
        return str(email or '').strip().lower()

    def _recruiter_onboarding_complete(self, user_data):
        if str((user_data or {}).get('user_type', '')).strip().lower() != 'recruiter':
            return True
        # Credential-based and legacy recruiter accounts already passed the
        # normal registration flow. OAuth onboarding applies only to Google
        # recruiter accounts, so never redirect local logins into signup.
        auth_provider = str((user_data or {}).get('auth_provider', 'local')).strip().lower()
        if auth_provider != 'google':
            return True
        required_fields = ('company_name', 'company_description', 'company_size', 'company_industry')
        return all(str((user_data or {}).get(field) or '').strip() for field in required_fields)

    def _google_onboarding_response(self, email, name, existing_user=None):
        return {
            'message': 'Complete your recruiter profile to continue',
            'onboarding_required': True,
            'user': {
                'id': str(existing_user['_id']) if existing_user else None,
                'name': name or (existing_user or {}).get('name', ''),
                'email': email,
                'user_type': 'recruiter',
                'auth_provider': 'google',
                'onboarding_complete': False,
            }
        }, 200

    def _find_user_by_identifier(self, identifier):
        """Resolve a user by email (if it contains '@') or by Invite ID otherwise.
        Email lookup intentionally skips invite-only burner accounts so a real
        candidate can keep using their email after they've been invited."""
        if not identifier:
            return None
        s = str(identifier).strip()
        if '@' in s:
            return self._find_user_by_email(s)
        s_lower = s.lower()
        # Invite ID lookup. Fall back to legacy `username_lower` for old data.
        return self.users_collection.find_one(
            {'$or': [{'invite_id_lower': s_lower}, {'username_lower': s_lower}]}
        )

    def _find_user_by_email(self, email):
        """Lookup a real (non-invite-only) account by email. Burner accounts
        are excluded so login-by-email never resolves to a temp invite account."""
        normalized_email = self._normalize_email(email)
        if not normalized_email:
            return None

        not_invite = {'is_invite_only': {'$ne': True}}

        user = self.users_collection.find_one({
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
        user = self.users_collection.find_one({
            '$and': [
                not_invite,
                {'email': {'$regex': f'^\\s*{escaped}\\s*$', '$options': 'i'}},
            ]
        })
        if user:
            return user

        # Last-resort normalization query using Mongo expressions.
        return self.users_collection.find_one({
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

    def check_email_account_type(self, email, requested_user_type='candidate'):
        """Check if an email is available for the requested account type."""
        normalized_email = self._normalize_email(email)
        requested_user_type = str(requested_user_type or 'candidate').strip().lower()

        if not normalized_email:
            return {'error': 'Email is required'}, 400

        if requested_user_type not in ['candidate', 'recruiter']:
            return {'error': 'Invalid user type'}, 400

        existing_user = self._find_user_by_email(normalized_email)
        if not existing_user:
            return {
                'available': True,
                'email': normalized_email,
                'requested_user_type': requested_user_type
            }, 200

        existing_type = str(existing_user.get('user_type', 'candidate')).strip().lower()
        if existing_type != requested_user_type:
            return {
                'available': False,
                'email': normalized_email,
                'requested_user_type': requested_user_type,
                'existing_user_type': existing_type,
                'error': f'This email is already registered as a {existing_type}. One email can be used for only one account type.'
            }, 409

        return {
            'available': False,
            'email': normalized_email,
            'requested_user_type': requested_user_type,
            'existing_user_type': existing_type,
            'error': 'Email already exists'
        }, 409
        
    def register_user(self, user_data):
        """Register a new user"""
        name = user_data.get('name')
        email = user_data.get('email')
        password = user_data.get('password')
        confirm_password = user_data.get('confirmPassword')
        user_type = str(user_data.get('userType', 'candidate')).strip().lower()
        normalized_email = self._normalize_email(email)

        # Validation
        if not all([name, normalized_email, password, confirm_password]):
            return {'error': 'All fields are required'}, 400

        err = validate_name(name)
        if err:
            return {'error': err}, 400
        err = validate_email(normalized_email)
        if err:
            return {'error': err}, 400
        err = validate_password(password)
        if err:
            return {'error': err}, 400

        if password != confirm_password:
            return {'error': 'Passwords do not match'}, 400

        # Only allow candidate and recruiter registration (admins created manually)
        if user_type not in ['candidate', 'recruiter']:
            return {'error': 'Invalid user type'}, 400

        verification_token = secrets.token_urlsafe(32) if self.require_email_verification else None
        is_verified = user_type == 'candidate'
        
        # Check if user exists - enforce one email per role
        existing_user = self._find_user_by_email(normalized_email)
        if existing_user:
            existing_role = existing_user.get('user_type', 'candidate')
            if existing_role == user_type:
                return {'error': f'An account with this email already exists as a {existing_role}. Please log in instead.'}, 400
            else:
                return {'error': f'This email is already registered as a {existing_role}. Each email can only be associated with one role.'}, 409
        
        # Create new user
        user_doc = {
            'name': name,
            'email': normalized_email,
            'email_lower': normalized_email,
            'password': generate_password_hash(password),
            'user_type': user_type,
            'email_verified': False if self.require_email_verification else True,
            'verification_token': verification_token if self.require_email_verification else None,
            'verification_token_expires': datetime.datetime.utcnow() + datetime.timedelta(hours=24) if self.require_email_verification else None,
            'created_at': datetime.datetime.utcnow(),
            'updated_at': datetime.datetime.utcnow(),
            'auth_provider': 'local',  # Track auth method
            # Verification and permission fields
            'is_verified': is_verified,
            'verified_by': None,
            'verified_at': datetime.datetime.utcnow() if is_verified else None,
            'permissions': []
        }
        
        # Add company information for recruiters (accept both camelCase and snake_case)
        if user_type == 'recruiter':
            user_doc.update({
                'company_name': user_data.get('companyName') or user_data.get('company_name', ''),
                'company_logo': user_data.get('companyLogo') or user_data.get('company_logo', None),
                'company_description': user_data.get('companyDescription') or user_data.get('company_description', ''),
                'company_website': user_data.get('companyWebsite') or user_data.get('company_website', None),
                'company_size': user_data.get('companySize') or user_data.get('company_size', None),
                'company_industry': user_data.get('companyIndustry') or user_data.get('company_industry', ''),
                'company_location': user_data.get('companyLocation') or user_data.get('company_location', ''),
                # Additional onboarding fields
                'reason_for_joining': user_data.get('reasonForJoining') or user_data.get('reason_for_joining', ''),
                'linkedin_profile': user_data.get('linkedinProfile') or user_data.get('linkedin_profile', ''),
                'onboarding_complete': True
            })
        
        try:
            user_id = self.users_collection.insert_one(user_doc).inserted_id
        except DuplicateKeyError:
            existing_user = self._find_user_by_email(normalized_email)
            existing_type = str((existing_user or {}).get('user_type', 'candidate')).strip().lower()
            if existing_type != user_type:
                return {
                    'error': f'This email is already registered as a {existing_type}. One email can be used for only one account type.'
                }, 409
            return {'error': 'Email already exists'}, 409

        # Send verification email if required
        if self.require_email_verification:
            try:
                email_sent = self.email_service.send_verification_email(normalized_email, verification_token, name)
            except Exception as e:
                print(f"Error sending verification email: {str(e)}")
                email_sent = False

            if not email_sent:
                self.users_collection.delete_one({'_id': user_id})
                return {'error': 'Could not send verification email. Please try again later.'}, 502

        self.wallet_service.grant_signup_bonus_once(str(user_id), user_type)
        
        # Generate token (but user may need to verify email before full access)
        token = self.generate_token(user_id)
        
        response_message = 'User registered successfully'
        if self.require_email_verification:
            response_message += '. Please check your email to verify your GenHire account.'
        if user_type == 'recruiter':
            response_message += ' Your recruiter account is pending admin verification.'
        
        return {
            'message': response_message,
            'token': token,
            'email_verification_required': self.require_email_verification,
            'account_verification_required': not is_verified,
            'user': {
                'id': str(user_id),
                'name': name,
                'email': normalized_email,
                'user_type': user_type,
                'email_verified': user_doc['email_verified'],
                'is_verified': is_verified,
                'permissions': [],
                'onboarding_complete': user_doc.get('onboarding_complete', True)
            }
        }, 201
        
    def login_user(self, identifier, password, user_type):
        """Authenticate user (by email or username) and return token."""
        if not identifier or not password:
            return {'error': 'Email/username and password are required'}, 400

        identifier_str = str(identifier).strip()
        user_type = str(user_type or 'candidate').strip().lower()

        # Support candidate, recruiter, and admin login
        if user_type not in ['candidate', 'recruiter', 'admin']:
            return {'error': 'Invalid credentials'}, 401

        user = self._find_user_by_identifier(identifier_str)

        if not user or not check_password_hash(user['password'], password):
            return {'error': 'Invalid email or password'}, 401

        # Block invite-only (burner) accounts from claiming recruiter or admin roles.
        if user.get('is_invite_only') and user_type in ('recruiter', 'admin'):
            return {'error': 'Invalid email or password'}, 401
        
        # Check if user type matches
        stored_user_type = user.get('user_type', 'candidate')
        
        # Strict user type matching - no cross-login allowed
        # Return generic error to avoid leaking user type information
        if stored_user_type != user_type:
            return {'error': 'Invalid email or password'}, 401
        
        # Admin-specific checks
        if user_type == 'admin':
            # Ensure admin has proper permissions
            if not user.get('permissions') or not user.get('is_verified'):
                return {'error': 'Invalid email or password'}, 401
        
        # Check if email verification is required and if email is verified
        # Skip email verification for admins (they are created as verified)
        if user_type != 'admin' and self.require_email_verification and not user.get('email_verified', False):
            # Allow OAuth users to login without verification
            if user.get('auth_provider') != 'google':
                return {
                    'error': 'Please verify your email before logging in to your GenHire account',
                    'email_verification_required': True
                }, 403
        
        # Get verification status (relevant for recruiters and admins)
        is_verified = user.get('is_verified', True)
        
        # Generate token
        token = self.generate_token(user['_id'])

        # Backfill normalized email_lower for legacy rows when we logged in via email.
        stored_email = user.get('email') or ''
        canonical_email = self._normalize_email(stored_email)
        if canonical_email and (stored_email != canonical_email or not user.get('email_lower')):
            self.users_collection.update_one(
                {'_id': user['_id']},
                {
                    '$set': {
                        'email': canonical_email,
                        'email_lower': canonical_email,
                        'updated_at': datetime.datetime.utcnow()
                    }
                }
            )

        invited_job_ids = [str(j) for j in (user.get('invited_job_ids') or [])]

        return {
            'message': 'Logged in successfully',
            'token': token,
            'user': {
                'id': str(user['_id']),
                'name': user.get('name') or '',
                'email': user.get('email'),
                'invite_id': user.get('invite_id') or user.get('username'),
                'user_type': stored_user_type,
                'email_verified': user.get('email_verified', False),
                'is_verified': is_verified,
                'permissions': user.get('permissions', []),
                'is_invite_only': bool(user.get('is_invite_only')),
                'invite_first_login_required': bool(user.get('invite_first_login_required')),
                'invited_job_ids': invited_job_ids,
                'onboarding_complete': self._recruiter_onboarding_complete(user),
                'rejection_reason': user.get('rejection_reason')
            }
        }, 200
        
    def generate_token(self, user_id):
        """Generate JWT token for user"""
        expiration_days = int(os.getenv('JWT_EXPIRATION_DAYS', 1))
        return pyjwt.encode({
            'user_id': str(user_id),
            'exp': datetime.datetime.utcnow() + datetime.timedelta(days=expiration_days)
        }, self.secret_key, algorithm='HS256')
        
    def verify_token(self, token):
        """Verify JWT token and return user data"""
        try:
            # Check for the "Bearer " prefix and remove it if it exists
            if isinstance(token, str) and token.startswith('Bearer '):
                token = token[7:]

            data = pyjwt.decode(token, self.secret_key, algorithms=['HS256'])
            current_user = self.users_collection.find_one({'_id': ObjectId(data['user_id'])})

            if not current_user:
                return None, 'User not found'

            return current_user, None

        except pyjwt.ExpiredSignatureError:
            return None, 'Token has expired'
        except pyjwt.InvalidTokenError:
            return None, 'Token is invalid'
    
    def get_current_user_info(self, user):
        """Get formatted current user information"""
        return {
            'id': str(user['_id']),
            'name': user.get('name') or '',
            'email': user.get('email'),
            'invite_id': user.get('invite_id') or user.get('username'),
            'user_type': user.get('user_type', 'candidate'),
            'email_verified': user.get('email_verified', False),
            'auth_provider': user.get('auth_provider', 'local'),
            'is_verified': user.get('is_verified', True),
            'permissions': user.get('permissions', []),
            'is_invite_only': bool(user.get('is_invite_only')),
            'invite_first_login_required': bool(user.get('invite_first_login_required')),
            'invited_job_ids': [str(j) for j in (user.get('invited_job_ids') or [])],
            'onboarding_complete': self._recruiter_onboarding_complete(user),
            'rejection_reason': user.get('rejection_reason')
        }
    
    def verify_email(self, token):
        """Verify user's email address using token"""
        user = self.users_collection.find_one({
            'verification_token': token,
            'email_verified': False
        })
        
        if not user:
            return {'error': 'Invalid or expired verification token'}, 400
        
        # Check if token is expired
        if user.get('verification_token_expires'):
            if user['verification_token_expires'] < datetime.datetime.utcnow():
                return {'error': 'Verification token has expired'}, 400
        
        # Update user document
        self.users_collection.update_one(
            {'_id': user['_id']},
            {
                '$set': {
                    'email_verified': True,
                    'updated_at': datetime.datetime.utcnow()
                },
                '$unset': {
                    'verification_token': '',
                    'verification_token_expires': ''
                }
            }
        )
        
        return {
            'message': 'Email verified successfully',
            'user': {
                'id': str(user['_id']),
                'name': user['name'],
                'email': user['email'],
                'user_type': user.get('user_type', 'candidate'),
                'email_verified': True
            }
        }, 200
    
    def resend_verification_email(self, email):
        """Resend verification email to user"""
        normalized_email = self._normalize_email(email)
        user = self._find_user_by_email(normalized_email)
        
        if not user:
            return {'error': 'User not found'}, 404
        
        if user.get('email_verified', False):
            return {'error': 'Email is already verified'}, 400
        
        # Generate new verification token
        verification_token = secrets.token_urlsafe(32)
        
        # Update user document with new token
        self.users_collection.update_one(
            {'_id': user['_id']},
            {
                '$set': {
                    'verification_token': verification_token,
                    'verification_token_expires': datetime.datetime.utcnow() + datetime.timedelta(hours=24),
                    'updated_at': datetime.datetime.utcnow()
                }
            }
        )
        
        # Send verification email
        try:
            email_sent = self.email_service.send_verification_email(normalized_email, verification_token, user['name'])
            if not email_sent:
                return {'error': 'Failed to send verification email'}, 502
            return {'message': 'Verification email sent successfully'}, 200
        except Exception as e:
            print(f"Error sending verification email: {str(e)}")
            return {'error': 'Failed to send verification email'}, 500
    
    def request_password_reset(self, email):
        """Send password reset email to user"""
        normalized_email = self._normalize_email(email)
        user = self._find_user_by_email(normalized_email)
        
        if not user:
            # Don't reveal if user exists for security
            return {'message': 'If your email is registered, you will receive a password reset link'}, 200
        
        # Don't allow password reset for OAuth users
        if user.get('auth_provider') == 'google':
            return {'error': 'Cannot reset password for Google accounts'}, 400
        
        # Generate reset token
        reset_token = secrets.token_urlsafe(32)
        
        # Update user document with reset token
        self.users_collection.update_one(
            {'_id': user['_id']},
            {
                '$set': {
                    'reset_token': reset_token,
                    'reset_token_expires': datetime.datetime.utcnow() + datetime.timedelta(hours=1),
                    'updated_at': datetime.datetime.utcnow()
                }
            }
        )
        
        # Send reset email
        try:
            email_sent = self.email_service.send_password_reset_email(normalized_email, reset_token, user['name'])
            if not email_sent:
                return {'error': 'Could not send password reset email. Please try again later.'}, 502
        except Exception as e:
            print(f"Error sending password reset email: {str(e)}")
            return {'error': 'Could not send password reset email. Please try again later.'}, 500
        
        return {'message': 'If your email is registered, you will receive a password reset link'}, 200
    
    def reset_password(self, token, new_password, confirm_password):
        """Reset user password using reset token"""
        if not new_password or not confirm_password:
            return {'error': 'Password and confirmation are required'}, 400

        if new_password != confirm_password:
            return {'error': 'Passwords do not match'}, 400

        err = validate_password(new_password, field_name='New password')
        if err:
            return {'error': err}, 400
        
        user = self.users_collection.find_one({
            'reset_token': token
        })
        
        if not user:
            return {'error': 'Invalid or expired reset token'}, 400
        
        # Check if token is expired
        if user.get('reset_token_expires'):
            if user['reset_token_expires'] < datetime.datetime.utcnow():
                return {'error': 'Reset token has expired'}, 400
        
        # Update password and remove reset token
        self.users_collection.update_one(
            {'_id': user['_id']},
            {
                '$set': {
                    'password': generate_password_hash(new_password),
                    'updated_at': datetime.datetime.utcnow()
                },
                '$unset': {
                    'reset_token': '',
                    'reset_token_expires': ''
                }
            }
        )
        
        # Send confirmation email
        try:
            self.email_service.send_password_changed_confirmation(user['email'], user['name'])
        except Exception as e:
            print(f"Error sending password change confirmation: {str(e)}")
        
        return {'message': 'Password reset successfully'}, 200
    
    def google_oauth_login(self, token, user_type='candidate', user_data=None):
        """Authenticate or create user using Google OAuth token"""
        if not self.google_client_id:
            return {'error': 'Google OAuth not configured'}, 500

        user_data = user_data or {}
        user_type = str(user_type or 'candidate').strip().lower()

        # Only allow candidate and recruiter registration via OAuth.
        if user_type not in ['candidate', 'recruiter']:
            return {'error': 'Invalid user type'}, 400
        
        try:
            # Detect token type: ID tokens are JWTs (contain two dots), access tokens are opaque
            if token.count('.') == 2:
                idinfo = id_token.verify_oauth2_token(
                    token,
                    google_requests.Request(),
                    self.google_client_id,
                    clock_skew_in_seconds=10
                )
            else:
                # Access token — verify via Google's userinfo endpoint
                resp = http_requests.get(
                    'https://www.googleapis.com/oauth2/v3/userinfo',
                    headers={'Authorization': f'Bearer {token}'},
                    timeout=10
                )
                if not resp.ok:
                    return {'error': 'Invalid Google access token'}, 401
                idinfo = resp.json()

            # Get user info from token
            email = self._normalize_email(idinfo.get('email'))
            name = idinfo.get('name')
            google_id = idinfo.get('sub')

            if not email:
                return {'error': 'Email not provided by Google'}, 400

            # Check if user exists
            user = self._find_user_by_email(email)

            if user:
                # Enforce one email = one role: block cross-role signup/login
                existing_role = user.get('user_type', 'candidate')
                if existing_role != user_type:
                    return {
                        'error': f'This email is already registered as a {existing_role}. Each email can only be associated with one role.'
                    }, 409

                if user_type == 'recruiter' and not self._recruiter_onboarding_complete(user):
                    has_onboarding_data = self._recruiter_onboarding_complete({
                        'user_type': 'recruiter',
                        'auth_provider': 'google',
                        'company_name': user_data.get('companyName') or user_data.get('company_name'),
                        'company_description': user_data.get('companyDescription') or user_data.get('company_description'),
                        'company_size': user_data.get('companySize') or user_data.get('company_size'),
                        'company_industry': user_data.get('companyIndustry') or user_data.get('company_industry'),
                    })
                    if not has_onboarding_data:
                        return self._google_onboarding_response(email, name, user)

                    self.users_collection.update_one(
                        {'_id': user['_id']},
                        {'$set': {
                            'name': name or user.get('name', ''),
                            'company_name': user_data.get('companyName') or user_data.get('company_name', ''),
                            'company_description': user_data.get('companyDescription') or user_data.get('company_description', ''),
                            'company_website': user_data.get('companyWebsite') or user_data.get('company_website'),
                            'company_size': user_data.get('companySize') or user_data.get('company_size'),
                            'company_industry': user_data.get('companyIndustry') or user_data.get('company_industry', ''),
                            'company_location': user_data.get('companyLocation') or user_data.get('company_location', ''),
                            'reason_for_joining': user_data.get('reasonForJoining') or user_data.get('reason_for_joining', ''),
                            'linkedin_profile': user_data.get('linkedinProfile') or user_data.get('linkedin_profile', ''),
                            'onboarding_complete': True,
                            'updated_at': datetime.datetime.utcnow(),
                        }}
                    )
                    user = self.users_collection.find_one({'_id': user['_id']})

                # Update existing user if they signed up with local auth
                self.users_collection.update_one(
                    {'_id': user['_id']},
                    {
                        '$set': {
                            'auth_provider': 'google',
                            'google_id': google_id,
                            'email': email,
                            'email_lower': email,
                            'email_verified': True,  # Google accounts are pre-verified
                            'updated_at': datetime.datetime.utcnow()
                        }
                    }
                )

                # Generate token
                jwt_token = self.generate_token(user['_id'])

                return {
                    'message': 'Logged in successfully with Google',
                    'token': jwt_token,
                    'user': {
                        'id': str(user['_id']),
                        'name': user['name'],
                        'email': user['email'],
                        'user_type': user.get('user_type', 'candidate'),
                        'email_verified': True,
                        'auth_provider': 'google',
                        'is_verified': user.get('is_verified', True),
                        'permissions': user.get('permissions', []),
                        'onboarding_complete': self._recruiter_onboarding_complete(user),
                        'rejection_reason': user.get('rejection_reason')
                    }
                }, 200
            else:
                if user_type == 'recruiter':
                    has_onboarding_data = self._recruiter_onboarding_complete({
                        'user_type': 'recruiter',
                        'auth_provider': 'google',
                        'company_name': user_data.get('companyName') or user_data.get('company_name'),
                        'company_description': user_data.get('companyDescription') or user_data.get('company_description'),
                        'company_size': user_data.get('companySize') or user_data.get('company_size'),
                        'company_industry': user_data.get('companyIndustry') or user_data.get('company_industry'),
                    })
                    if not has_onboarding_data:
                        return self._google_onboarding_response(email, name)

                # Determine verification status for new users
                # Candidates are auto-verified, recruiters need admin approval
                is_verified = True if user_type == 'candidate' else False

                # Create new user with Google OAuth
                user_doc = {
                    'name': name,
                    'email': email,
                    'email_lower': email,
                    'password': generate_password_hash(secrets.token_urlsafe(32)),  # Random password for OAuth users
                    'user_type': user_type,
                    'email_verified': True,  # Google accounts are pre-verified
                    'auth_provider': 'google',
                    'google_id': google_id,
                    'created_at': datetime.datetime.utcnow(),
                    'updated_at': datetime.datetime.utcnow(),
                    # Verification and permission fields
                    'is_verified': is_verified,
                    'verified_by': None,
                    'verified_at': datetime.datetime.utcnow() if is_verified else None,
                    'permissions': []
                }

                # Add company information for recruiters (from onboarding form)
                if user_type == 'recruiter':
                    user_doc.update({
                        'company_name': user_data.get('companyName') or user_data.get('company_name', ''),
                        'company_logo': user_data.get('companyLogo') or user_data.get('company_logo', None),
                        'company_description': user_data.get('companyDescription') or user_data.get('company_description', ''),
                        'company_website': user_data.get('companyWebsite') or user_data.get('company_website', None),
                        'company_size': user_data.get('companySize') or user_data.get('company_size', None),
                        'company_industry': user_data.get('companyIndustry') or user_data.get('company_industry', ''),
                        'company_location': user_data.get('companyLocation') or user_data.get('company_location', ''),
                        'reason_for_joining': user_data.get('reasonForJoining') or user_data.get('reason_for_joining', ''),
                        'linkedin_profile': user_data.get('linkedinProfile') or user_data.get('linkedin_profile', ''),
                        'onboarding_complete': True
                    })
                
                try:
                    user_id = self.users_collection.insert_one(user_doc).inserted_id
                except DuplicateKeyError:
                    existing_user = self._find_user_by_email(email)
                    existing_type = str((existing_user or {}).get('user_type', 'candidate')).strip().lower()
                    if existing_type != user_type:
                        return {
                            'error': f'This email is already registered as a {existing_type}. One email can be used for only one account type.'
                        }, 409
                    return {'error': 'Email already exists'}, 409

                self.wallet_service.grant_signup_bonus_once(str(user_id), user_type)
                
                # Generate token
                jwt_token = self.generate_token(user_id)
                
                message = 'Account created and logged in successfully with Google'
                if user_type == 'recruiter':
                    message += '. Your recruiter account is pending admin verification.'
                
                return {
                    'message': message,
                    'token': jwt_token,
                    'account_verification_required': not is_verified,
                    'user': {
                        'id': str(user_id),
                        'name': name,
                        'email': email,
                        'user_type': user_type,
                        'email_verified': True,
                        'auth_provider': 'google',
                        'is_verified': is_verified,
                        'permissions': [],
                        'onboarding_complete': user_doc.get('onboarding_complete', True),
                        'rejection_reason': user_doc.get('rejection_reason')
                    }
                }, 201

        except ValueError as e:
            # Invalid token (e.g. wrong audience, expired, or bad signature)
            err_msg = str(e)
            print(f"Google OAuth error: {err_msg}")
            return {'error': 'Invalid Google token', 'detail': err_msg}, 401
        except Exception as e:
            print(f"Google OAuth error: {str(e)}")
            return {'error': 'Failed to authenticate with Google'}, 500

    def delete_account(self, current_user):
        """Delete current user's account and related data"""
        try:
            user_id = current_user['_id']
            user_type = current_user.get('user_type')
            
            # Prevent admin self-deletion through this route for safety
            if user_type == 'admin':
                return {'error': 'Admin accounts cannot be deleted through this endpoint'}, 403

            # Hard delete the user
            self.users_collection.delete_one({'_id': ObjectId(user_id)})
            
            # Delete related data
            if user_type == 'candidate':
                # Delete candidate's applications and practice sessions
                applications_coll = self.users_collection.database['applications']
                practice_coll = self.users_collection.database.get('practice_sessions')
                applications_coll.delete_many({'student_id': str(user_id)})
                if practice_coll is not None:
                    practice_coll.delete_many({'user_id': str(user_id)})
            elif user_type == 'recruiter':
                # Delete recruiter's jobs and applications for those jobs
                jobs_coll = self.users_collection.database['jobs']
                applications_coll = self.users_collection.database['applications']
                recruiter_jobs = list(jobs_coll.find({'created_by': str(user_id)}, {'_id': 1}))
                job_ids = [str(job['_id']) for job in recruiter_jobs]
                if job_ids:
                    applications_coll.delete_many({'job_id': {'$in': job_ids}})
                jobs_coll.delete_many({'created_by': str(user_id)})
                
            return {'message': 'Account deleted successfully'}, 200
        except Exception as e:
            print(f"Error deleting account: {str(e)}")
            return {'error': 'Failed to delete account'}, 500
