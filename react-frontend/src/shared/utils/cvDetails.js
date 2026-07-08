export const hasCvValue = (value) => String(value || '').trim().length > 0;

const asArray = (value) => (Array.isArray(value) ? value : []);

export const isProfileCvComplete = (cvDetails) => {
  if (!cvDetails || typeof cvDetails !== 'object') return false;

  const education = asArray(cvDetails.education);
  const hasValidEducation = education.some(edu =>
    hasCvValue(edu?.degree) &&
    hasCvValue(edu?.institution) &&
    hasCvValue(edu?.year)
  );

  const skills = cvDetails.skills;
  const technicalSkills = Array.isArray(skills)
    ? skills
    : asArray(skills?.technical);
  const hasTechnicalSkills = technicalSkills.some(hasCvValue);

  const projects = asArray(cvDetails.projects);
  const hasValidProject = projects.some(project =>
    (hasCvValue(project?.title) || hasCvValue(project?.name)) &&
    hasCvValue(project?.description)
  );

  const salary = cvDetails.salaryExpectations || cvDetails.salary_expectations || {};
  const hasExpectedSalary =
    typeof salary === 'object'
      ? hasCvValue(salary.expectedSalary || salary.expected_salary)
      : hasCvValue(salary);

  return hasValidEducation && hasTechnicalSkills && hasValidProject && hasExpectedSalary;
};
