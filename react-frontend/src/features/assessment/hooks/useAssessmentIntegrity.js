import { useEffect, useRef } from 'react';

export default function useAssessmentIntegrity(call, attempt, policy) {
  const queued = useRef([]), pending = useRef(null);
  useEffect(() => {
    if (!policy || !attempt?.attempt_id || attempt.state !== 'in_progress') return undefined;
    const enqueue = type => { queued.current = [...queued.current.slice(-18), { type }]; };
    const hidden = () => { if (document.hidden) enqueue('tab_hidden'); };
    const blur = () => enqueue('window_blur');
    const fullscreen = () => { if (!document.fullscreenElement) enqueue('fullscreen_exit'); };
    const paste = () => enqueue('external_paste_blocked');
    const runtime = () => enqueue('runtime_gap');
    document.addEventListener('visibilitychange', hidden); window.addEventListener('blur', blur);
    document.addEventListener('fullscreenchange', fullscreen); window.addEventListener('oa:paste-blocked', paste);
    window.addEventListener('offline', runtime);
    window.electronAPI?.onAppSwitched(blur);
    let busy = false;
    const timer = setInterval(async () => {
      if (busy) return; busy = true;
      if (!pending.current) { pending.current = { operation_key: crypto.randomUUID(), observations: [...queued.current, { type: 'heartbeat' }] }; queued.current = []; }
      try { await call(`/assessment-attempts/${attempt.attempt_id}/integrity-events`, { method: 'POST', body: JSON.stringify(pending.current) }); pending.current = null; }
      catch { /* Missing acknowledgments are coverage gaps; retry the same packet. */ }
      finally { busy = false; }
    }, 15000);
    return () => { clearInterval(timer); document.removeEventListener('visibilitychange', hidden); window.removeEventListener('blur', blur);
      document.removeEventListener('fullscreenchange', fullscreen); window.removeEventListener('oa:paste-blocked', paste); window.removeEventListener('offline', runtime); };
  }, [call, attempt?.attempt_id, attempt?.state, policy]);
}
