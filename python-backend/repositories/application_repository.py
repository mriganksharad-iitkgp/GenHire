"""Application collection access."""

from repositories.base_repository import BaseRepository
from config.workflow import legacy_filter


class ApplicationRepository(BaseRepository):
    def update_by_id(self, raw_id, update):
        return self.update_one({'_id': self.to_object_id(raw_id)}, update)

    def update_one(self, query, update):
        # Managed writes belong to WorkflowRepository, including score changes.
        return self.col.update_one(legacy_filter(query), update)

    def delete_by_id(self, raw_id):
        return self.col.delete_one(legacy_filter({'_id': self.to_object_id(raw_id)}))
