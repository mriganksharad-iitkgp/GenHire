"""
Migration Script: Add Background Processing Fields to Existing Applications

This script updates all existing applications to include the new fields required
for the background CV scoring system.

Run this ONCE after deploying the new code.

Usage:
    python migrate_background_processing.py
"""

import sys
import os
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(os.path.dirname(__file__))

from config.database import db_config


def migrate_applications():
    """Add background processing fields to existing applications"""
    
    print("=" * 70)
    print("Background Processing Migration")
    print("=" * 70)
    print()
    
    # Connect to database
    print("Connecting to database...")
    db = db_config.connect()
    collections = db_config.get_collections()
    applications = collections['applications']
    
    # Count applications that need migration
    needs_migration = applications.count_documents({
        'is_visible': {'$exists': False}
    })
    
    print(f"Found {needs_migration} applications that need migration")
    print()
    
    if needs_migration == 0:
        print("✓ No applications need migration. All up to date!")
        return
    
    # Confirm with user
    print("This will update all existing applications with:")
    print("  • is_visible: True (make them visible)")
    print("  • processing_status: 'completed'")
    print("  • cv_score_calculated_at: None (unknown)")
    print()
    
    response = input("Continue with migration? (yes/no): ").strip().lower()
    if response != 'yes':
        print("Migration cancelled.")
        return
    
    print()
    print("Starting migration...")
    
    # Perform migration
    result = applications.update_many(
        {'is_visible': {'$exists': False}},  # Applications without the field
        {
            '$set': {
                'is_visible': True,  # Make existing applications visible
                'processing_status': 'completed',  # Mark as completed
                'cv_score_calculated_at': None,  # Unknown when they were scored
                'processing_error': None
            }
        }
    )
    
    print(f"✓ Updated {result.modified_count} applications")
    
    # Verify migration
    still_needs_migration = applications.count_documents({
        'is_visible': {'$exists': False}
    })
    
    if still_needs_migration == 0:
        print("✓ Migration completed successfully!")
        print()
        print("Next steps:")
        print("  1. Restart your Flask application")
        print("  2. Existing applications will now appear in dashboards")
        print("  3. New applications will use background CV scoring")
    else:
        print(f"⚠ Warning: {still_needs_migration} applications still need migration")
        print("   Please check database connection and try again")
    
    print()
    print("=" * 70)


def rollback_migration():
    """Remove background processing fields (for testing/rollback)"""
    
    print("=" * 70)
    print("Rollback Background Processing Migration")
    print("=" * 70)
    print()
    
    print("⚠ WARNING: This will remove background processing fields")
    print("   from all applications. Only use this for testing/rollback.")
    print()
    
    response = input("Are you sure you want to rollback? (yes/no): ").strip().lower()
    if response != 'yes':
        print("Rollback cancelled.")
        return
    
    # Connect to database
    db = db_config.connect()
    collections = db_config.get_collections()
    applications = collections['applications']
    
    # Remove fields
    result = applications.update_many(
        {},
        {
            '$unset': {
                'is_visible': '',
                'processing_status': '',
                'cv_score_calculated_at': '',
                'processing_error': ''
            }
        }
    )
    
    print(f"✓ Removed fields from {result.modified_count} applications")
    print()


def check_status():
    """Check migration status of applications"""
    
    print("=" * 70)
    print("Background Processing Migration Status")
    print("=" * 70)
    print()
    
    # Connect to database
    db = db_config.connect()
    collections = db_config.get_collections()
    applications = collections['applications']
    
    # Count different statuses
    total = applications.count_documents({})
    migrated = applications.count_documents({'is_visible': {'$exists': True}})
    visible = applications.count_documents({'is_visible': True})
    invisible = applications.count_documents({'is_visible': False})
    
    pending = applications.count_documents({'processing_status': 'pending'})
    processing = applications.count_documents({'processing_status': 'processing'})
    completed = applications.count_documents({'processing_status': 'completed'})
    failed = applications.count_documents({'processing_status': 'failed'})
    
    print(f"Total Applications: {total}")
    print(f"Migrated: {migrated} ({migrated/total*100:.1f}%)")
    print(f"Need Migration: {total - migrated}")
    print()
    
    print("Visibility Status:")
    print(f"  • Visible: {visible}")
    print(f"  • Invisible: {invisible}")
    print()
    
    print("Processing Status:")
    print(f"  • Pending: {pending}")
    print(f"  • Processing: {processing}")
    print(f"  • Completed: {completed}")
    print(f"  • Failed: {failed}")
    print()
    
    # Show stuck applications (processing for > 5 minutes)
    from datetime import timedelta
    five_mins_ago = datetime.utcnow() - timedelta(minutes=5)
    
    stuck = applications.count_documents({
        'processing_status': {'$in': ['pending', 'processing']},
        'applied_at': {'$lt': five_mins_ago}
    })
    
    if stuck > 0:
        print(f"⚠ WARNING: {stuck} applications stuck in processing (> 5 minutes)")
        print("   Consider running a retry operation")
    
    print("=" * 70)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Migrate applications to support background CV scoring'
    )
    parser.add_argument(
        'action',
        choices=['migrate', 'rollback', 'status'],
        help='Action to perform: migrate (add fields), rollback (remove fields), status (check)'
    )
    
    args = parser.parse_args()
    
    try:
        if args.action == 'migrate':
            migrate_applications()
        elif args.action == 'rollback':
            rollback_migration()
        elif args.action == 'status':
            check_status()
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
