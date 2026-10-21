"""Public job metadata only; assessment authoring has separate scoped APIs."""


def candidate_job(job):
    # Allowlist public job metadata. Assessment content, answers, source
    # instructions and internal setup/workflow identifiers never leave here.
    allowed = {'_id','title','canonical_role','department','location','type','experience','salary',
        'description','skills','responsibilities','requirements','benefits',
        'status','company','logo','deadline','created_at','updated_at',
        'jd_original_filename','jd_upload_date','minimum_cv_score','gaze_proctoring','proctoring_config'}
    public = {key:value for key,value in job.items() if key in allowed}
    if 'proctoring_config' in public:
        from services.interview_flow_service import normalize_proctoring_config
        stored = public['proctoring_config']
        public['proctoring_config'] = normalize_proctoring_config(
            {key:value for key,value in stored.items() if type(value) is bool} if isinstance(stored,dict) else None)
    public['has_jd_document'] = bool(job.get('jd_pdf_path') or job.get('jd_gcs_path'))
    return public
