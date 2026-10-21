import test from 'node:test';
import assert from 'node:assert/strict';
import {authoringError} from './authoringError.js';
test('missing authoring route reports backend mismatch rather than an unexplained 404',()=>{
 assert.match(authoringError({status:404,message:'URL not found'}),/Restart the backend/);
 assert.equal(authoringError({status:404,code:'workflow_disabled',message:'Workflow disabled'}),'Workflow disabled');
 assert.equal(authoringError({status:422,message:'Review question count'}),'Review question count');
});
