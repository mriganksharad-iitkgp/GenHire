import { getHiringSetup } from '../api/jobSetupApi';
import { getAssessmentWorkspace, saveAssessmentWorkspace } from '../api/assessmentAuthoringApi';

export default async function attachJobQuestions(jobId, questions, replace=false) {
  if (!questions.length && !replace) return;
  const { version } = await getHiringSetup(jobId);
  const blueprintId = version?.assessment_blueprint_id;
  if (!blueprintId) throw new Error('Job saved. Its OA blueprint is unavailable; retain these questions and retry attaching them.');
  const workspace = await getAssessmentWorkspace(blueprintId);
  const ids = [...new Set([...(replace?[]:workspace.question_version_ids), ...questions.map(q => q._id)])];
  if (JSON.stringify(ids) === JSON.stringify(workspace.question_version_ids)) return;
  await saveAssessmentWorkspace(blueprintId, { question_version_ids: ids, expected_revision: workspace.revision,
    operation_key: crypto.randomUUID() });
}
