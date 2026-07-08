#!/usr/bin/env python3
"""
Script to create a new Super Admin user
Usage: python create_super_admin.py
The script will prompt for email and password interactively.
"""

import os
import sys
import datetime
import re
import getpass
from pymongo import MongoClient
from werkzeug.security import generate_password_hash
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def validate_password(password: str) -> tuple[bool, str]:
    """
    Validate password meets security requirements:
    - Minimum 8 characters
    - At least 1 uppercase letter
    - At least 1 lowercase letter
    - At least 1 digit
    - At least 1 special character
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    
    if not re.search(r'\d', password):
        return False, "Password must contain at least one digit"
    
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, "Password must contain at least one special character (!@#$%^&*(),.?\":{}|<>)"
    
    return True, "Password is valid"

def create_super_admin(email: str = None, password: str = None, name: str = None):
    """
    Create a new super admin user with provided credentials
    """
    # Get MongoDB connection details
    mongodb_uri = os.getenv('MONGODB_URI')
    database_name = os.getenv('DATABASE_NAME', 'hrtech')
    
    if not mongodb_uri:
        print("[ERROR] MONGODB_URI not found in .env file")
        return False
    
    # Prompt for inputs if not provided
    if not email:
        email = input("Enter admin email: ").strip()
    
    if not email:
        print("[ERROR] Email is required")
        return False
    
    # Validate email format
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        print("[ERROR] Invalid email format")
        return False
    
    if not password:
        password = getpass.getpass("Enter admin password: ")
        confirm_password = getpass.getpass("Confirm password: ")
        
        if password != confirm_password:
            print("[ERROR] Passwords do not match")
            return False
    
    # Validate password
    is_valid, message = validate_password(password)
    if not is_valid:
        print(f"[ERROR] {message}")
        return False
    
    if not name:
        name = input("Enter admin name: ").strip()
        if not name:
            name = "Super Admin"
    
    print(f"\n[INFO] Connecting to MongoDB...")
    print(f"       Database: {database_name}")
    
    try:
        # Connect to MongoDB
        client = MongoClient(mongodb_uri)
        db = client[database_name]
        users_collection = db['users']
        
        # Test connection
        client.admin.command('ping')
        print("[OK] Connected to MongoDB successfully")
        
        # Check if email already exists
        print(f"\n[INFO] Checking if email already exists: {email}")
        existing_user = users_collection.find_one({'email': email})
        
        if existing_user:
            existing_type = existing_user.get('user_type', 'unknown')
            print(f"[ERROR] Email already exists as {existing_type}")
            print(f"        Name: {existing_user.get('name')}")
            print(f"        Email: {existing_user.get('email')}")
            
            if existing_type in ['candidate', 'recruiter']:
                print(f"\n[ERROR] Cannot create admin with same email as existing {existing_type}")
                print("[INFO] Please use a different email address for admin account")
                return False
            elif existing_type == 'admin':
                print("[INFO] User is already an admin")
                return False
        
        # Create new admin user
        print(f"\n[INFO] Creating Super Admin account...")
        
        admin_doc = {
            'name': name,
            'email': email,
            'password': generate_password_hash(password),
            'user_type': 'admin',
            'is_verified': True,
            'email_verified': True,
            'permissions': ['*'],  # Super admin has all permissions
            'verified_by': 'system',
            'verified_at': datetime.datetime.utcnow(),
            'rejection_reason': None,
            'auth_provider': 'local',
            'created_at': datetime.datetime.utcnow(),
            'updated_at': datetime.datetime.utcnow()
        }
        
        result = users_collection.insert_one(admin_doc)
        
        if result.inserted_id:
            print("[OK] Super Admin created successfully!")
            print("\n[INFO] Admin details:")
            print(f"       Name: {name}")
            print(f"       Email: {email}")
            print(f"       User Type: admin")
            print(f"       Permissions: ['*'] (All permissions)")
            print(f"\n[SUCCESS] You can now login at /login using the 'Admin' tab")
            print(f"          Email: {email}")
            print(f"          Password: [the password you entered]")
            return True
        else:
            print("[ERROR] Failed to create admin user")
            return False
                
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        return False
    finally:
        if 'client' in locals():
            client.close()
            print("\n[INFO] MongoDB connection closed")

if __name__ == "__main__":
    print("=" * 60)
    print("Super Admin Creation Tool")
    print("=" * 60)
    print("\nPassword Requirements:")
    print("  - Minimum 8 characters")
    print("  - At least 1 uppercase letter")
    print("  - At least 1 lowercase letter")
    print("  - At least 1 digit")
    print("  - At least 1 special character (!@#$%^&*(),.?\":{}|<>)")
    print("=" * 60)
    print()
    
    # Check for command line arguments
    email = sys.argv[1] if len(sys.argv) > 1 else None
    password = sys.argv[2] if len(sys.argv) > 2 else None
    name = sys.argv[3] if len(sys.argv) > 3 else None
    
    success = create_super_admin(email, password, name)
    sys.exit(0 if success else 1)
