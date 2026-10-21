export function authoringError(error) {
  if(error.status===404&&!error.code)return 'This backend has not loaded the OA authoring routes. Restart the backend with the latest code (and redeploy it for production), then retry. No AI request was accepted by this missing route.';
  return error.message||'Assessment preparation failed. Your current draft is retained.';
}
