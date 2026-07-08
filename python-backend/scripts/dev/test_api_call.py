import requests

def test_api():
    # Login first
    login_res = requests.post("http://127.0.0.1:5000/api/login", json={
        "email": "demo@techcorp.com",
        "password": "password123",
        "userType": "recruiter"
    })
    
    if login_res.status_code != 200:
        print("Login failed!", login_res.status_code, login_res.text)
        return
        
    token = login_res.json().get('token')
    print("Token:", token)
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    job_data = {
        'title': 'API Test Job',
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
    
    # Create job
    res = requests.post("http://127.0.0.1:5000/api/jobs", json=job_data, headers=headers)
    print("Create Job Status:", res.status_code)
    print("Create Job Result:", res.text)

if __name__ == '__main__':
    test_api()
