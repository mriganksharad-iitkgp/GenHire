// Shared role starters for create/edit. Compensation and benefits need recruiter review.
const roles = [
  ['Software Engineer','Engineering','sde',['Problem Solving','JavaScript','Git'],'Algorithms, data structures and practical problem solving.'],
  ['Frontend Developer','Engineering','web_developer',['JavaScript','React','HTML','CSS'],'JavaScript fundamentals, accessible interfaces and browser behavior.','frontend'],
  ['Backend Developer','Engineering','web_developer',['Python','REST API','SQL','Git'],'API design, data modeling, reliability and backend problem solving.','backend'],
  ['Full Stack Developer','Engineering','web_developer',['JavaScript','React','Node.js','SQL'],'Web fundamentals, frontend/backend integration and problem solving.','full_stack'],
  ['Data Analyst','Data & Analytics','data_analyst',['SQL','Excel','Statistics','Data Analysis'],'SQL joins, aggregation, NULLs and analytical reasoning.'],
  ['Data Scientist','Data & Analytics','data_scientist',['Python','SQL','Machine Learning','Statistics'],'Data preparation, statistics, model evaluation and SQL analysis.'],
  ['Machine Learning Engineer','Data & Analytics','data_scientist',['Python','Machine Learning','MLOps'],'Model evaluation, data leakage, deployment and practical Python.'],
  ['DevOps Engineer','DevOps','devops',['Linux','Docker','CI/CD','Cloud'],'Linux, CI/CD, containers, incident response and automation.'],
  ['Site Reliability Engineer','DevOps','devops',['Linux','Monitoring','Python','Networking'],'Reliability, observability, incidents and automation.'],
  ['QA Automation Engineer','Quality Assurance','qa',['Testing','Python','API Testing','Automation'],'Test design, edge cases, automation and debugging.'],
  ['Product Manager','Product','product',['Product Strategy','Analytics','User Research'],'Prioritization, product metrics, discovery and stakeholder decisions.'],
  ['Business Analyst','Operations','business_analyst',['Business Analysis','Requirements','Analytics'],'Requirements, process analysis and business reasoning.'],
  ['UX Designer','Design','ux_design',['Figma','User Research','Prototyping','Accessibility'],'Research methods, usability, accessibility and design reasoning.'],
  ['Security Analyst','Security','security',['Security','Networking','Risk Analysis'],'Threat analysis, access control and incident response.'],
  ['Digital Marketing Specialist','Marketing','marketing',['Marketing','SEO','Analytics'],'Campaign measurement, experimentation and audience analysis.'],
  ['Sales Executive','Sales','sales',['Sales','Communication','CRM'],'Discovery, qualification, negotiation and customer scenarios.'],
  ['HR Specialist','Human Resources','hr',['Recruitment','Communication','HR Operations'],'Hiring operations, workplace scenarios and candidate communication.'],
  ['Customer Support Specialist','Customer Success','customer_support',['Customer Support','Communication','Troubleshooting'],'Customer scenarios, prioritization and troubleshooting.'],
  ['Finance Analyst','Finance','finance',['Finance','Excel','Accounting'],'Financial statements, budgeting and numerical reasoning.'],
];

export const JOB_TEMPLATES = Object.fromEntries(roles.map(([title,department,oaTemplateId,skills,oaInstructions,specialization='general']) => [title, {
  department, oaTemplateId, oaInstructions, specialization, skills, experience:'2-4 years', salary:'Competitive',
  description:`We are hiring a ${title} to join our ${department.toLowerCase()} team. Help solve practical problems, collaborate across teams and deliver reliable outcomes.`,
  responsibilities:[`Apply ${skills.slice(0,3).join(', ')} to day-to-day work.`, 'Collaborate with stakeholders and communicate progress clearly.', 'Review outcomes, document decisions and improve team processes.'],
  requirements:[`Practical experience with ${skills.slice(0,3).join(', ')}.`, 'Ability to explain decisions and solve role-relevant problems.', 'Relevant experience or equivalent demonstrable skills.'],
  benefits:[],
}]));

export function roleForTitle(title='') {
  const normalized=title.toLowerCase().replace(/[-/]/g,' ');
  const exact=Object.entries(JOB_TEMPLATES).find(([name])=>name.toLowerCase()===normalized);
  if(exact) return exact[1];
  const matches=[
    [/front\s*end|react developer/,'Frontend Developer'],[/back\s*end/,'Backend Developer'],[/full\s*stack/,'Full Stack Developer'],
    [/machine learning|\bml\b/,'Machine Learning Engineer'],[/data scien/,'Data Scientist'],[/data analy/,'Data Analyst'],
    [/devops|platform engineer/,'DevOps Engineer'],[/reliability|\bsre\b/,'Site Reliability Engineer'],[/\bqa\b|quality assurance|test engineer/,'QA Automation Engineer'],
    [/product manag/,'Product Manager'],[/business analy/,'Business Analyst'],[/\bux\b|\bui\b|designer/,'UX Designer'],
    [/security|cyber/,'Security Analyst'],[/market/,'Digital Marketing Specialist'],[/sales/,'Sales Executive'],[/\bhr\b|human resource|recruiter/,'HR Specialist'],
    [/support|customer success/,'Customer Support Specialist'],[/financ|accountant/,'Finance Analyst'],[/software|\bsde\b|developer|engineer/,'Software Engineer'],
  ];
  return JOB_TEMPLATES[matches.find(([pattern])=>pattern.test(normalized))?.[1]] || {oaTemplateId:'custom',specialization:'general',oaInstructions:`Assess skills relevant to ${title || 'this role'} with practical, unambiguous questions.`};
}

export function roleAssessment(configuration, templates, title) {
  const role=roleForTitle(title), preset=templates?.find(t=>t.id===role.oaTemplateId) || templates?.find(t=>t.id==='custom');
  if(!preset) return configuration;
  return {...configuration,oa:{...configuration.oa,template_id:preset.id,sections:structuredClone(preset.sections),duration_minutes:preset.duration_minutes,
    specialization:role.specialization,instructions:configuration.oa.instructions || role.oaInstructions}};
}
