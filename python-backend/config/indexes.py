"""Idempotent application-index compatibility checks. Never drops indexes."""
IDENTITY_KEYS = [("job_id", 1), ("student_id", 1)]
IDENTITY_FILTER = {"job_id": {"$type": "string"}, "student_id": {"$type": "string"}}


def ensure_application_identity_index(applications):
    for name, spec in applications.index_information().items():
        keys = list(spec.get("key", []))
        covers_identity = keys in (IDENTITY_KEYS, list(reversed(IDENTITY_KEYS)))
        # Full and sparse unique indexes cover every canonical application.
        # More restrictive partial filters cannot protect all new applications.
        partial = spec.get("partialFilterExpression")
        if covers_identity and spec.get("unique") and (partial is None or partial == IDENTITY_FILTER):
            return name
    return applications.create_index(IDENTITY_KEYS, name="uq_applications_job_student",
                                     unique=True, partialFilterExpression=IDENTITY_FILTER)
