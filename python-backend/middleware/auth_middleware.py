from functools import wraps
from flask import request, jsonify
import jwt as pyjwt
import os
from bson import ObjectId
from config.database import db_config

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        # Support Authorization header or token passed via query parameter (for new-tab file views)
        token = request.headers.get('Authorization') or request.args.get('token')

        if not token:
            return jsonify({'message': 'Token is missing!'}), 401

        try:
            # Check for the "Bearer " prefix and remove it if it exists.
            if isinstance(token, str) and token.startswith('Bearer '):
                token = token[7:]

            secret_key = os.getenv('JWT_SECRET_KEY', 'your-secret-key-here')
            data = pyjwt.decode(token, secret_key, algorithms=['HS256'])
            
            # Get database collections
            collections = db_config.get_collections()
            current_user = collections['users'].find_one({'_id': ObjectId(data['user_id'])})

            if not current_user:
                return jsonify({'message': 'User not found!'}), 401

        except pyjwt.ExpiredSignatureError:
            return jsonify({'message': 'Token has expired!'}), 401
        except pyjwt.InvalidTokenError:
            return jsonify({'message': 'Token is invalid!'}), 401

        return f(current_user, *args, **kwargs)
    return decorated
