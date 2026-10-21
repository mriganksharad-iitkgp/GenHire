import panelStyles from 'shared/styles/OperationalPanels.module.css';
import React, { useState } from 'react';
import { request } from 'shared/api/client';

export default function AssessmentEvaluationReport({ attemptId }) {
  const [value, setValue] = useState(null), [error, setError] = useState(''), [busy, setBusy] = useState(false);
  if (!attemptId) return null;
  const load = async () => {
    setBusy(true); setError('');
    try { setValue(await request(`/assessment-attempts/${attemptId}/evaluation`)); }
    catch (err) { setError(err.message); } finally { setBusy(false); }
  };
  return <section className={panelStyles.panel} aria-label="Objective assessment evaluation">
    <button onClick={load} disabled={busy}>{busy ? 'Loading evaluation…' : 'View / refresh OA evaluation'}</button>
    {error && <p role="alert">{error}</p>}
    {value && <p role="status">Evaluation: {value.state.replaceAll('_', ' ')}{value.error_code && !value.report ? ' — processing or operator review is required.' : ''}</p>}
    {value?.report && <>
      <p>Objective score: {value.report.score === null ? 'Unavailable; no final score assigned' : `${value.report.score}%`}</p>
      <p>Objective threshold recommendation: {value.report.recommendation.replaceAll('_', ' ')}. Integrity review, company-round advancement and candidate result release require recruiter action.</p>
      <div className={panelStyles.tableScroll} role="region" aria-label="OA section scores" tabIndex={0}><table><caption>OA section scores</caption><thead><tr><th scope="col">Section</th><th scope="col">Earned</th><th scope="col">Possible</th><th scope="col">Weight</th></tr></thead>
        <tbody>{value.report.sections.map(section => <tr key={section.type}><th scope="row">{section.type}</th><td>{section.earned ?? 'Unavailable'}</td><td>{section.possible}</td><td>{section.weight}%</td></tr>)}</tbody>
      </table></div>
      <p>Attempt credits: {value.report.billing_action === 'capture' ? 'captured for completed evaluation' : 'reservation returned after platform evaluation failure'}.</p>
      <p>Candidate summary: {value.report.released ? 'released' : 'withheld until recruiter release'}.</p>
    </>}
  </section>;
}
