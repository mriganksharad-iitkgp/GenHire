try:
    from google.cloud import speech
    print("Success: google.cloud.speech imported")
except ImportError as e:
    print(f"ImportError: {e}")
except Exception as e:
    print(f"Exception: {e}")
