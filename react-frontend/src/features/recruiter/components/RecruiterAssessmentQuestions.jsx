import React,{useEffect,useState} from 'react';
import {getAssessmentWorkspace} from '../api/assessmentAuthoringApi';
import QuestionAccordionGroup from './QuestionAccordionGroup';
import styles from './HiringSetupWizard.module.css';

export default function RecruiterAssessmentQuestions({blueprintId}) {
  const [questions,setQuestions]=useState(null),[error,setError]=useState('');
  useEffect(()=>{
    let cancelled=false;setQuestions(null);setError('');
    getAssessmentWorkspace(blueprintId).then(result=>{if(!cancelled)setQuestions(result.questions);})
      .catch(err=>{if(!cancelled)setError(err.message||'Questions could not be loaded.');});
    return()=>{cancelled=true;};
  },[blueprintId]);
  if(error)return <p role="alert">{error}</p>;
  if(!questions)return <p role="status">Loading your private OA questions...</p>;
  return <section aria-label="Recruiter-only OA questions">
    <p className={styles.hint}>Private to your recruiting account. Edit these questions through Edit job. Candidates cannot access this preview, answer keys or hidden tests.</p>
    {!questions.length&&<p>No questions attached yet. Add them through Edit job.</p>}
    {['coding','mcq','sql'].map(kind=>{
      const items=questions.filter(q=>q.content.type===kind);
      return items.length>0&&<QuestionAccordionGroup key={kind} label={`${kind.toUpperCase()} questions`} items={items}
        title={(item,index)=>`${index+1}. ${item.content.title} - ${item.content.marks} marks`}
        render={({content:q})=><div className={styles.privatePreview}>
          <p>{q.statement}</p>
          {q.mcq&&<><ul>{q.mcq.options.map(option=><li key={option.id}>{option.text}{q.mcq.correct_option_ids.includes(option.id)&&<strong> (correct)</strong>}</li>)}</ul><p>{q.mcq.selection==='multiple'?'Multiple correct answers':'Single correct answer'}</p></>}
          {q.coding&&<>
            <p><strong>Input:</strong> {q.coding.input_format}</p><p><strong>Output:</strong> {q.coding.output_format}</p><p><strong>Constraints:</strong> {q.coding.constraints}</p>
            <details><summary>Testcases ({q.coding.tests.length})</summary>{q.coding.tests.map(test=><details key={test.id}><summary>{test.id} - {test.visibility}</summary><pre>{JSON.stringify({input:test.input,expected:test.expected,weight:test.weight},null,2)}</pre></details>)}</details>
            <details><summary>Reference solutions</summary>{Object.entries(q.coding.reference_solutions).map(([language,source])=><details key={language}><summary>{language}</summary><pre>{source}</pre></details>)}</details>
          </>}
          {q.sql&&<><p>{q.sql.engine} {q.sql.engine_version}</p><details><summary>Schema and reference query</summary><pre>{q.sql.schema_sql}</pre><pre>{q.sql.reference_query}</pre></details>
            <details><summary>SQL datasets ({q.sql.datasets.length})</summary>{q.sql.datasets.map(data=><details key={data.id}><summary>{data.id} - {data.visibility}</summary><pre>{JSON.stringify(data,null,2)}</pre></details>)}</details></>}
          <details><summary>Answer explanation</summary><p>{q.explanation}</p></details>
        </div>}/>;
    })}
  </section>;
}
