"""
Utility script to migrate existing applications to use AI-generated CV scores
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from config.database import db_config
from services.cv_scoring_service import CVScoringService
from bson import ObjectId
import datetime

class CVScoreMigration:
    def __init__(self):
        self.collections = db_config.get_collections()
        self.applications_collection = self.collections['applications']
        self.jobs_collection = self.collections['jobs']
        self.users_collection = self.collections['users']
        
        try:
            self.cv_scoring_service = CVScoringService()
            print("CV scoring service initialized successfully")
        except Exception as e:
            print(f"Error initializing CV scoring service: {e}")
            self.cv_scoring_service = None
    
    def migrate_all_applications(self):
        """Migrate all existing applications to use AI-generated CV scores"""
        if not self.cv_scoring_service:
            print("CV scoring service not available. Cannot proceed with migration.")
            return
        
        print("Starting migration of all applications...")
        
        # Get all applications
        applications = list(self.applications_collection.find({}))
        total_applications = len(applications)
        
        print(f"Found {total_applications} applications to migrate")
        
        successful_migrations = 0
        failed_migrations = 0
        
        for i, application in enumerate(applications, 1):
            print(f"\nProcessing application {i}/{total_applications}: {application['_id']}")
            
            try:
                result = self.recalculate_application_score(application)
                if result:
                    successful_migrations += 1
                    print(f"✓ Successfully migrated application {application['_id']}")
                else:
                    failed_migrations += 1
                    print(f"✗ Failed to migrate application {application['_id']}")
                    
            except Exception as e:
                failed_migrations += 1
                print(f"✗ Error migrating application {application['_id']}: {e}")
        
        print(f"\n=== Migration Summary ===")
        print(f"Total applications: {total_applications}")
        print(f"Successful migrations: {successful_migrations}")
        print(f"Failed migrations: {failed_migrations}")
        print(f"Success rate: {(successful_migrations/total_applications)*100:.1f}%")
    
    def recalculate_application_score(self, application):
        """Recalculate CV score for a single application"""
        try:
            # Get student profile and CV details
            student = self.users_collection.find_one({'_id': ObjectId(application['student_id'])})
            if not student:
                print(f"Student not found for application {application['_id']}")
                return False
            
            cv_details = student.get('cv_details')
            if not cv_details:
                print(f"CV details not found for student {application['student_id']}")
                # Set fallback score for applications without CV details
                self.applications_collection.update_one(
                    {'_id': application['_id']},
                    {
                        '$set': {
                            'cv_score': 75.0,
                            'cv_score_breakdown': None,
                            'updated_at': datetime.datetime.utcnow()
                        }
                    }
                )
                return True
            
            # Get job details
            job = self.jobs_collection.find_one({'_id': ObjectId(application['job_id'])})
            if not job:
                print(f"Job not found for application {application['_id']}")
                return False
            
            # Calculate new CV score
            scoring_result = self.cv_scoring_service.calculate_cv_score(cv_details, job)
            new_cv_score = scoring_result.get('total_score', 75.0)
            new_cv_score_breakdown = scoring_result.get('score_breakdown')
            
            # Update application with new score
            self.applications_collection.update_one(
                {'_id': application['_id']},
                {
                    '$set': {
                        'cv_score': new_cv_score,
                        'cv_score_breakdown': new_cv_score_breakdown,
                        'updated_at': datetime.datetime.utcnow()
                    }
                }
            )
            
            print(f"Updated CV score to {new_cv_score}")
            return True
            
        except Exception as e:
            print(f"Error processing application {application['_id']}: {e}")
            return False
    
    def recalculate_single_application(self, application_id):
        """Recalculate CV score for a single application by ID"""
        if not self.cv_scoring_service:
            print("CV scoring service not available.")
            return False
        
        try:
            application = self.applications_collection.find_one({'_id': ObjectId(application_id)})
            if not application:
                print(f"Application {application_id} not found")
                return False
            
            print(f"Recalculating score for application {application_id}")
            return self.recalculate_application_score(application)
            
        except Exception as e:
            print(f"Error recalculating application {application_id}: {e}")
            return False

def main():
    """Main function to run migration"""
    migration = CVScoreMigration()
    
    if len(sys.argv) > 1:
        # Recalculate specific application
        application_id = sys.argv[1]
        print(f"Recalculating CV score for application: {application_id}")
        migration.recalculate_single_application(application_id)
    else:
        # Migrate all applications
        print("Starting full migration of all applications...")
        migration.migrate_all_applications()

if __name__ == "__main__":
    main()
