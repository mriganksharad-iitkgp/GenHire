import panelStyles from 'shared/styles/OperationalPanels.module.css';
import React, { useState } from 'react';
import { request } from 'shared/api/client';

export default function ReleasedAssessmentSummary({ attemptId }) {
  const [value, setValue] = useState(null), [error, setError] = useState(''), [busy, setBusy] = useState(false);
  if (!attemptId) return null;
  return <section className={panelStyles.panel} aria-label="Released assessment summary"><button disabled={busy} onClick={async () => {
    setBusy(true); setError('');
    try { setValue(await request(`/assessment-attempts/${attemptId}/evaluation`)); }
    catch (err) { setError(err.message); setValue(null); } finally { setBusy(false); }
  }}>Check released OA result</button>
    {error && <p role="alert">{error}</p>}
    {value && (value.result_available ? <><p>OA score: {value.summary.score}%. Outcome: {value.summary.outcome.replaceAll('_', ' ')}.</p>
      <ul>{value.summary.sections.map(s => <li key={s.type}>{s.type}: {s.earned}/{s.possible} ({s.weight}% weight)</li>)}</ul><p>The company will confirm any next interview arrangements.</p></> : <p>{value.message}</p>)}
  </section>;
}
