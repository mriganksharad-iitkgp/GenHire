import datetime
from bson import ObjectId

class ProfileController:
    def __init__(self, db_collections):
        self.users_collection = db_collections['users']
        
    def get_profile(self, user_id):
        """Retrieve user profile data"""
        user = self.users_collection.find_one({'_id': ObjectId(user_id)})
        if not user:
            return {'error': 'User not found'}, 404
            
        profile_data = {
            'id': str(user['_id']),
            'name': user.get('name', ''),
            'email': user.get('email', ''),
            'phone': user.get('phone', ''),
            'location': user.get('location', ''),
            'title': user.get('title', ''),
            'about': user.get('about', ''),
            'skills': user.get('skills', []),
            'cv_path': user.get('cv_path', ''),
            'cv_details': user.get('cv_details', None),
            'profile_photo': user.get('profile_photo', ''),
            'user_type': user.get('user_type', 'candidate')
        }
        
        # Add company information for recruiters
        if user.get('user_type') == 'recruiter':
            profile_data.update({
                'company_name': user.get('company_name', ''),
                'company_logo': user.get('company_logo', ''),
                'company_description': user.get('company_description', ''),
                'company_website': user.get('company_website', ''),
                'company_size': user.get('company_size', ''),
                'company_industry': user.get('company_industry', ''),
                'company_location': user.get('company_location', '') or user.get('location', ''),
                'is_verified': user.get('is_verified', False),
                'rejection_reason': user.get('rejection_reason', None),
            })
        
        return profile_data, 200
        
    def update_profile(self, user_id, profile_data):
        """Update user profile information"""
        # Update fields that are provided
        update_fields = {}
        for field in ['name', 'phone', 'location', 'title', 'about', 'skills']:
            if field in profile_data:
                update_fields[field] = profile_data[field]
        
        if update_fields:
            update_fields['updated_at'] = datetime.datetime.utcnow()
            self.users_collection.update_one(
                {'_id': ObjectId(user_id)},
                {'$set': update_fields}
            )
        
        return {'message': 'Profile updated successfully'}, 200
        
    def update_company_profile(self, user_id, company_data):
        """Update recruiter company information"""
        user = self.users_collection.find_one({'_id': ObjectId(user_id)})
        if not user:
            return {'error': 'User not found'}, 404
            
        if user.get('user_type') != 'recruiter':
            return {'error': 'Unauthorized. Only recruiters can update company profile.'}, 403
        
        # Update company fields that are provided
        update_fields = {}
        for field in ['company_name', 'company_logo', 'company_description', 'company_website', 'company_size', 'company_industry', 'company_location']:
            if field in company_data:
                update_fields[field] = company_data[field]
        
        if update_fields:
            update_fields['updated_at'] = datetime.datetime.utcnow()
            self.users_collection.update_one(
                {'_id': ObjectId(user_id)},
                {'$set': update_fields}
            )
        
        return {'message': 'Company profile updated successfully'}, 200
        
    def get_cv_details(self, user_id):
        """Get CV details for the user"""
        user = self.users_collection.find_one({'_id': ObjectId(user_id)})
        if not user:
            return {'error': 'User not found'}, 404
            
        cv_details = user.get('cv_details', None)
        return {'cv_details': cv_details}, 200
        
    def update_cv_details(self, user_id, cv_data):
        """Update CV details for the user"""
        if not cv_data:
            return {'error': 'No CV details provided'}, 400
        
        # Update CV details
        self.users_collection.update_one(
            {'_id': ObjectId(user_id)},
            {'$set': {
                'cv_details': cv_data,
                'updated_at': datetime.datetime.utcnow()
            }}
        )
        
        return {'message': 'CV details updated successfully'}, 200
