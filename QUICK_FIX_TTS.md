# Quick Fix for TTS 500 Error

## Issue
Getting `500 Internal Server Error` when TalkingHead tries to use TTS. This means the backend is crashing.

## Most Likely Cause
The `GOOGLE_TTS_SERVICE_ACCOUNT_KEY` is not set in your `.env` file or is incorrectly formatted.

## Quick Fix Steps

### 1. Check Your Backend Terminal
Look at the error message in your backend terminal - it will tell you exactly what's wrong.

### 2. Set Up Google TTS Service Account Key

**Option A: Using a JSON File (Easier for Development)**

1. Download your Google Cloud service account JSON key file
2. Place it in your `python-backend` directory (e.g., `python-backend/google-tts-key.json`)
3. Add to `python-backend/.env`:
   ```
   GOOGLE_TTS_SERVICE_ACCOUNT_KEY=./google-tts-key.json
   ```

**Option B: Using JSON String (For Production)**

1. Open your service account JSON key file
2. Copy the entire JSON content
3. Add to `python-backend/.env` as a single line (replace newlines with spaces or use a JSON minifier):
   ```
   GOOGLE_TTS_SERVICE_ACCOUNT_KEY={"type":"service_account","project_id":"your-project",...}
   ```

### 3. Verify the Service Account Has Correct Permissions

Your service account needs the **"Cloud Text-to-Speech API User"** role.

### 4. Restart Your Backend

After updating `.env`, restart your Flask backend:
```bash
cd python-backend
python app.py
```

### 5. Check the Backend Logs

After restarting, try speaking again and check your backend terminal. You should see:
- `DEBUG TTS Request - Headers: ...`
- `DEBUG TTS Request - Data: ...`

If you see an error about credentials, the service account key is incorrect or missing.

## Port Configuration

**Important**: Your frontend is trying to connect to `http://127.0.0.1:5000`, but you mentioned the server runs on port `8080`.

Check your `react-frontend/.env` file and make sure:
```
REACT_APP_API_BASE=http://localhost:8080/api
```

Or update `react-frontend/src/components/TalkingHeadAvatar.jsx` line 48 to use the correct port.

## Testing the Endpoint Directly

You can test the TTS endpoint directly:

```bash
curl -X POST http://localhost:8080/api/tts/synthesize \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "input": {"text": "Hello, this is a test"},
    "voice": {
      "languageCode": "en-GB",
      "name": "en-GB-Standard-A"
    }
  }'
```

Replace `YOUR_JWT_TOKEN` with a valid JWT token from your auth system.

## Expected Response

If working correctly, you should get:
```json
{
  "audioContent": "UklGRiQAAABXQVZFZm10..."
}
```

If you get an error, the response will tell you what's wrong.

