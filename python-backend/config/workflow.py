"""Workflow rollout is opt-in; stored managed records stay protected when disabled."""
import os


def workflow_enabled():
    return os.getenv('GENHIRE_WORKFLOW_ENABLED', 'false').strip().lower() == 'true'


def managed(application):
    return bool(application and application.get('workflow_version_id'))


def legacy_filter(query):
    """Fence legacy writers against concurrent adoption, including in-flight workers."""
    return dict(query, workflow_version_id={'$in': [None, '']})
