import requests

def test_create_job():
    # Attempt a POST without token to see if it responds
    resp = requests.post("http://127.0.0.1:5000/api/jobs", json={})
    print(resp.status_code, resp.text)

if __name__ == '__main__':
    test_create_job()
