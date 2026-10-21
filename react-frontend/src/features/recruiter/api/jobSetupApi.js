import { request } from 'shared/api/client';

export const getSetupCatalog = () => request('/job-setup/catalog');
export const previewSetup = (configuration) => request('/job-setup/preview', {
  method: 'POST', body: JSON.stringify({ configuration }),
});
export const getSetupDraft = (jobId) => request(`/job-setup-drafts/latest${jobId ? `?job_id=${encodeURIComponent(jobId)}` : ''}`);
export const getHiringSetup = (jobId) => request(`/jobs/${jobId}/hiring-setup`);
export const saveSetupDraft = (draft, payload) => request(`/job-setup-drafts${draft ? `/${draft._id}` : ''}`, {
  method: draft ? 'PUT' : 'POST',
  body: JSON.stringify({ ...payload, ...(draft ? { expected_revision: draft.revision } : {}) }),
});
