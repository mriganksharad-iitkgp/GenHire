"""Flask JSON provider that serializes BSON ObjectIds and datetimes.

Without this, Flask's default encoder raises 500 on ObjectIds nested inside
any response dict (cv_snapshot.metadata, recruiter_id stored as ObjectId on
legacy docs, etc.) — and because the 500 short-circuits before after_request
runs, the browser also reports a CORS error as a side effect.
"""

import datetime

from bson import ObjectId
from flask.json.provider import DefaultJSONProvider


class ObjectIdSafeJSONProvider(DefaultJSONProvider):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()
        return super().default(obj)
