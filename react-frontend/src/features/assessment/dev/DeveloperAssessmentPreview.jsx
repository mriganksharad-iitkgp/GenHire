import React, { useCallback, useEffect, useState } from 'react';
import Assessment from '../pages/Assessment';
import styles from '../pages/Assessment.module.css';

function connection() {
  const parameters = new URLSearchParams(window.location.hash.slice(1));
  const saved = JSON.parse(sessionStorage.getItem('genhire-oa-dev-connection') || 'null');
  const token = parameters.get('token') || saved?.token || '';
  const port = Number(parameters.get('port') || saved?.port || 5011);
  if (!Number.isInteger(port) || port < 1024 || port > 65535) throw new Error('Invalid local preview port.');
  if (token) sessionStorage.setItem('genhire-oa-dev-connection', JSON.stringify({ token, port }));
  return { token, port };
}

export default function DeveloperAssessmentPreview() {
  const [config] = useState(connection);
  const [status, setStatus] = useState(null), [error, setError] = useState(''), [busy, setBusy] = useState(false);
  const [engine, setEngine] = useState('sqlite'), [contract, setContract] = useState('stdin_stdout');
  const call = useCallback(async (path, options = {}) => {
    if (!config.token) throw new Error('Start the local OA preview launcher and open its printed developer URL.');
    if (!path.startsWith('/dev/') && !path.startsWith('/assessment-')) throw new Error('Unsupported local preview request.');
    const response = await fetch(`http://127.0.0.1:${config.port}${path.startsWith('/dev/') ? '' : '/api'}${path}`, {
      ...options, credentials: 'omit', headers: { 'Content-Type': 'application/json', 'X-GenHire-Dev-Token': config.token },
    });
    const value = await response.json();
    if (!response.ok) throw new Error(value.error || 'Local preview request failed.');
    return value;
  }, [config]);

  useEffect(() => {
    let active = true;
    const load = () => call('/dev/status').then(value => { if (active) { setStatus(value); setError(''); } })
      .catch(failure => { if (active) setError(failure.message); });
    load(); const timer = setInterval(load, 2000);
    return () => { active = false; clearInterval(timer); };
  }, [call]);

  const reset = async (scenario, submit) => {
    setBusy(true); setError('');
    try {
      await call('/dev/reset', { method: 'POST', body: JSON.stringify({ engine, contract, scenario, submit }) });
      setStatus(await call('/dev/status'));
    } catch (failure) { setError(failure.message); } finally { setBusy(false); }
  };
  const pending = status && !['editable', 'complete', 'unavailable'].includes(status.state);
  return <>
    <details className={styles.developerTools} aria-label="Developer OA controls">
      <summary>Developer tools · localhost</summary>
      <div className={styles.developerToolsContent}>
      <h1>Local OA developer preview</h1>
      <p>Inspect the real candidate workspace and test submissions without an invitation, kiosk or timed exam. Answers are prefilled. Only the disposable local database is used; real compiler runs consume your provider allowance.</p>
      {error && <p role="alert">{error}</p>}
      <label>SQL engine <select value={engine} onChange={event => setEngine(event.target.value)}><option value="sqlite">SQLite</option><option value="duckdb">DuckDB</option></select></label>{' '}
      <label>Coding contract <select value={contract} onChange={event => setContract(event.target.value)}><option value="stdin_stdout">Standard input/output</option><option value="function">Typed function</option></select></label>
      <div>
        <button disabled={busy || pending || !status} onClick={() => reset('correct', false)}>Load editable preview</button>
        <button disabled={busy || pending || !status} onClick={() => reset('correct', true)}>Check correct submission</button>
        <button disabled={busy || pending || !status} onClick={() => reset('wrong', true)}>Check wrong submission</button>
        <button disabled={busy || pending || !status} onClick={() => reset('compile_error', true)}>Check compiler failure</button>
      </div>
      {status && <>
        <p role="status">Loaded: {status.engine}, {status.contract}. Evaluation: {status.state.replaceAll('_', ' ')}. Each complete submission uses seven provider runs; public Run adds runs.</p>
        {status.error_code && <p role="alert">{status.error_code}. Pending or unknown execution is not a candidate zero.</p>}
        {status.report && <section aria-label="Developer grading result"><h2>Actual graded score: {status.report.score ?? 'unavailable'}%</h2>
          <p>Correct preset: 100%; wrong preset: 0%; first coding compile failure: 80%.</p>
          <ul>{status.report.sections.map(section => <li key={section.type}>{section.type}: {section.earned}/{section.possible}, weight {section.weight}%</li>)}</ul>
        </section>}
        {!!status.case_results?.length && <table aria-label="Actual execution verdicts"><thead><tr><th>Question</th><th>Case</th><th>Purpose</th><th>Verdict</th></tr></thead>
          <tbody>{status.case_results.map((result, index) => <tr key={index}><td>{result.question}</td><td>{result.case_id}</td><td>{result.purpose}</td>
            <td>{result.status === 'ok' && result.passed === false ? 'wrong answer' : (result.status || result.state).replaceAll('_', ' ')}{result.passed === true ? ' — passed' : ''}</td></tr>)}</tbody></table>}
        <details><summary>Execution queue and provider usage</summary><pre>{JSON.stringify({ tasks: status.tasks, provider_usage: status.provider_usage }, null, 2)}</pre></details>
      </>}
      </div>
    </details>
    {status && <Assessment key={status.invitation_id} invitationId={status.invitation_id} oaRequest={call} developerPreview />}
  </>;
}
