"""Seed the throw-away E2E database with one admin account.

There is no admin signup in the product (admins come from
python-backend/scripts/admin/create_super_admin.py, which is interactive), so
this inserts the same document that script creates. It runs with the backend's
own virtualenv so the password hash format matches what the login code checks.

Usage: seed_admin.py <mongo_uri> <db_name> <email> <password>
"""
import datetime
import sys

from pymongo import MongoClient
from werkzeug.security import generate_password_hash

uri, db_name, email, password = sys.argv[1:5]
now = datetime.datetime.utcnow()
MongoClient(uri)[db_name].users.update_one(
    {"email": email},
    {"$set": {
        "name": "E2E Admin", "email": email, "email_lower": email,
        "password": generate_password_hash(password), "user_type": "admin",
        "is_verified": True, "email_verified": True, "permissions": ["*"],
        "verified_by": "system", "verified_at": now, "rejection_reason": None,
        "auth_provider": "local", "updated_at": now,
    }, "$setOnInsert": {"created_at": now}},
    upsert=True,
)
print("admin seeded:", email)
