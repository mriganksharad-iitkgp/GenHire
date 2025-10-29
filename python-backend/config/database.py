import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

class DatabaseConfig:
    def __init__(self):
        self.uri = os.getenv('MONGODB_URI')
        self.database_name = os.getenv('DATABASE_NAME', 'hrtech')
        self.client = None
        self.db = None
    
    def connect(self):
        """Establish connection to MongoDB and return database instance"""
        self.client = MongoClient(self.uri)
        self.db = self.client[self.database_name]
        return self.db
    
    def get_collections(self):
        """Return dictionary of collection objects"""
        if self.db is None:
            self.connect()
        return {
            'users': self.db['users'],
            'jobs': self.db['jobs'],
            'applications': self.db['applications'],
            'interviews': self.db['interviews'],
            'practice_sessions': self.db['practice_sessions']
        }
    
    def close_connection(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()

# Global database instance
db_config = DatabaseConfig()
