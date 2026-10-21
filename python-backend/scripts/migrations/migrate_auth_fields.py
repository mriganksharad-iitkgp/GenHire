"""
Migration script to add email verification fields to existing users.

This script:
1. Adds email_verified=True to existing users (backward compatibility)
2. Adds auth_provider='local' to existing users
3. Does not modify user passwords or other fields

Run this once after deploying the new authentication features.
"""

import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from config.env_loader import load_environment
from pymongo import MongoClient
from datetime import datetime

# Load environment variables
load_environment(require_database=True)

def migrate_users():
    """Add new authentication fields to existing users"""
    
    # Connect to MongoDB
    mongo_uri = os.getenv('MONGODB_URI')
    db_name = os.getenv('DATABASE_NAME', 'hrtech')
    
    if not mongo_uri:
        print("❌ Error: MONGODB_URI not found in environment variables")
        return
    
    try:
        client = MongoClient(mongo_uri)
        db = client[db_name]
        users_collection = db['users']
        
        print("🔄 Starting user migration...")
        print(f"📊 Database: {db_name}")
        
        # Find users that don't have the new fields
        users_to_update = users_collection.find({
            '$or': [
                {'email_verified': {'$exists': False}},
                {'auth_provider': {'$exists': False}}
            ]
        })
        
        count = 0
        for user in users_to_update:
            update_fields = {
                'updated_at': datetime.utcnow()
            }
            
            # Add email_verified if missing (set to True for backward compatibility)
            if 'email_verified' not in user:
                update_fields['email_verified'] = True
            
            # Add auth_provider if missing
            if 'auth_provider' not in user:
                update_fields['auth_provider'] = 'local'
            
            # Update the user
            users_collection.update_one(
                {'_id': user['_id']},
                {'$set': update_fields}
            )
            count += 1
            print(f"✅ Updated user: {user.get('email', 'N/A')}")
        
        print(f"\n✨ Migration completed successfully!")
        print(f"📊 Total users updated: {count}")
        
        # Show summary
        total_users = users_collection.count_documents({})
        verified_users = users_collection.count_documents({'email_verified': True})
        local_auth_users = users_collection.count_documents({'auth_provider': 'local'})
        google_auth_users = users_collection.count_documents({'auth_provider': 'google'})
        
        print("\n📈 Database Summary:")
        print(f"   Total users: {total_users}")
        print(f"   Verified users: {verified_users}")
        print(f"   Local auth users: {local_auth_users}")
        print(f"   Google auth users: {google_auth_users}")
        
        client.close()
        
    except Exception as e:
        print(f"❌ Error during migration: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    print("=" * 60)
    print("User Migration Script - Authentication Features")
    print("=" * 60)
    print()
    
    response = input("⚠️  This will update existing user records. Continue? (yes/no): ")
    
    if response.lower() in ['yes', 'y']:
        migrate_users()
    else:
        print("❌ Migration cancelled")

