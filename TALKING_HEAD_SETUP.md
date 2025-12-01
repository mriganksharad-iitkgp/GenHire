# Talking Head Integration Setup Guide

This guide explains how to set up the Talking Head (3D) library for realistic 3D avatar interviews in AptiDude.

## Overview

The Talking Head library provides a 3D avatar with real-time lip-sync capabilities, making interviews more realistic and engaging. The avatar will speak the interviewer's questions with synchronized mouth movements.

## Components Added

### Backend (`python-backend/`)

1. **TTS Routes** (`routes/tts_routes.py`)
   - Endpoint: `/api/tts/synthesize` - Synthesizes speech using Google Cloud TTS
   - Endpoint: `/api/tts/voices` - Lists available TTS voices
   - Uses Google Cloud Text-to-Speech service account authentication

2. **Dependencies**
   - Added `google-cloud-texttospeech==2.18.1` to `requirements.txt`

### Frontend (`react-frontend/`)

1. **TalkingHeadAvatar Component** (`src/components/TalkingHeadAvatar.jsx`)
   - Replaces the static avatar image with a 3D animated avatar
   - Handles TalkingHead initialization and speech synthesis
   - Integrates with the interview flow

2. **Chat.jsx Updates**
   - Removed Web Speech API usage
   - Integrated TalkingHeadAvatar component
   - Updated speech handling to use TalkingHead

3. **index.html**
   - Added import map for TalkingHead library and Three.js dependencies

## Configuration

### Backend Configuration

1. **Install Dependencies**
   ```bash
   cd python-backend
   pip install -r requirements.txt
   ```

2. **Google Cloud TTS Setup**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create or select a project
   - Enable the Text-to-Speech API
   - Create a service account:
     1. Go to "IAM & Admin" → "Service Accounts"
     2. Click "Create Service Account"
     3. Grant "Cloud Text-to-Speech API User" role
     4. Create and download a JSON key
   - Add to `.env` file:

   **Option 1: JSON String (Recommended for Production)**
   ```env
   GOOGLE_TTS_SERVICE_ACCOUNT_KEY={"type":"service_account","project_id":"your-project",...}
   ```

   **Option 2: File Path (Recommended for Development)**
   ```env
   GOOGLE_TTS_SERVICE_ACCOUNT_KEY=./path/to/service-account-key.json
   ```

### Frontend Configuration

The frontend automatically uses:
- Avatar file: `/public/avatars/brunette.glb`
- TTS endpoint: `${REACT_APP_API_BASE}/tts/synthesize`
- Language: English (en-GB)
- Voice: en-GB-Standard-A

Make sure your `.env` file has:
```env
REACT_APP_API_BASE=http://localhost:8080/api
REACT_APP_TOKEN_KEY=companyxyz-token
```

## Avatar File

The avatar file should be a Ready Player Me compatible GLB file:
- Located at: `react-frontend/public/avatars/brunette.glb`
- Must include ARKit and Oculus viseme blend shapes for lip-sync
- Full-body avatar with compatible rig

You can create free avatars at:
- https://readyplayer.me/avatar/
- https://playerzero.readyplayer.me/

## How It Works

1. **Interview Flow**
   - When an interview question is generated, `Chat.jsx` calls `speakResponse(text)`
   - This sets `textToSpeak` state, which triggers `TalkingHeadAvatar`
   - The avatar component uses TalkingHead's `speakText()` method

2. **TTS Processing**
   - TalkingHead makes a POST request to `/api/tts/synthesize` with the text
   - Backend authenticates using JWT token
   - Google Cloud TTS synthesizes the speech
   - Audio is returned in base64 format

3. **Lip-Sync**
   - TalkingHead uses built-in English lip-sync module
   - Converts text to visemes (mouth shapes)
   - Animates the avatar's mouth in real-time

## Troubleshooting

### Avatar Not Loading
- Check browser console for errors
- Verify the avatar file exists at `/public/avatars/brunette.glb`
- Ensure the file is a valid GLB format with required blend shapes

### TTS Not Working
- Verify Google Cloud TTS service account is configured correctly
- Check backend logs for authentication errors
- Ensure the TTS API is enabled in Google Cloud Console
- Verify JWT token is being sent correctly

### No Audio Playing
- Check browser audio permissions
- Verify TalkingHead is initialized correctly
- Check browser console for Web Audio API errors
- Ensure the TTS endpoint is returning valid audio data

## Features

- ✅ Real-time 3D avatar with facial animation
- ✅ Lip-sync with spoken text
- ✅ Natural voice synthesis using Google Cloud TTS
- ✅ Browser-side rendering (no server-side video processing)
- ✅ Compatible with Ready Player Me avatars
- ✅ English language support with expandable to other languages

## Next Steps

- Consider adding more avatar options
- Implement multiple language support
- Add custom poses and gestures
- Optimize avatar loading performance

