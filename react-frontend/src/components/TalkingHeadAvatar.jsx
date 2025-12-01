
import React, { useEffect, useRef, useState } from 'react';
import './Avatar.css';

export default function TalkingHeadAvatar({
  textToSpeak,
  onSpeakingStart,
  onSpeakingEnd,
  isSpeaking,
  voiceConfig
}) {
  const containerRef = useRef(null);
  const headRef = useRef(null);
  const [isLoaded, setIsLoaded] = useState(false);
  const [error, setError] = useState(null);
  const lastTextRef = useRef(null);  // Track the last spoken text to prevent repetition
  const isSpeakingRef = useRef(false);  // Track if currently speaking

  // Handle voice changes dynamically
  useEffect(() => {
    if (headRef.current && voiceConfig) {
      console.log("Updating voice to:", voiceConfig);
      // Try to update properties directly if supported
      try {
        // Common pattern for such libraries
        headRef.current.ttsLang = voiceConfig.lang;
        headRef.current.ttsVoice = voiceConfig.voice;
      } catch (e) {
        console.warn("Failed to set voice properties directly:", e);
      }
    }
  }, [voiceConfig]);

  useEffect(() => {
    let head = null;

    const initializeTalkingHead = async () => {
      try {
        // Wait for TalkingHead module to be loaded (preloaded in index.html)
        let retries = 0;
        const maxRetries = 50; // 5 seconds total
        while (!window.TalkingHeadModule && retries < maxRetries) {
          await new Promise(resolve => setTimeout(resolve, 100));
          retries++;
        }

        if (!window.TalkingHeadModule) {
          throw new Error('TalkingHead module failed to load. Please refresh the page.');
        }

        const { TalkingHead } = window.TalkingHeadModule;

        if (!containerRef.current) return;

        // Get JWT token for authentication
        const token = localStorage.getItem(process.env.REACT_APP_TOKEN_KEY || 'companyxyz-token');

        // Function to get JWT token
        const jwtGet = async () => {
          return token;
        };

        // Initialize TalkingHead
        // Note: TalkingHead expects ttsEndpoint to be a Google TTS proxy endpoint
        // The endpoint should accept POST requests with text and return audio data
        // Use the correct API base URL (check your .env file)
        const apiBase = process.env.REACT_APP_API_BASE || 'http://localhost:5000/api';
        head = new TalkingHead(containerRef.current, {
          ttsEndpoint: `${apiBase}/tts/synthesize`,
          jwtGet: jwtGet,
          lipsyncModules: ["en"], // This will generate visemes from text automatically
          mixerGainSpeech: 3,
          enableSubtitles: false // Disable subtitles to reduce complexity
        });

        headRef.current = head;

        // Load and show the avatar
        // Note: The avatar must have all required blend shapes (ARKit + Oculus visemes)
        // Download from Ready Player Me with all morph targets included
        try {
          // Use provided voice config or defaults
          const lang = voiceConfig?.lang || "en-GB";
          const voice = voiceConfig?.voice || "en-GB-Standard-A";

          await head.showAvatar({
            url: '/avatars/brunette.glb',
            body: 'F',
            avatarMood: 'neutral',
            ttsLang: lang,
            ttsVoice: voice,
            lipsyncLang: 'en'
          });
        } catch (avatarError) {
          console.warn('Avatar loading error (may be missing blend shapes):', avatarError);
          // Try to continue anyway - some features may not work
          throw new Error('Avatar model is missing required blend shapes. Please use a Ready Player Me avatar downloaded with all morph targets.');
        }

        setIsLoaded(true);
        setError(null);
      } catch (err) {
        console.error('Error initializing TalkingHead:', err);
        if (err.message && err.message.includes('blend shapes')) {
          setError('Avatar model is missing required blend shapes. Please download a Ready Player Me avatar with all morph targets included. See AVATAR_SETUP_INSTRUCTIONS.md for details.');
        } else {
          setError('Failed to load avatar. Please refresh the page. Error: ' + err.message);
        }
      }
    };

    initializeTalkingHead();

    // Cleanup function
    return () => {
      if (headRef.current) {
        try {
          // Cleanup TalkingHead if needed
          headRef.current = null;
        } catch (err) {
          console.error('Error cleaning up TalkingHead:', err);
        }
      }
    };
  }, []); // Only run once on mount (voice updates handled by separate effect)

  useEffect(() => {
    // Don't speak if:
    // 1. Not loaded or no head reference
    // 2. No text to speak
    // 3. Currently speaking
    // 4. Same text as last spoken (prevents repetition)
    if (!isLoaded || !headRef.current || !textToSpeak ||
      isSpeakingRef.current || textToSpeak === lastTextRef.current) {
      return;
    }

    const speakText = async () => {
      try {
        // Set speaking state
        isSpeakingRef.current = true;
        lastTextRef.current = textToSpeak;

        if (onSpeakingStart) {
          onSpeakingStart();
        }

        // Try using speakText - TalkingHead should handle TTS request and lip-sync
        // If this fails, it will throw an error which we'll catch
        try {
          await headRef.current.speakText(textToSpeak);

          // Estimate duration for callback
          const words = textToSpeak.split(' ').length;
          const estimatedDuration = (words / 120) * 60 * 1000; // 120 words per minute
          const timeoutDuration = Math.max(estimatedDuration + 500, 1000);

          setTimeout(() => {
            isSpeakingRef.current = false;
            if (onSpeakingEnd) {
              onSpeakingEnd();
            }
          }, timeoutDuration);
        } catch (speakError) {
          console.error('speakText error:', speakError);
          // If speakText fails, the error might be about missing timestamps
          // But TalkingHead should handle this with lip-sync modules
          // Re-throw to show the actual error
          throw speakError;
        }
      } catch (err) {
        console.error('Error speaking text:', err);
        console.error('Error details:', err.message, err.stack);
        // Reset speaking state and call onSpeakingEnd to allow continuation
        isSpeakingRef.current = false;
        if (onSpeakingEnd) {
          onSpeakingEnd();
        }
      }
    };

    speakText();
  }, [textToSpeak, isLoaded, onSpeakingStart, onSpeakingEnd]);

  if (error) {
    return (
      <div className="avatar-container-static">
        <div style={{
          padding: '20px',
          color: '#666',
          textAlign: 'center'
        }}>
          {error}
        </div>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      style={{
        width: '100%',
        height: '100%',
        background: 'transparent'
      }}
    />
  );
}
