import os
import sys
from dotenv import load_dotenv

# Load exactly the same env as your app
load_dotenv('.env')

from services import gcs_service

def test_gcs():
    print("Testing GCS Configuration...")
    print(f"Bucket from env: {os.getenv('GCS_BUCKET_NAME')}")
    print(f"Service Account Key from env: {os.getenv('GCS_SERVICE_ACCOUNT_KEY')}")
    
    is_configured = gcs_service.is_gcs_configured()
    print(f"gcs_service.is_gcs_configured() returned: {is_configured}")
    
    if not is_configured:
        print("❌ GCS is not configured properly according to the service.")
        sys.exit(1)
        
    test_path = "test/connection_test.txt"
    test_content = b"This is a test file from GenHire to verify GCS is working."
    
    try:
        # 1. Upload
        print("\n1. Testing Upload...")
        gcs_uri = gcs_service.upload_file(test_content, test_path, content_type="text/plain")
        print(f"✅ Upload successful! URI: {gcs_uri}")
        
        # 2. Signed URL
        print("\n2. Testing Signed URL Generation...")
        signed_url = gcs_service.generate_signed_url(test_path, expiration_minutes=5)
        print(f"✅ Signed URL generated! (Valid for 5 mins)")
        print(f"URL: {signed_url}")
        
        import requests
        resp = requests.get(signed_url)
        if resp.status_code == 200 and resp.content == test_content:
            print("✅ Signed URL successfully downloaded the exact content!")
        else:
            print(f"❌ Signed URL validation failed. Status: {resp.status_code}")
            
        # 3. Delete
        print("\n3. Testing Delete...")
        gcs_service.delete_file(test_path)
        print("✅ Delete successful!")
        
        print("\n🎉 ALL GCS TESTS PASSED!")
        
    except Exception as e:
        print(f"\n❌ Test failed with exception: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_gcs()
