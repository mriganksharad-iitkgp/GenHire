"""
Migration script for admin system and recruiter verification.

This script:
1. Adds 'is_verified: True' to all existing recruiters (grandfather them in)
2. Adds 'permissions: []' to all existing users
3. Adds verification-related fields to users that don't have them

Run this script once after deploying the admin system update.

Usage:
    python migrate_admin_system.py
"""

import os
import sys
import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.database import db_config


def migrate_users():
    """Add admin system fields to existing users"""
    
    print("=" * 60)
    print("Admin System Migration")
    print("=" * 60)
    
    # Connect to database
    db_config.connect()
    collections = db_config.get_collections()
    users_collection = collections['users']
    
    # Get all users
    all_users = list(users_collection.find({}))
    print(f"\nFound {len(all_users)} users to migrate")
    
    migrated_count = 0
    skipped_count = 0
    
    for user in all_users:
        user_id = user['_id']
        user_type = user.get('user_type', 'candidate')
        needs_update = False
        update_fields = {}
        
        # Check if is_verified field exists
        if 'is_verified' not in user:
            needs_update = True
            # Grandfather in existing recruiters as verified
            update_fields['is_verified'] = True
            
        # Check if permissions field exists
        if 'permissions' not in user:
            needs_update = True
            update_fields['permissions'] = []
            
        # Check if verified_by field exists
        if 'verified_by' not in user:
            needs_update = True
            update_fields['verified_by'] = None
            
        # Check if verified_at field exists
        if 'verified_at' not in user:
            needs_update = True
            # For existing verified users, set verified_at to their creation date
            update_fields['verified_at'] = user.get('created_at', datetime.datetime.utcnow())
            
        # Check if rejection_reason field exists
        if 'rejection_reason' not in user:
            needs_update = True
            update_fields['rejection_reason'] = None
        
        if needs_update:
            update_fields['updated_at'] = datetime.datetime.utcnow()
            
            users_collection.update_one(
                {'_id': user_id},
                {'$set': update_fields}
            )
            
            print(f"  ✓ Migrated: {user.get('email')} ({user_type})")
            migrated_count += 1
        else:
            skipped_count += 1
    
    print(f"\n" + "=" * 60)
    print(f"Migration Complete!")
    print(f"  - Migrated: {migrated_count} users")
    print(f"  - Skipped (already migrated): {skipped_count} users")
    print("=" * 60)
    
    # Show summary by user type
    print("\nUser Summary:")
    candidates = users_collection.count_documents({'user_type': 'candidate'})
    recruiters = users_collection.count_documents({'user_type': 'recruiter'})
    admins = users_collection.count_documents({'user_type': 'admin'})
    verified_recruiters = users_collection.count_documents({'user_type': 'recruiter', 'is_verified': True})
    pending_recruiters = users_collection.count_documents({'user_type': 'recruiter', 'is_verified': False})
    
    print(f"  - Candidates: {candidates}")
    print(f"  - Recruiters: {recruiters} (verified: {verified_recruiters}, pending: {pending_recruiters})")
    print(f"  - Admins: {admins}")


def create_super_admin_instructions():
    """Print instructions for creating a super admin"""
    
    print("\n" + "=" * 60)
    print("Super Admin Creation Instructions")
    print("=" * 60)
    print("""
To create a super admin account, run this in MongoDB shell or Compass:

// First, generate a password hash using Python:
// python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('YOUR_PASSWORD'))"

db.users.insertOne({
    name: "Super Admin",
    email: "admin@yourdomain.com",
    password: "<paste_hashed_password_here>",
    user_type: "admin",
    is_verified: true,
    email_verified: true,
    permissions: ["*"],
    verified_by: null,
    verified_at: new Date(),
    rejection_reason: null,
    auth_provider: "local",
    created_at: new Date(),
    updated_at: new Date()
})

Or use this Python snippet:

from werkzeug.security import generate_password_hash
from config.database import db_config
import datetime

db_config.connect()
collections = db_config.get_collections()

admin_doc = {
    'name': 'Super Admin',
    'email': 'admin@yourdomain.com',
    'password': generate_password_hash('your_secure_password'),
    'user_type': 'admin',
    'is_verified': True,
    'email_verified': True,
    'permissions': ['*'],
    'verified_by': None,
    'verified_at': datetime.datetime.utcnow(),
    'rejection_reason': None,
    'auth_provider': 'local',
    'created_at': datetime.datetime.utcnow(),
    'updated_at': datetime.datetime.utcnow()
}

result = collections['users'].insert_one(admin_doc)
print(f"Super admin created with ID: {result.inserted_id}")
""")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Migrate users for admin system')
    parser.add_argument('--instructions', action='store_true', 
                        help='Show super admin creation instructions')
    parser.add_argument('--migrate', action='store_true',
                        help='Run the migration')
    
    args = parser.parse_args()
    
    if args.instructions:
        create_super_admin_instructions()
    elif args.migrate:
        migrate_users()
        create_super_admin_instructions()
    else:
        print("Usage:")
        print("  python migrate_admin_system.py --migrate      # Run migration")
        print("  python migrate_admin_system.py --instructions # Show admin creation instructions")
