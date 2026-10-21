import panelStyles from 'shared/styles/OperationalPanels.module.css';
import React, { useState } from 'react';
import { request } from 'shared/api/client';
export default function AssessmentVariantPool({ setup, content }) {
  const [selected, setSelected] = useState([]), [quote, setQuote] = useState(null), [approved, setApproved] = useState(false), [error, setError] = useState(''), [notice, setNotice] = useState('');
  if (!(setup.configuration.oa?.variant_count > 1)) return null;
  const post = (path, value) => request(path, { method: 'POST', body: JSON.stringify(value) });
  return <section className={panelStyles.panel} aria-label="Reviewed assessment variant pool"><h4>Publish the reviewed variant pool before activation</h4>
    <p>Select exactly {setup.configuration.oa.variant_count} independently reviewed versions. Marks, difficulty and configuration must match; duplicated content is refused. Candidate invitations pin a balanced selection.</p>
    {error && <p role="alert">{error}</p>}{notice && <p role="status">{notice}</p>}
    {content.map(item => <label key={item._id} style={{ display: 'block' }}><input type="checkbox" checked={selected.includes(item._id)} onChange={e => { setSelected(e.target.checked ? [...selected, item._id] : selected.filter(id => id !== item._id)); setQuote(null); setApproved(false); }} /> Published revision {item.workspace_revision} ({item._id})</label>)}
    <button disabled={selected.length !== setup.configuration.oa.variant_count} onClick={async () => { try { setQuote(await post('/assessment-integrity-quotes', { kind: 'variants', target_id: setup._id, version_ids: selected })); setError(''); } catch (err) { setError(err.message); } }}>Preview variant pool credits</button>
    {quote && <><p>Additional validated batches: {quote.credits} credits.</p><label><input type="checkbox" checked={approved} onChange={e => setApproved(e.target.checked)} /> I approve the variant pool cost</label>
      <button disabled={!approved} onClick={async () => { try { await post('/assessment-integrity-purchases', { quote_id: quote.quote_id, operation_key: crypto.randomUUID(), accepted: true }); setNotice('Reviewed pool pinned. Proceed with activation; existing invitations retain their content.'); setError(''); } catch (err) { setError(err.message); } }}>Approve reviewed variant pool</button></>}
  </section>;
}
