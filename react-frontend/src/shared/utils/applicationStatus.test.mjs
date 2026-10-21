import test from 'node:test';
import assert from 'node:assert/strict';
import { applicationStatusLabel, normalizeStatus } from './applicationStatus.js';

test('managed labels separate screening clearance from OA invitation', () => {
  assert.equal(applicationStatusLabel({status: 'screening_cleared', workflow_version_id: 'version',
    workflow_label: 'Online assessment — eligible'}), 'Online assessment — eligible');
});

test('legacy selected and pre/post screening rejection remain compatible', () => {
  assert.equal(normalizeStatus('selected'), 'screening_cleared');
  assert.equal(applicationStatusLabel({status: 'selected'}), 'Screening Cleared');
  assert.equal(applicationStatusLabel({status: 'rejected'}), 'Not Shortlisted');
  assert.equal(applicationStatusLabel({status: 'rejected', interview_score: 0}), 'Screening Not Cleared');
  assert.equal(applicationStatusLabel({status: 'pending'}, {candidateFacing: true}), 'Awaiting Recruiter Review');
});

test('blank/unmanaged workflow labels cannot replace legacy labels', () => {
  assert.equal(applicationStatusLabel({status: 'interviewed', workflow_label: 'Hidden'}), 'Interviewed');
  assert.equal(applicationStatusLabel({status: 'interviewed', workflow_version_id: 'v', workflow_label: ' '}), 'Interviewed');
});
