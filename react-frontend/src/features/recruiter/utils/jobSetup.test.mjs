import test from 'node:test';
import assert from 'node:assert/strict';
import { resizeSection, localInput, withExistingDeadline, applyRoleTemplate } from './jobSetup.js';
import { JOB_TEMPLATES, roleForTitle, roleAssessment } from './jobTemplates.js';
import questionDraftConfiguration from './questionDraftConfiguration.js';

test('saved question content determines counts, difficulty slots and marks without changing hiring policies',()=>{
  const c={pipeline:{advancement:'manual'},qualification:{interview_minimum:72},schedule:{timezone:'UTC'},oa:{timer_mode:'shared',duration_minutes:90,
    sections:[{type:'mcq',weight:30,duration_minutes:20},{type:'coding',weight:70,duration_minutes:70}]}};
  const qs=[{type:'mcq',content:{difficulty:'easy',marks:2}},{type:'coding',content:{difficulty:'hard',marks:40}}];
  const result=questionDraftConfiguration(c,qs);
  assert.deepEqual(result.qualification,c.qualification);assert.deepEqual(result.schedule,c.schedule);
  assert.deepEqual(result.oa.sections.map(s=>s.count),[1,1]);assert.deepEqual(result.oa.sections.map(s=>s.marks),[[2],[40]]);
  assert.equal(result.oa.sections[1].difficulty.hard,1);assert.equal(c.oa.sections[0].count,undefined);
});

test('manual question synchronization preserves fixed timers and assigns positive weights to new section types',()=>{
  const c={oa:{timer_mode:'section',revisit_allowed:false,duration_minutes:5,sections:[{type:'mcq',weight:100,duration_minutes:5}]}};
  const result=questionDraftConfiguration(c,['mcq','coding','sql'].map(type=>({type,content:{difficulty:'medium',marks:1}})));
  assert.equal(result.oa.timer_mode,'section');assert.equal(result.oa.revisit_allowed,false);
  assert.equal(result.oa.sections.reduce((sum,s)=>sum+s.duration_minutes,0),5);
  assert.equal(result.oa.sections.reduce((sum,s)=>sum+s.weight,0),100);
  assert.ok(result.oa.sections.every(s=>s.weight>0&&s.duration_minutes>0));
});

test('legacy metadata without private content does not reset an existing assessment plan',()=>{
  const c={oa:{sections:[{type:'sql',count:2}]}};
  assert.equal(questionDraftConfiguration(c,[{_id:'legacy-id',type:'sql'}]),c);
});

test('job role matching chooses technical and nontechnical OA plans', () => {
  assert.equal(Object.keys(JOB_TEMPLATES).length,19);
  for (const [title,role] of [['Senior Data Analyst','data_analyst'],['Senior Backend Engineer','web_developer'],['UX Designer','ux_design'],['Sales Executive','sales'],['HR Specialist','hr'],['Finance Analyst','finance']]) {
    assert.equal(roleForTitle(title).oaTemplateId,role);
  }
  assert.equal(roleForTitle('Custom research associate').oaTemplateId,'custom');
});

test('role assessment copies a preset without mutating it or losing policies', () => {
  const c={pipeline:{oa_enabled:false},oa:{instructions:'',source:'manual',sql_engine:'mysql',timer_mode:'shared'}};
  const templates=[{id:'data_analyst',sections:[{type:'sql',count:2}],duration_minutes:70}];
  const result=roleAssessment(c,templates,'Senior Data Analyst');
  assert.equal(result.oa.template_id,'data_analyst');
  assert.equal(result.oa.instructions.includes('SQL joins'),true);
  assert.equal(result.oa.source,'manual');
  assert.equal(result.oa.sql_engine,'mysql');
  result.oa.sections[0].count=7;
  assert.equal(templates[0].sections[0].count,2);
  assert.equal(c.oa.instructions,'');
});

test('section resizing keeps existing marks and bounds counts', () => {
  const section = { type: 'coding', marks: [20, 30], weight: 70, duration_minutes: 60 };
  const updated = resizeSection(section, 3);
  assert.deepEqual(updated.marks, [20, 30, 25]);
  assert.equal(section.marks.length, 2);
  assert.equal(resizeSection(section, 999).count, 10);
  assert.equal(resizeSection(section, 0).weight, 0);
  assert.equal(resizeSection(section, 0).duration_minutes, 0);
});
test('existing deadlines preserve local calendar intent and default stage windows', () => {
  const configuration = { schedule: { timezone: 'Asia/Kolkata' } };
  const result = withExistingDeadline(configuration, '2030-01-08');
  assert.equal(result.schedule.application_closes_at, '2030-01-08T23:59');
  assert.equal(result.schedule.screening_closes_at, '2030-01-11T23:59');
  assert.equal(result.schedule.oa_opens_at, '2030-01-12T09:00');
  assert.equal(result.schedule.oa_start_closes_at, '2030-01-13T09:00');
  assert.equal(localInput('2030-01-01T03:30:00Z', 'Asia/Kolkata'), '2030-01-01T09:00');
  assert.equal(localInput('invalid', 'Asia/Kolkata'), '');
  assert.equal(withExistingDeadline(configuration, ''), configuration);
  assert.equal(withExistingDeadline(configuration, 'invalid'), configuration);
  const dst = withExistingDeadline({ schedule: { timezone: 'America/New_York' } }, '2030-03-05');
  assert.equal(dst.schedule.oa_opens_at, '2030-03-09T09:00');
  assert.equal(dst.schedule.oa_start_closes_at, '2030-03-10T10:00');
});
test('role templates preserve recruiter instructions, dialect, format and policies', () => {
  const c = { pipeline: { oa_enabled: true }, oa: { instructions: 'SQL scenarios', source: 'hybrid', sql_engine: 'mysql', coding_contract: 'function' } };
  const preset = { id: 'product', sections: [{ type: 'mcq', count: 25 }], duration_minutes: 45 };
  const updated = applyRoleTemplate(c, preset);
  assert.equal(updated.oa.source, 'hybrid');
  assert.equal(updated.oa.sql_engine, 'mysql');
  assert.equal(updated.oa.coding_contract, 'function');
  assert.equal(updated.oa.instructions, 'SQL scenarios');
  assert.notEqual(updated.oa.sections, preset.sections);
  assert.equal(updated.pipeline, c.pipeline);
});
