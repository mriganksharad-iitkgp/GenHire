import datetime
from bson import ObjectId
from models.user import AVAILABLE_PERMISSIONS


class AdminController:
    def __init__(self, db_collections):
        self.users_collection = db_collections['users']
        self.jobs_collection = db_collections['jobs']
        self.applications_collection = db_collections['applications']
    
    def get_dashboard_stats(self, current_user):
        """Get platform statistics for admin dashboard"""
        try:
            # Count users by type
            total_candidates = self.users_collection.count_documents({'user_type': 'candidate'})
            total_recruiters = self.users_collection.count_documents({'user_type': 'recruiter'})
            total_admins = self.users_collection.count_documents({'user_type': 'admin'})
            
            # Pending recruiter verifications
            pending_verifications = self.users_collection.count_documents({
                'user_type': 'recruiter',
                'is_verified': False
            })
            
            # Verified recruiters
            verified_recruiters = self.users_collection.count_documents({
                'user_type': 'recruiter',
                'is_verified': True
            })
            
            # Job statistics
            total_jobs = self.jobs_collection.count_documents({})
            active_jobs = self.jobs_collection.count_documents({'status': {'$in': ['active', 'open', None]}})
            
            # Application statistics
            total_applications = self.applications_collection.count_documents({})
            
            # Recent activity - users registered in last 7 days
            seven_days_ago = datetime.datetime.utcnow() - datetime.timedelta(days=7)
            new_users_week = self.users_collection.count_documents({
                'created_at': {'$gte': seven_days_ago}
            })
            
            return {
                'users': {
                    'total': total_candidates + total_recruiters + total_admins,
                    'candidates': total_candidates,
                    'recruiters': total_recruiters,
                    'admins': total_admins,
                    'new_this_week': new_users_week
                },
                'recruiters': {
                    'total': total_recruiters,
                    'verified': verified_recruiters,
                    'pending_verification': pending_verifications
                },
                'jobs': {
                    'total': total_jobs,
                    'active': active_jobs
                },
                'applications': {
                    'total': total_applications
                }
            }, 200
        except Exception as e:
            print(f"Error getting dashboard stats: {str(e)}")
            return {'error': 'Failed to get dashboard statistics'}, 500
    
    def get_users(self, current_user, filters=None):
        """Get list of users with optional filters and pagination"""
        try:
            filters = filters or {}
            
            # Build query
            query = {}
            
            # Filter by user type
            if filters.get('user_type'):
                query['user_type'] = filters['user_type']
            
            # Filter by verification status
            if filters.get('is_verified') is not None:
                query['is_verified'] = filters['is_verified']
            
            # Search by name or email
            if filters.get('search'):
                search_term = filters['search']
                query['$or'] = [
                    {'name': {'$regex': search_term, '$options': 'i'}},
                    {'email': {'$regex': search_term, '$options': 'i'}},
                    {'company_name': {'$regex': search_term, '$options': 'i'}}
                ]
            
            # Pagination
            page = int(filters.get('page', 1))
            limit = int(filters.get('limit', 20))
            skip = (page - 1) * limit
            
            # Get total count for pagination
            total_count = self.users_collection.count_documents(query)
            
            # Get users with sorting (newest first)
            users_cursor = self.users_collection.find(query).sort('created_at', -1).skip(skip).limit(limit)
            
            users = []
            for user in users_cursor:
                users.append({
                    'id': str(user['_id']),
                    'name': user.get('name', ''),
                    'email': user.get('email', ''),
                    'user_type': user.get('user_type', 'candidate'),
                    'is_verified': user.get('is_verified', True),
                    'email_verified': user.get('email_verified', False),
                    'permissions': user.get('permissions', []),
                    'company_name': user.get('company_name'),
                    'company_industry': user.get('company_industry'),
                    'created_at': user.get('created_at').isoformat() if user.get('created_at') else None,
                    'verified_at': user.get('verified_at').isoformat() if user.get('verified_at') else None,
                    'auth_provider': user.get('auth_provider', 'local')
                })
            
            return {
                'users': users,
                'pagination': {
                    'page': page,
                    'limit': limit,
                    'total': total_count,
                    'total_pages': (total_count + limit - 1) // limit
                }
            }, 200
        except Exception as e:
            print(f"Error getting users: {str(e)}")
            return {'error': 'Failed to get users'}, 500
    
    def get_pending_recruiters(self, current_user):
        """Get list of recruiters pending verification"""
        try:
            query = {
                'user_type': 'recruiter',
                'is_verified': False
            }
            
            recruiters_cursor = self.users_collection.find(query).sort('created_at', -1)
            
            recruiters = []
            for recruiter in recruiters_cursor:
                recruiters.append({
                    'id': str(recruiter['_id']),
                    'name': recruiter.get('name', ''),
                    'email': recruiter.get('email', ''),
                    'phone': recruiter.get('phone'),
                    'company_name': recruiter.get('company_name', ''),
                    'company_description': recruiter.get('company_description', ''),
                    'company_website': recruiter.get('company_website'),
                    'company_industry': recruiter.get('company_industry', ''),
                    'company_size': recruiter.get('company_size'),
                    'company_location': recruiter.get('location') or recruiter.get('company_location', ''),
                    'reason_for_joining': recruiter.get('reason_for_joining', ''),
                    'linkedin_profile': recruiter.get('linkedin_profile', ''),
                    'email_verified': recruiter.get('email_verified', False),
                    'created_at': recruiter.get('created_at').isoformat() if recruiter.get('created_at') else None,
                    'auth_provider': recruiter.get('auth_provider', 'local')
                })
            
            return {
                'pending_recruiters': recruiters,
                'count': len(recruiters)
            }, 200
        except Exception as e:
            print(f"Error getting pending recruiters: {str(e)}")
            return {'error': 'Failed to get pending recruiters'}, 500
    
    def get_user_details(self, current_user, user_id):
        """Get detailed information about a specific user"""
        try:
            user = self.users_collection.find_one({'_id': ObjectId(user_id)})
            
            if not user:
                return {'error': 'User not found'}, 404
            
            # Get additional stats for the user
            user_stats = {}
            
            if user.get('user_type') == 'candidate':
                # Count applications
                user_stats['applications_count'] = self.applications_collection.count_documents({
                    'candidate_id': str(user['_id'])
                })
            elif user.get('user_type') == 'recruiter':
                # Count jobs posted
                user_stats['jobs_posted'] = self.jobs_collection.count_documents({
                    'recruiter_id': str(user['_id'])
                })
                user_stats['total_applications'] = self.applications_collection.count_documents({
                    'job_id': {'$in': [str(job['_id']) for job in self.jobs_collection.find({'recruiter_id': str(user['_id'])}, {'_id': 1})]}
                })
            
            return {
                'user': {
                    'id': str(user['_id']),
                    'name': user.get('name', ''),
                    'email': user.get('email', ''),
                    'user_type': user.get('user_type', 'candidate'),
                    'phone': user.get('phone'),
                    'location': user.get('location'),
                    'title': user.get('title'),
                    'about': user.get('about'),
                    'is_verified': user.get('is_verified', True),
                    'email_verified': user.get('email_verified', False),
                    'permissions': user.get('permissions', []),
                    'company_name': user.get('company_name'),
                    'company_description': user.get('company_description'),
                    'company_website': user.get('company_website'),
                    'company_industry': user.get('company_industry'),
                    'company_size': user.get('company_size'),
                    'created_at': user.get('created_at').isoformat() if user.get('created_at') else None,
                    'updated_at': user.get('updated_at').isoformat() if user.get('updated_at') else None,
                    'verified_at': user.get('verified_at').isoformat() if user.get('verified_at') else None,
                    'verified_by': user.get('verified_by'),
                    'auth_provider': user.get('auth_provider', 'local')
                },
                'stats': user_stats
            }, 200
        except Exception as e:
            print(f"Error getting user details: {str(e)}")
            return {'error': 'Failed to get user details'}, 500
    
    def verify_recruiter(self, current_user, recruiter_id):
        """Verify a recruiter account"""
        try:
            recruiter = self.users_collection.find_one({'_id': ObjectId(recruiter_id)})
            
            if not recruiter:
                return {'error': 'Recruiter not found'}, 404
            
            if recruiter.get('user_type') != 'recruiter':
                return {'error': 'User is not a recruiter'}, 400
            
            if recruiter.get('is_verified', False):
                return {'error': 'Recruiter is already verified'}, 400
            
            # Update verification status
            self.users_collection.update_one(
                {'_id': ObjectId(recruiter_id)},
                {
                    '$set': {
                        'is_verified': True,
                        'verified_by': str(current_user['_id']),
                        'verified_at': datetime.datetime.utcnow(),
                        'updated_at': datetime.datetime.utcnow(),
                        'rejection_reason': None  # Clear any previous rejection reason
                    }
                }
            )
            
            return {
                'message': f'Recruiter {recruiter.get("name")} has been verified successfully',
                'recruiter_id': recruiter_id
            }, 200
        except Exception as e:
            print(f"Error verifying recruiter: {str(e)}")
            return {'error': 'Failed to verify recruiter'}, 500
    
    def reject_recruiter(self, current_user, recruiter_id, reason=None):
        """Reject/suspend a recruiter account"""
        try:
            recruiter = self.users_collection.find_one({'_id': ObjectId(recruiter_id)})
            
            if not recruiter:
                return {'error': 'Recruiter not found'}, 404
            
            if recruiter.get('user_type') != 'recruiter':
                return {'error': 'User is not a recruiter'}, 400
            
            # Update to unverified status with rejection reason
            self.users_collection.update_one(
                {'_id': ObjectId(recruiter_id)},
                {
                    '$set': {
                        'is_verified': False,
                        'rejection_reason': reason or 'Account verification rejected by admin',
                        'updated_at': datetime.datetime.utcnow()
                    }
                }
            )
            
            return {
                'message': f'Recruiter {recruiter.get("name")} has been rejected',
                'recruiter_id': recruiter_id
            }, 200
        except Exception as e:
            print(f"Error rejecting recruiter: {str(e)}")
            return {'error': 'Failed to reject recruiter'}, 500
    
    def update_user_permissions(self, current_user, user_id, permissions):
        """Update user permissions (and promote to admin if granting admin-level permissions)"""
        try:
            user = self.users_collection.find_one({'_id': ObjectId(user_id)})
            
            if not user:
                return {'error': 'User not found'}, 404
            
            # Validate permissions
            invalid_permissions = [p for p in permissions if p not in AVAILABLE_PERMISSIONS]
            if invalid_permissions:
                return {
                    'error': f'Invalid permissions: {", ".join(invalid_permissions)}',
                    'available_permissions': AVAILABLE_PERMISSIONS
                }, 400
            
            # Check if granting admin-level permissions (*, or any permission)
            has_admin_permissions = len(permissions) > 0
            is_super_admin = '*' in permissions
            
            # Only allow granting admin permissions to candidates, not recruiters
            if has_admin_permissions and user.get('user_type') == 'recruiter':
                return {
                    'error': 'Cannot grant admin permissions to recruiter accounts. Only candidates can be promoted to admin.',
                    'user_type': user.get('user_type')
                }, 400
            
            # Build update data
            update_data = {
                'permissions': permissions,
                'updated_at': datetime.datetime.utcnow()
            }
            
            # If granting any permissions, promote user to admin
            if has_admin_permissions and user.get('user_type') == 'candidate':
                update_data['user_type'] = 'admin'
                update_data['is_verified'] = True
                new_role = 'admin'
            elif not has_admin_permissions and user.get('user_type') == 'admin':
                # If removing all permissions from admin, demote back to candidate
                update_data['user_type'] = 'candidate'
                new_role = 'candidate'
            else:
                new_role = user.get('user_type')
            
            # Update user
            self.users_collection.update_one(
                {'_id': ObjectId(user_id)},
                {'$set': update_data}
            )
            
            return {
                'message': f'Permissions updated for {user.get("name")}',
                'user_id': user_id,
                'permissions': permissions,
                'user_type': new_role,
                'promoted': new_role != user.get('user_type')
            }, 200
        except Exception as e:
            print(f"Error updating permissions: {str(e)}")
            return {'error': 'Failed to update permissions'}, 500
    
    def update_user_type(self, current_user, user_id, new_user_type):
        """Update user type (promote/demote users)"""
        try:
            user = self.users_collection.find_one({'_id': ObjectId(user_id)})
            
            if not user:
                return {'error': 'User not found'}, 404
            
            # Validate user type
            if new_user_type not in ['candidate', 'recruiter', 'admin']:
                return {'error': 'Invalid user type'}, 400
            
            # Prevent demoting self
            if str(user['_id']) == str(current_user['_id']) and new_user_type != 'admin':
                return {'error': 'Cannot demote yourself'}, 400
            
            # Prevent promoting recruiters to admin - only candidates can become admins
            if new_user_type == 'admin' and user.get('user_type') == 'recruiter':
                return {
                    'error': 'Recruiters cannot be promoted to admin. Only candidates can become admins.',
                    'current_type': user.get('user_type')
                }, 400
            
            update_data = {
                'user_type': new_user_type,
                'updated_at': datetime.datetime.utcnow()
            }
            
            # Auto-verify if promoting to admin
            if new_user_type == 'admin':
                update_data['is_verified'] = True
                update_data['permissions'] = ['*']  # Give all permissions to new admin
            
            # If demoting admin to candidate, clear permissions
            if new_user_type == 'candidate' and user.get('user_type') == 'admin':
                update_data['permissions'] = []
            
            self.users_collection.update_one(
                {'_id': ObjectId(user_id)},
                {'$set': update_data}
            )
            
            return {
                'message': f'User {user.get("name")} is now a {new_user_type}',
                'user_id': user_id,
                'new_user_type': new_user_type
            }, 200
        except Exception as e:
            print(f"Error updating user type: {str(e)}")
            return {'error': 'Failed to update user type'}, 500
    
    def get_available_permissions(self, current_user):
        """Get list of available permissions"""
        return {
            'permissions': AVAILABLE_PERMISSIONS
        }, 200
    
    def delete_user(self, current_user, user_id):
        """Delete a user account (soft delete or hard delete)"""
        try:
            user = self.users_collection.find_one({'_id': ObjectId(user_id)})
            
            if not user:
                return {'error': 'User not found'}, 404
            
            # Prevent deleting self
            if str(user['_id']) == str(current_user['_id']):
                return {'error': 'Cannot delete your own account'}, 400
            
            # Prevent deleting other admins (only super admin with '*' permission can)
            if user.get('user_type') == 'admin':
                if '*' not in current_user.get('permissions', []):
                    return {'error': 'Only super admins can delete other admin accounts'}, 403
            
            # Hard delete the user
            self.users_collection.delete_one({'_id': ObjectId(user_id)})
            
            return {
                'message': f'User {user.get("name")} has been deleted',
                'user_id': user_id
            }, 200
        except Exception as e:
            print(f"Error deleting user: {str(e)}")
            return {'error': 'Failed to delete user'}, 500
