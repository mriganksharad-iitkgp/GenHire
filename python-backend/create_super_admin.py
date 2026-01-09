#!/usr/bin/env python3
"""
Script to create or promote a user to Super Admin
Usage: python create_super_admin.py [email]
If no email provided, defaults to roshan643yadav@gmail.com
"""

import os
import sys
import datetime
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def create_super_admin(email: str = "roshan643yadav@gmail.com"):
    """
    Find a user by email and promote them to super admin
    """
    # Get MongoDB connection details
    mongodb_uri = os.getenv('MONGODB_URI')
    database_name = os.getenv('DATABASE_NAME', 'hrtech')
    
    if not mongodb_uri:
        print("[ERROR] MONGODB_URI not found in .env file")
        return False
    
    print(f"[INFO] Connecting to MongoDB...")
    print(f"       Database: {database_name}")
    
    try:
        # Connect to MongoDB
        client = MongoClient(mongodb_uri)
        db = client[database_name]
        users_collection = db['users']
        
        # Test connection
        client.admin.command('ping')
        print("[OK] Connected to MongoDB successfully")
        
        # Find the user
        print(f"\n[INFO] Searching for user: {email}")
        user = users_collection.find_one({'email': email})
        
        if not user:
            print(f"[ERROR] User with email '{email}' not found")
            print("\n[INFO] Available users in database:")
            all_users = list(users_collection.find({}, {'email': 1, 'name': 1, 'user_type': 1}))
            for u in all_users[:10]:  # Show first 10 users
                print(f"   - {u.get('email')} ({u.get('name')}) - {u.get('user_type')}")
            if len(all_users) > 10:
                print(f"   ... and {len(all_users) - 10} more users")
            return False
        
        print(f"[OK] Found user: {user.get('name')} ({user.get('email')})")
        print(f"     Current user_type: {user.get('user_type')}")
        print(f"     Current is_verified: {user.get('is_verified', 'not set')}")
        print(f"     Current permissions: {user.get('permissions', [])}")
        
        # Update user to super admin
        print(f"\n[INFO] Promoting user to Super Admin...")
        
        update_result = users_collection.update_one(
            {'_id': user['_id']},
            {
                '$set': {
                    'user_type': 'admin',
                    'is_verified': True,
                    'permissions': ['*'],  # Super admin has all permissions
                    'verified_by': 'system',
                    'verified_at': datetime.datetime.utcnow(),
                    'updated_at': datetime.datetime.utcnow()
                }
            }
        )
        
        if update_result.modified_count > 0:
            print("[OK] User successfully promoted to Super Admin!")
            print("\n[INFO] Updated user details:")
            updated_user = users_collection.find_one({'_id': user['_id']})
            print(f"       Name: {updated_user.get('name')}")
            print(f"       Email: {updated_user.get('email')}")
            print(f"       User Type: {updated_user.get('user_type')}")
            print(f"       Is Verified: {updated_user.get('is_verified')}")
            print(f"       Permissions: {updated_user.get('permissions')}")
            print(f"\n[SUCCESS] You can now login as admin at /login and select 'Admin' tab")
            return True
        else:
            # Check if already an admin
            if user.get('user_type') == 'admin' and user.get('permissions') == ['*']:
                print("[INFO] User is already a Super Admin!")
                return True
            else:
                print("[WARN] No changes made. User may already have these settings.")
                return False
                
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        return False
    finally:
        if 'client' in locals():
            client.close()
            print("\n[INFO] MongoDB connection closed")

if __name__ == "__main__":
    email = sys.argv[1] if len(sys.argv) > 1 else "roshan643yadav@gmail.com"
    success = create_super_admin(email)
    sys.exit(0 if success else 1)
