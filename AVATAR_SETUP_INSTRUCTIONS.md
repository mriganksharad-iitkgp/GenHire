# Avatar Setup Instructions

## The Issue

Your current `brunette.glb` avatar is missing required blend shapes (morph targets) that TalkingHead needs for facial animations. Specifically, it's missing `eyesLookDown` and potentially other blend shapes.

## Solution: Download a Proper Ready Player Me Avatar

### Step 1: Create Avatar at Ready Player Me

1. Go to https://readyplayer.me/avatar/
2. Create your avatar (or use an existing one)
3. **IMPORTANT**: When downloading, make sure to include ALL morph targets

### Step 2: Download with Required Parameters

When downloading your avatar, you need to include these morph targets in the URL:

**For Ready Player Me:**
```
https://models.readyplayer.me/[YOUR-AVATAR-ID].glb?morphTargets=ARKit,Oculus+Visemes,mouthOpen,mouthSmile,eyesClosed,eyesLookUp,eyesLookDown&textureSizeLimit=1024&textureFormat=png
```

**For PlayerZero:**
```
https://avatars.readyplayer.me/[YOUR-AVATAR-ID].glb?morphTargetsGroup=ARKit,Oculus+Visemes&morphTargets=mouthSmile,mouthOpen,eyesClosed,eyesLookUp,eyesLookDown&textureSizeLimit=1024&textureFormat=png
```

### Step 3: Replace the Avatar File

1. Download your avatar with the proper URL parameters
2. Replace `react-frontend/public/avatars/brunette.glb` with your new avatar file
3. Keep the same filename (`brunette.glb`) or update the path in `TalkingHeadAvatar.jsx`

### Required Blend Shapes

The avatar MUST include these blend shapes:
- **ARKit blend shapes** (for basic facial expressions)
- **Oculus Visemes** (for lip-sync)
- **Additional**: mouthOpen, mouthSmile, eyesClosed, eyesLookUp, eyesLookDown

### Quick Test Avatar

You can use this Ready Player Me test avatar that should have all required blend shapes:

1. Go to: https://readyplayer.me/avatar
2. Create any avatar
3. Copy the avatar ID from the URL
4. Download using this format (replace `[AVATAR-ID]` with your ID):
   ```
   https://models.readyplayer.me/[AVATAR-ID].glb?morphTargets=ARKit,Oculus+Visemes,mouthOpen,mouthSmile,eyesClosed,eyesLookUp,eyesLookDown&textureSizeLimit=1024&textureFormat=png
   ```

### Alternative: Use a Known Working Avatar

If you want a quick solution, you can download a test avatar from the TalkingHead repository examples. However, the best approach is to create your own with all morph targets.

## Verification

After replacing the avatar:
1. Clear browser cache
2. Refresh the page
3. Check browser console - you should no longer see `eyesLookDown` errors
4. The avatar should animate smoothly

## Troubleshooting

### Still Getting Errors?

1. **Check avatar file**: Ensure the GLB file is valid and not corrupted
2. **Check morph targets**: Open the avatar in a 3D viewer (like Blender) and verify it has blend shapes
3. **Try different avatar**: Create a new avatar at Ready Player Me with all morph targets
4. **Check console**: Look for specific missing blend shape errors

### Avatar Not Showing?

- Check the file path in `TalkingHeadAvatar.jsx` (line 58)
- Verify the file exists at `public/avatars/brunette.glb`
- Check browser console for loading errors

