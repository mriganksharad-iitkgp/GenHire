export function canStartManagedScreening(app, now = Date.now()) {
  if (!app.workflow_version_id) return true;
  const workflow = app.workflow;
  const stage = workflow?.stages.find(s => s.stage_id === workflow.current_stage_id);
  if (workflow?.lifecycle !== 'active' || stage?.type !== 'screening' || !['eligible', 'in_progress'].includes(stage.state)) return false;
  const timing = app.hiring_timing;
  if (!timing) return false;
  return Date.parse(timing.screening_opens_at) <= now && now < Date.parse(timing.screening_closes_at);
}
