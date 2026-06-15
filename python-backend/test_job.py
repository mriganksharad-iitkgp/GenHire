import os
import jwt as pyjwt
import datetime
from bson import ObjectId
from app import app, collections

def test():
    # Get a real recruiter from the database
    recruiter = collections['users'].find_one({'user_type': 'recruiter'})
    if not recruiter:
        print("No recruiter found! Creating one...")
        result = collections['users'].insert_one({
            'name': 'Test Recruiter',
            'email': 'test_recruiter@example.com',
            'user_type': 'recruiter',
            'is_verified': True,
        })
        recruiter_id = str(result.inserted_id)
    else:
        recruiter_id = str(recruiter['_id'])
        collections['users'].update_one({'_id': ObjectId(recruiter_id)}, {'$set': {'is_verified': True}})
        
    print(f"Testing with recruiter: {recruiter_id}")
    
    # Generate token
    secret_key = os.getenv('JWT_SECRET_KEY', 'your-secret-key-here')
    payload = {
        'user_id': recruiter_id,
        'user_type': 'recruiter',
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1)
    }
    token = pyjwt.encode(payload, secret_key, algorithm='HS256')
    
    job_data = {
        'title': 'API Test Job via Flask Client',
        'department': 'Engineering',
        'location': 'Remote',
        'type': 'Full-time',
        'experience': '1-2 years',
        'salary': '100k',
        'description': 'Test description',
        'skills': ['Python', 'React'],
        'responsibilities': [],
        'requirements': [],
        'benefits': [],
        'status': 'draft'
    }
    
    with app.test_client() as client:
        res = client.post(
            '/api/jobs',
            json=job_data,
            headers={'Authorization': f'Bearer {token}'}
        )
        print("Status Code:", res.status_code)
        print("Response:", res.data.decode('utf-8'))

if __name__ == '__main__':
    test()
