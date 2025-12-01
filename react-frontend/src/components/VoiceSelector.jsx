import React from 'react';

const VOICES = [
    {
        id: 'us',
        label: '🇺🇸 US English',
        config: {
            lang: 'en-US',
            voice: 'en-US-Standard-C' // Female US
        }
    },
    {
        id: 'uk',
        label: '🇬🇧 UK English',
        config: {
            lang: 'en-GB',
            voice: 'en-GB-Standard-A' // Female UK
        }
    },
    {
        id: 'in',
        label: '🇮🇳 Indian English',
        config: {
            lang: 'en-IN',
            voice: 'en-IN-Standard-A' // Female India
        }
    },
    {
        id: 'au',
        label: '🇦🇺 Australian English',
        config: {
            lang: 'en-AU',
            voice: 'en-AU-Standard-A' // Female Australia
        }
    }
];

export default function VoiceSelector({ selectedVoiceId, onVoiceChange }) {
    const handleChange = (e) => {
        const selectedId = e.target.value;
        const voice = VOICES.find(v => v.id === selectedId);
        if (voice) {
            onVoiceChange(voice);
        }
    };

    return (
        <div className="voice-selector" style={{
            position: 'absolute',
            top: '20px',
            right: '20px',
            zIndex: 100,
            backgroundColor: 'rgba(0, 0, 0, 0.6)',
            backdropFilter: 'blur(10px)',
            padding: '8px 12px',
            borderRadius: '20px',
            border: '1px solid rgba(255, 255, 255, 0.2)',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
        }}>
            <span style={{ fontSize: '14px', color: '#ccc' }}>🎙️ Accent:</span>
            <select
                value={selectedVoiceId}
                onChange={handleChange}
                style={{
                    background: 'transparent',
                    border: 'none',
                    color: 'white',
                    fontSize: '14px',
                    fontWeight: '500',
                    cursor: 'pointer',
                    outline: 'none',
                    appearance: 'none', // Remove default arrow in some browsers
                    paddingRight: '15px'
                }}
            >
                {VOICES.map(voice => (
                    <option key={voice.id} value={voice.id} style={{ color: 'black' }}>
                        {voice.label}
                    </option>
                ))}
            </select>
            <span style={{
                position: 'absolute',
                right: '12px',
                pointerEvents: 'none',
                fontSize: '10px',
                color: '#aaa'
            }}>▼</span>
        </div>
    );
}

export { VOICES };
