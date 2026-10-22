import test from 'node:test';
import assert from 'node:assert/strict';
import { newQuestion, editQuestion, prepareQuestion } from './questionEditor.js';

const oa = { sections: [{ type: 'coding', marks: [5] }], coding_contract: 'function',
  languages: ['python', 'javascript', 'java', 'cpp'], mcq_mode: 'multiple', sql_engine: 'sqlite' };

test('function input JSON round trip preserves private fixtures and editor state', () => {
  const editor = newQuestion('coding', oa);
  editor.topics = ' Arrays, Strings , ';
  editor.coding.reference_solutions.python = 'private solution';
  editor.coding.tests[1].input = '{"value":9371}';
  const content = prepareQuestion(editor);
  assert.deepEqual(content.topics, ['Arrays', 'Strings']);
  assert.equal(content.coding.tests[1].input.value, 9371);
  assert.equal(editor.coding.tests[1].input, '{"value":9371}');
  assert.deepEqual(prepareQuestion(editQuestion(content)), content);
  assert.deepEqual(content.coding.runtime_versions, { python: 'python-3.14', javascript: 'nodejs-24', java: 'openjdk-25', cpp: 'g++-15' });
});

test('invalid fixture JSON rejects saving without mutating the draft', () => {
  const editor = newQuestion('coding', oa);
  editor.coding.tests[1].expected = '{unfinished';
  const before = structuredClone(editor);
  assert.throws(() => prepareQuestion(editor), SyntaxError);
  assert.deepEqual(editor, before);
});

test('SQL dialect, hidden expected rows and MCQ selection survive editing', () => {
  const editor = newQuestion('sql', oa);
  assert.equal(editor.sql.engine_version, 'sqlite-3');
  editor.sql.datasets[1].expected_rows = '[[null,true,2.5,"private"]]';
  editor.sql.reference_query = 'SELECT private_column FROM fixture';
  const content = prepareQuestion(editor);
  assert.deepEqual(prepareQuestion(editQuestion(content)), content);
  assert.equal(newQuestion('mcq', oa).mcq.selection, 'multiple');
  assert.equal(newQuestion('coding', oa).marks, 5);
});

test('new coding suites contain sixteen cases and reject counts outside fifteen to twenty',()=>{
  const editor=newQuestion('coding',oa);
  assert.equal(editor.coding.tests.length,16);
  assert.equal(editor.coding.tests.filter(t=>t.visibility==='sample').length,2);
  editor.coding.tests=editor.coding.tests.slice(0,14);
  assert.throws(()=>prepareQuestion(editor),/15-20/);
  editor.coding.tests=Array.from({length:21},(_,i)=>({...newQuestion('coding',oa).coding.tests[0],id:`case${i}`}));
  assert.throws(()=>prepareQuestion(editor),/15-20/);
});
