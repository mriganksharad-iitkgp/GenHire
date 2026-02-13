from werkzeug.security import generate_password_hash, check_password_hash
import jwt as pyjwt
import datetime
import os
from bson import ObjectId
import secrets
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from services.email_service import EmailService

class AuthController:
    def __init__(self, db_collections):
        self.users_collection = db_collections['users']
        self.secret_key = os.getenv('JWT_SECRET_KEY', 'your-secret-key-here')
        self.google_client_id = os.getenv('GOOGLE_CLIENT_ID')
        self.email_service = EmailService()
        self.require_email_verification = os.getenv('REQUIRE_EMAIL_VERIFICATION', 'true').lower() == 'true'
        
    def register_user(self, user_data):
        """Register a new user"""
        name = user_data.get('name')
        email = user_data.get('email')
        password = user_data.get('password')
        confirm_password = user_data.get('confirmPassword')
        user_type = user_data.get('userType', 'candidate')

        # Validation
        if not all([name, email, password, confirm_password]):
            return {'error': 'All fields are required'}, 400
        
        if password != confirm_password:
            return {'error': 'Passwords do not match'}, 400
        
        # Only allow candidate and recruiter registration (admins created manually)
        if user_type not in ['candidate', 'recruiter']:
            return {'error': 'Invalid user type'}, 400
        
        # Check if user exists
        if self.users_collection.find_one({'email': email}):
            return {'error': 'Email already exists'}, 400
        
        # Generate verification token
        verification_token = secrets.token_urlsafe(32)
        
        # Determine verification status:
        # - Candidates are auto-verified (is_verified: True)
        # - Recruiters need admin approval (is_verified: False)
        is_verified = True if user_type == 'candidate' else False
        
        # Create new user
        user_doc = {
            'name': name,
            'email': email,
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
                'linkedin_profile': user_data.get('linkedinProfile') or user_data.get('linkedin_profile', '')
            })
        
        user_id = self.users_collection.insert_one(user_doc).inserted_id
        
        # Send verification email if required
        if self.require_email_verification:
            try:
                self.email_service.send_verification_email(email, verification_token, name)
            except Exception as e:
                print(f"Error sending verification email: {str(e)}")
                # Continue registration even if email fails
        
        # Generate token (but user may need to verify email before full access)
        token = self.generate_token(user_id)
        
        response_message = 'User registered successfully'
        if self.require_email_verification:
            response_message += '. Please check your email to verify your HR Tech account.'
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
                'email': email,
                'user_type': user_type,
                'email_verified': user_doc['email_verified'],
                'is_verified': is_verified,
                'permissions': []
            }
        }, 201
        
    def login_user(self, email, password, user_type):
        """Authenticate user and return token"""
        if not email or not password:
            return {'error': 'Email and password are required'}, 400
        
        # Support candidate, recruiter, and admin login
        if user_type not in ['candidate', 'recruiter', 'admin']:
            return {'error': 'Invalid credentials'}, 401
        
        user = self.users_collection.find_one({'email': email})
        
        if not user or not check_password_hash(user['password'], password):
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
                    'error': 'Please verify your email before logging in to your HR Tech account',
                    'email_verification_required': True
                }, 403
        
        # Get verification status (relevant for recruiters and admins)
        is_verified = user.get('is_verified', True)
        
        # Generate token
        token = self.generate_token(user['_id'])
        
        return {
            'message': 'Logged in successfully',
            'token': token,
            'user': {
                'id': str(user['_id']),
                'name': user['name'],
                'email': user['email'],
                'user_type': stored_user_type,
                'email_verified': user.get('email_verified', False),
                'is_verified': is_verified,
                'permissions': user.get('permissions', [])
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
            'name': user['name'],
            'email': user['email'],
            'user_type': user.get('user_type', 'candidate'),
            'email_verified': user.get('email_verified', False),
            'auth_provider': user.get('auth_provider', 'local'),
            'is_verified': user.get('is_verified', True),
            'permissions': user.get('permissions', [])
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
        user = self.users_collection.find_one({'email': email})
        
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
            self.email_service.send_verification_email(email, verification_token, user['name'])
            return {'message': 'Verification email sent successfully'}, 200
        except Exception as e:
            print(f"Error sending verification email: {str(e)}")
            return {'error': 'Failed to send verification email'}, 500
    
    def request_password_reset(self, email):
        """Send password reset email to user"""
        user = self.users_collection.find_one({'email': email})
        
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
            self.email_service.send_password_reset_email(email, reset_token, user['name'])
        except Exception as e:
            print(f"Error sending password reset email: {str(e)}")
        
        return {'message': 'If your email is registered, you will receive a password reset link'}, 200
    
    def reset_password(self, token, new_password, confirm_password):
        """Reset user password using reset token"""
        if not new_password or not confirm_password:
            return {'error': 'Password and confirmation are required'}, 400
        
        if new_password != confirm_password:
            return {'error': 'Passwords do not match'}, 400
        
        # Validate password strength (basic validation)
        if len(new_password) < 6:
            return {'error': 'Password must be at least 6 characters long'}, 400
        
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
        
        try:
            # Verify the token with Google (allow 10s clock skew for "Token used too early")
            idinfo = id_token.verify_oauth2_token(
                token,
                google_requests.Request(),
                self.google_client_id,
                clock_skew_in_seconds=10
            )

            # Get user info from token
            email = idinfo.get('email')
            name = idinfo.get('name')
            google_id = idinfo.get('sub')

            if not email:
                return {'error': 'Email not provided by Google'}, 400

            # Check if user exists
            user = self.users_collection.find_one({'email': email})

            if user:
                # Update existing user if they signed up with local auth
                if user.get('auth_provider') != 'google':
                    self.users_collection.update_one(
                        {'_id': user['_id']},
                        {
                            '$set': {
                                'auth_provider': 'google',
                                'google_id': google_id,
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
                        'permissions': user.get('permissions', [])
                    }
                }, 200
            else:
                # Determine verification status for new users
                # Candidates are auto-verified, recruiters need admin approval
                is_verified = True if user_type == 'candidate' else False

                # Create new user with Google OAuth
                user_doc = {
                    'name': name,
                    'email': email,
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
                        'linkedin_profile': user_data.get('linkedinProfile') or user_data.get('linkedin_profile', '')
                    })
                
                user_id = self.users_collection.insert_one(user_doc).inserted_id
                
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
                        'permissions': []
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
