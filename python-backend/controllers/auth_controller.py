from werkzeug.security import generate_password_hash, check_password_hash
import jwt as pyjwt
import datetime
import os
from bson import ObjectId

class AuthController:
    def __init__(self, db_collections):
        self.users_collection = db_collections['users']
        self.secret_key = os.getenv('JWT_SECRET_KEY', 'your-secret-key-here')
        
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
        
        if user_type not in ['candidate', 'recruiter']:
            return {'error': 'Invalid user type'}, 400
        
        # Check if user exists
        if self.users_collection.find_one({'email': email}):
            return {'error': 'Email already exists'}, 400
        
        # Create new user
        user_doc = {
            'name': name,
            'email': email,
            'password': generate_password_hash(password),
            'user_type': user_type,
            'created_at': datetime.datetime.utcnow(),
            'updated_at': datetime.datetime.utcnow()
        }
        
        # Add default company information for recruiters
        if user_type == 'recruiter':
            user_doc.update({
                'company_name': user_data.get('company_name', 'TechCorp Solutions'),
                'company_logo': user_data.get('company_logo', None),
                'company_description': user_data.get('company_description', 'A leading technology company focused on innovation.'),
                'company_website': user_data.get('company_website', None),
                'company_size': user_data.get('company_size', None),
                'company_industry': user_data.get('company_industry', 'Technology')
            })
        
        user_id = self.users_collection.insert_one(user_doc).inserted_id
        
        # Generate token
        token = self.generate_token(user_id)
        
        return {
            'message': 'User registered successfully',
            'token': token,
            'user': {
                'id': str(user_id),
                'name': name,
                'email': email,
                'user_type': user_type
            }
        }, 201
        
    def login_user(self, email, password, user_type):
        """Authenticate user and return token"""
        if not email or not password:
            return {'error': 'Email and password are required'}, 400
        
        if user_type not in ['candidate', 'recruiter']:
            return {'error': 'Invalid user type'}, 400
        
        user = self.users_collection.find_one({'email': email})
        
        if not user or not check_password_hash(user['password'], password):
            return {'error': 'Invalid credentials'}, 401
        
        # Check if user type matches
        stored_user_type = user.get('user_type', 'candidate')
        if stored_user_type != user_type:
            return {'error': f'Please login as {stored_user_type}'}, 401
        
        # Generate token
        token = self.generate_token(user['_id'])
        
        return {
            'message': 'Logged in successfully',
            'token': token,
            'user': {
                'id': str(user['_id']),
                'name': user['name'],
                'email': user['email'],
                'user_type': stored_user_type
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
            'user_type': user.get('user_type', 'candidate')
        }
