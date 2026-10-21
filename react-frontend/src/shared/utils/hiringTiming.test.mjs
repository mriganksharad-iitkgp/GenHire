import test from 'node:test';
import assert from 'node:assert/strict';
import { canStartManagedScreening } from './hiringTiming.js';

test('managed screening uses exact server window and current stage', () => {
  const opening = Date.parse('2027-01-02T09:00:00Z'), closing = Date.parse('2027-01-05T09:00:00Z');
  const app = { workflow_version_id: 'version', workflow: { lifecycle: 'active', current_stage_id: 'screening',
    stages: [{ stage_id: 'screening', type: 'screening', state: 'eligible' }] },
    hiring_timing: { screening_opens_at: new Date(opening).toISOString(), screening_closes_at: new Date(closing).toISOString() } };
  assert.equal(canStartManagedScreening(app, opening - 1), false);
  assert.equal(canStartManagedScreening(app, opening), true);
  assert.equal(canStartManagedScreening(app, closing - 1), true);
  assert.equal(canStartManagedScreening(app, closing), false);
  assert.equal(canStartManagedScreening({ ...app, hiring_timing: null }, opening), false);
  assert.equal(canStartManagedScreening({ ...app, workflow: { ...app.workflow, lifecycle: 'withdrawn' } }, opening), false);
  app.workflow.stages[0].state = 'evaluating';
  assert.equal(canStartManagedScreening(app, opening), false);
  assert.equal(canStartManagedScreening({ status: 'shortlisted' }, closing), true);
});
