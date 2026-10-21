// OA credentials never replace the dashboard's account session or enter URLs.
export function scopedAssessmentClient(apiBase, initialToken, onToken = () => {}) {
  let token = initialToken;
  const replaceToken = value => { token = value; onToken(value); };
  const request = async (path, options = {}) => {
    const response = await fetch(`${apiBase.replace(/\/$/, '')}${path}`, { ...options,
      headers: { ...(options.body ? { 'Content-Type': 'application/json' } : {}), Authorization: `OA ${token}`, ...options.headers } });
    const value = await response.json();
    if (!response.ok) { const error = new Error(value.error || 'Assessment request failed.'); error.code = value.error_code; error.status = response.status; throw error; }
    return value;
  };
  return { request, replaceToken };
}
