import datetime
from functools import wraps
from flask import request, jsonify
import jwt as pyjwt
from bson import ObjectId
from config.database import db_config
from core.security import get_jwt_secret

_JWT_SECRET_KEY = get_jwt_secret()

# Fetch only the fields needed for auth — loading the full user document
# (which includes large cv_details, raw_cv_text, etc.) on every authenticated
# request/socket-connect adds unnecessary latency and BSON transfer overhead.
_AUTH_PROJECTION = {
    "_id": 1,
    "name": 1,
    "email": 1,
    "email_lower": 1,
    "user_type": 1,
    "is_verified": 1,
    "is_invite_only": 1,
    "invite_id_lower": 1,
    "invited_job_ids": 1,    # burner job scoping (jobs list/detail)
    "access_expires_at": 1,  # burner (invite-only) access window
    "permissions": 1,
    "cv_details": 1,   # needed by interview start route
    "is_active": 1,
}

INVITE_ACCESS_EXPIRED_MESSAGE = (
    "This invite access has expired. Ask the recruiter to re-send your invite."
)


def is_invite_access_expired(user) -> bool:
    """Burner (invite-only) accounts carry a recruiter-set `access_expires_at`;
    past that instant the candidate can no longer authenticate. The account and
    any completed interview results remain intact for the recruiter."""
    if not user or not user.get("is_invite_only"):
        return False
    expires_at = user.get("access_expires_at")
    if not expires_at:
        return False  # legacy burner without a window (migration backfills this)
    return expires_at < datetime.datetime.utcnow()


def decode_user_from_token(token):
    """
    Shared JWT decode + user lookup used by both the REST `token_required`
    decorator and the Socket.IO connect handler, so there is exactly one
    place that implements auth-token verification.

    Returns (current_user_dict, error_message_or_None).
    """
    if not token:
        return None, 'Token is missing!'

    if isinstance(token, str) and token.startswith('Bearer '):
        token = token[7:]

    try:
        data = pyjwt.decode(token, _JWT_SECRET_KEY, algorithms=['HS256'])

        collections = db_config.get_collections()
        current_user = collections['users'].find_one(
            {'_id': ObjectId(data['user_id'])},
            _AUTH_PROJECTION,
        )

        if not current_user:
            return None, 'User not found!'

        if is_invite_access_expired(current_user):
            return None, INVITE_ACCESS_EXPIRED_MESSAGE

        return current_user, None
    except pyjwt.ExpiredSignatureError:
        return None, 'Token has expired!'
    except pyjwt.InvalidTokenError:
        return None, 'Token is invalid!'
    except Exception:
        return None, 'Token is invalid!'


def token_required(f):
    """Decorator to require valid JWT token for a route"""
    @wraps(f)
    def decorated(*args, **kwargs):
        # Support Authorization header or token passed via query parameter (for new-tab file views)
        token = request.headers.get('Authorization') or request.args.get('token')

        current_user, error = decode_user_from_token(token)
        if error:
            status = 401
            return jsonify({'message': error}), status

        return f(current_user, *args, **kwargs)
    return decorated


def admin_required(f):
    """Decorator to require admin user type (must be used after token_required)"""
    @wraps(f)
    def decorated(current_user, *args, **kwargs):
        user_type = current_user.get('user_type', 'candidate')
        
        if user_type != 'admin':
            return jsonify({
                'message': 'Admin access required!',
                'error': 'unauthorized'
            }), 403
        
        return f(current_user, *args, **kwargs)
    return decorated


def verified_required(f):
    """Decorator to require verified recruiter status (must be used after token_required)
    
    This is for routes that require a verified recruiter, like posting jobs.
    Candidates and admins pass through automatically.
    """
    @wraps(f)
    def decorated(current_user, *args, **kwargs):
        user_type = current_user.get('user_type', 'candidate')
        
        # Admins and candidates pass through
        if user_type in ['admin', 'candidate']:
            return f(current_user, *args, **kwargs)
        
        # For recruiters, check verification status
        if user_type == 'recruiter':
            is_verified = current_user.get('is_verified', False)
            if not is_verified:
                return jsonify({
                    'message': 'Your recruiter account is pending verification. Please wait for admin approval.',
                    'error': 'verification_required',
                    'is_verified': False
                }), 403
            return f(current_user, *args, **kwargs)
            
        # Default fallback for unrecognized user types
        return jsonify({'error': 'Unauthorized user type.'}), 403
    return decorated


def permission_required(permission):
    """Decorator factory to require specific permission (must be used after token_required)
    
    Usage:
        @token_required
        @permission_required('users.write')
        def my_route(current_user):
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated(current_user, *args, **kwargs):
            user_permissions = current_user.get('permissions', [])
            
            # Super admin has all permissions
            if '*' in user_permissions:
                return f(current_user, *args, **kwargs)
            
            # Check if user has the specific permission
            if permission not in user_permissions:
                return jsonify({
                    'message': f'Permission denied. Required: {permission}',
                    'error': 'permission_denied',
                    'required_permission': permission
                }), 403
            
            return f(current_user, *args, **kwargs)
        return decorated
    return decorator


def recruiter_required(f):
    """Decorator to require recruiter or admin user type (must be used after token_required)"""
    @wraps(f)
    def decorated(current_user, *args, **kwargs):
        user_type = current_user.get('user_type', 'candidate')
        
        if user_type not in ['recruiter', 'admin']:
            return jsonify({
                'message': 'Recruiter access required!',
                'error': 'unauthorized'
            }), 403
        
        return f(current_user, *args, **kwargs)
    return decorated


def candidate_required(f):
    """Decorator to require candidate user type (must be used after token_required)"""
    @wraps(f)
    def decorated(current_user, *args, **kwargs):
        user_type = current_user.get('user_type', 'candidate')
        
        # Admins can also access candidate routes for testing/support
        if user_type not in ['candidate', 'admin']:
            return jsonify({
                'message': 'Candidate access required!',
                'error': 'unauthorized'
            }), 403
        
        return f(current_user, *args, **kwargs)
    return decorated
