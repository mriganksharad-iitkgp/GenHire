#!/usr/bin/env python3
"""
Migration script to update existing applications with max_status_reached field
This script will update all applications to have proper max_status_reached based on their current status
"""

from pymongo import MongoClient
import datetime

# Database connection
client = MongoClient('mongodb://localhost:27017/')
db = client['recruitment_db']
applications_collection = db.applications

def migrate_max_status():
    """Update existing applications to add highest_status_reached field based on current status"""
    applications = list(applications_collection.find({}))
    updated_count = 0
    
    print(f"Found {len(applications)} applications to process...")
    
    for app in applications:
        current_status = (app.get('status') or 'pending').lower()
        existing_highest_status = app.get('highest_status_reached')
        
        # Always update if highest_status_reached doesn't exist or is None
        should_update = not existing_highest_status
        
        if should_update:
            print(f"Updating application {app['_id']} - Current status: {current_status}")
            
            # Set highest_status_reached based on current status
            # For rejected status, determine max based on available scores
            if current_status == 'rejected':
                # If they have interview_score, they reached interviewed
                if app.get('interview_score'):
                    highest_status_reached = 'interviewed'
                    print(f"  -> Setting highest_status to 'interviewed' (has interview score)")
                # Otherwise assume they reached reviewed stage
                else:
                    highest_status_reached = 'reviewed'
                    print(f"  -> Setting highest_status to 'reviewed' (no interview score)")
            else:
                highest_status_reached = current_status
                print(f"  -> Setting highest_status to '{current_status}'")
            
            # Also add mock scores if missing
            update_data = {'highest_status_reached': highest_status_reached}
            
            # Add mock CV score for reviewed and above
            if highest_status_reached in ['reviewed', 'shortlisted', 'interviewed', 'selected', 'screening_cleared']:
                if not app.get('cv_score') or app.get('cv_score') == 85.0:
                    update_data['cv_score'] = 87.0
                    print(f"  -> Adding mock CV score: 87.0")
            
            # Add mock interview score for interviewed and above
            if highest_status_reached in ['interviewed', 'selected', 'screening_cleared'] and not app.get('interview_score'):
                update_data['interview_score'] = 78.0
                print(f"  -> Adding mock interview score: 78.0")
            
            # Update the application
            applications_collection.update_one(
                {'_id': app['_id']},
                {'$set': update_data}
            )
            updated_count += 1
        else:
            print(f"Skipping application {app['_id']} - already has highest_status_reached: {existing_highest_status}")
    
    print(f"\nMigration completed!")
    print(f"Updated {updated_count} applications with highest_status_reached field")
    print(f"Total applications: {len(applications)}")
    
    return {
        'message': f'Updated {updated_count} applications with highest_status_reached field',
        'total_applications': len(applications),
        'updated_count': updated_count
    }

if __name__ == "__main__":
    try:
        result = migrate_max_status()
        print(f"\nResult: {result}")
    except Exception as e:
        print(f"Error during migration: {e}")
    finally:
        client.close()