import { useCallback, useEffect, useRef, useState } from 'react';
import { getSetupCatalog, getSetupDraft, getHiringSetup, previewSetup, saveSetupDraft } from '../api/jobSetupApi';
import { withExistingDeadline } from '../utils/jobSetup';
import { roleAssessment } from '../utils/jobTemplates';

function withScoreDefaults(value,defaults) {
  if(!value)return value;
  return {...value,qualification:{...value.qualification,
    interview_minimum:value.qualification.interview_minimum??defaults?.qualification.interview_minimum??60,
    proctoring_minimum:value.qualification.proctoring_minimum??defaults?.qualification.proctoring_minimum??70}};
}

function hasAssessmentPlan(configuration, defaults) {
  // Old jobs saved with OA off still contain the untouched SDE default. Treat
  // that as uninitialized, while preserving configured or previously enabled plans.
  return configuration.pipeline.oa_enabled || configuration.oa.template_id !== defaults.oa.template_id
    || !!configuration.oa.instructions?.trim()
    || JSON.stringify(configuration.oa.sections) !== JSON.stringify(defaults.oa.sections);
}

export default function useJobSetup({ isOpen, jobId, initialJobData, onResume, jobTitle='' }) {
  const [catalog, setCatalog] = useState(null);
  const [assessmentBlueprintId,setAssessmentBlueprintId]=useState(null);
  const [configuration, setConfiguration] = useState(null);
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState('');
  const [previewError, setPreviewError] = useState('');
  const [previewPending, setPreviewPending] = useState(false);
  const [savedDraft, setSavedDraft] = useState(null);
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState(null);
  const [loading, setLoading] = useState(false);
  const [reloadVersion, setReloadVersion] = useState(0);
  const [actionNotice,setActionNotice] = useState(null);
  const oaInitialized = useRef(false);
  const draftRef = useRef(null);
  const savedContentRef = useRef(null);
  const keys = useRef(new Map());
  const onResumeRef = useRef(onResume);
  onResumeRef.current = onResume;
  const initialRef = useRef(initialJobData);
  initialRef.current = initialJobData;
  const enabled = catalog?.workflow_enabled === true;

  useEffect(() => {
    if (!isOpen) return;
    let cancelled = false;
    setLoading(true); setAssessmentBlueprintId(null); setActionNotice(null); oaInitialized.current=false;
    setCatalog(null); setConfiguration(null); setPreview(null); setError(''); setSavedDraft(null); setSavedAt(null);
    draftRef.current = null; savedContentRef.current = null; keys.current.clear();
    async function load() {
      try {
        const next = await getSetupCatalog();
        if (cancelled) return;
        setCatalog(next);
        if (!next.workflow_enabled) {setConfiguration({...structuredClone(next.defaults),oa:{...structuredClone(next.defaults.oa),source:'manual'},pipeline:{...next.defaults.pipeline,oa_enabled:false}});return;}
        let baseline = withExistingDeadline(structuredClone(next.defaults), initialRef.current?.deadline);
        baseline.oa.source='manual';
        const [saved, attached] = await Promise.allSettled([
          getSetupDraft(jobId), jobId ? getHiringSetup(jobId) : Promise.resolve(null),
        ]);
        if (cancelled) return;
        if (attached.status === 'rejected' || saved.status === 'rejected') {
          throw new Error('Saved hiring settings could not be loaded. Reopen the dialog before editing them.');
        }
        const version = attached.value?.version;setAssessmentBlueprintId(version?.assessment_blueprint_id||null);
        if (version) { baseline = version.configuration; oaInitialized.current=hasAssessmentPlan(baseline,next.defaults); }
        const draft = saved.value?.draft;
        // Reuse the same server draft even when the recruiter prefers the device copy.
        // Resuming controls the form values, not whether a second draft is created.
        if(draft)draftRef.current=draft;
        if (draft && version?.draft_id === draft._id && version?.draft_revision === draft.revision) {
          draftRef.current = draft;
        } else if (draft) setSavedDraft(draft);
        setConfiguration(withScoreDefaults(baseline,next.defaults));
      } catch (err) { if (!cancelled) setError(err.message || 'Hiring settings could not be loaded.'); }
      finally { if (!cancelled) setLoading(false); }
    }
    load();
    return () => { cancelled = true; };
  }, [isOpen, jobId, reloadVersion]);

  useEffect(() => {
    if (!isOpen || !enabled || !configuration) return;
    let cancelled = false;
    setPreviewPending(true); setPreviewError('');
    const timer = setTimeout(async () => {
      try {
        const result = await previewSetup(configuration);
        if (!cancelled) setPreview(result);
      } catch (err) {
        if (!cancelled) { setPreview(null); setPreviewError(err.message || 'Check your hiring configuration.'); }
      } finally { if (!cancelled) setPreviewPending(false); }
    }, 300);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [isOpen, enabled, configuration]);

  const save = useCallback(async (jobFields) => {
    if (!enabled) return {};
    if (!configuration || error) throw new Error(error || 'Hiring settings are still loading.');
    setSaving(true);
    try {
      // Validate the exact current value, rather than trusting a debounced preview.
      const checked = await previewSetup(configuration);
      const draft = draftRef.current;
      const body = { configuration: checked.configuration, job_fields: jobFields, job_id: jobId || null };
      const content = JSON.stringify(body);
      if (draft && savedContentRef.current === content) {
        setPreview(checked); setPreviewError('');
        return { setup_draft_id: draft._id, setup_draft_revision: draft.revision };
      }
      const signature = JSON.stringify({ ...body, id: draft?._id, revision: draft?.revision });
      if (!keys.current.has(signature)) keys.current.set(signature, crypto.randomUUID());
      const result = await saveSetupDraft(draft, { ...body, operation_key: keys.current.get(signature) });
      draftRef.current = result.draft;
      savedContentRef.current = content;
      setSavedAt(result.draft.updated_at);
      setSavedDraft(null);
      setPreview(checked); setPreviewError('');
      return { setup_draft_id: result.draft._id, setup_draft_revision: result.draft.revision };
    } finally { setSaving(false); }
  }, [enabled, configuration, error, jobId]);

  const resume = () => {
    if (!savedDraft) return;
    draftRef.current = savedDraft;
    oaInitialized.current=hasAssessmentPlan(savedDraft.configuration,catalog.defaults);
    setConfiguration(withScoreDefaults(savedDraft.configuration,catalog.defaults));
    onResumeRef.current?.(savedDraft.job_fields);
    setSavedAt(savedDraft.updated_at);
    setSavedDraft(null);
  };
  const setAssessmentEnabled = value => {
    if (!configuration) return;
    const initialize=value&&!oaInitialized.current;
    if(value) oaInitialized.current=true;
    setConfiguration(current => {
      const next=initialize?roleAssessment(current,catalog?.templates,jobTitle):current;
      return {...next,pipeline:{...next.pipeline,oa_enabled:value}};
    });
  };
  const applyRolePlan = (title=jobTitle) => {
    oaInitialized.current=true;
    setConfiguration(current=>roleAssessment({...current,oa:{...current.oa,instructions:''}},catalog?.templates,title));
    setActionNotice({id:crypto.randomUUID(),text:`Role defaults applied for ${title || 'this role'}: section counts, marks, timing and generation instructions updated. Review your questions separately.`});
  };
  return { catalog, enabled, assessmentBlueprintId, configuration, setConfiguration, preview, error, previewError, previewPending, loading,
    restoreConfiguration:value=>{oaInitialized.current=hasAssessmentPlan(value,catalog?.defaults||value);setConfiguration(withScoreDefaults(value,catalog?.defaults));},
    reload:()=>setReloadVersion(value=>value+1), setAssessmentEnabled, resetRoleAssessment:()=>applyRolePlan(), applyRolePlan, actionNotice,
    savedDraft, resume, dismissSaved: () => setSavedDraft(null), save, saving, savedAt,
    ready: !enabled || (!!configuration && !!preview && !previewPending && !previewError && !error) };
}
