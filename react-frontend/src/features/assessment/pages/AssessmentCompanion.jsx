import React, { useEffect, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import { API_BASE } from 'shared/api/client';

export default function AssessmentCompanion() {
  const { invitationId } = useParams();
  const token = useRef(decodeURIComponent(window.location.hash.slice(1)));
  const video = useRef(null), stream = useRef(null);
  const [active, setActive] = useState(false), [message, setMessage] = useState('Consent to sampled camera capture before pairing. Raw images and summaries follow the policy shown in your assessment.');
  useEffect(() => { window.history.replaceState(null, '', window.location.pathname); }, []);
  useEffect(() => {
    if (!active) return undefined;
    let busy = false;
    const capture = async () => {
      if (busy || document.hidden) return; busy = true;
      try {
        const canvas = document.createElement('canvas'); canvas.width = 480; canvas.height = 360;
        canvas.getContext('2d').drawImage(video.current, 0, 0, 480, 360);
        const response = await fetch(`${API_BASE}/assessment-invitations/${invitationId}/camera-frame`, { method: 'POST',
          headers: { 'Content-Type': 'application/json', Authorization: `OA-Mobile ${token.current}` },
          body: JSON.stringify({ operation_key: crypto.randomUUID(), image: canvas.toDataURL('image/jpeg', .65) }) });
        const result = await response.json(); if (!response.ok) throw new Error(result.error);
        setMessage('Camera frame acknowledged. Keep this page visible; coverage gaps are reported for review.');
      } catch (error) { setMessage(error.message); } finally { busy = false; }
    };
    capture(); const timer = setInterval(capture, 15000);
    return () => { clearInterval(timer); stream.current?.getTracks().forEach(track => track.stop()); };
  }, [active, invitationId]);
  const start = async () => {
    if (!token.current) { setMessage('Pairing token is missing. Create a fresh link from the OA.'); return; }
    try { stream.current = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user' }, audio: false }); video.current.srcObject = stream.current; await video.current.play(); setActive(true); }
    catch (error) { setMessage(error.message); }
  };
  return <main style={{ padding: 24 }}><h1>OA companion camera</h1><p role="status">{message}</p><video ref={video} muted playsInline style={{ maxWidth: '100%' }} />
    <button disabled={active} onClick={start}>Consent and start companion camera</button><button onClick={() => { setActive(false); stream.current?.getTracks().forEach(track => track.stop()); }}>Stop camera</button></main>;
}
