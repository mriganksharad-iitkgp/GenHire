"""Generic Mongo repository primitives shared by the domain repositories."""

from bson import ObjectId


class BaseRepository:
    def __init__(self, collection):
        self.col = collection

    @staticmethod
    def to_object_id(raw_id):
        """Coerce a str/ObjectId to ObjectId.

        Raises bson.errors.InvalidId on garbage — deliberately identical to
        the inline ObjectId(...) calls this layer replaced, so existing
        try/except error handling in controllers keeps its exact behavior.
        """
        return raw_id if isinstance(raw_id, ObjectId) else ObjectId(raw_id)

    def find_one_by_id(self, raw_id, projection=None):
        return self.col.find_one({"_id": self.to_object_id(raw_id)}, projection)

    def find_one_by_id_or_none(self, raw_id, projection=None):
        """Tolerant variant for new code: malformed ids return None."""
        try:
            oid = self.to_object_id(raw_id)
        except Exception:
            return None
        return self.col.find_one({"_id": oid}, projection)

    def update_by_id(self, raw_id, update):
        return self.col.update_one({"_id": self.to_object_id(raw_id)}, update)

    def delete_by_id(self, raw_id):
        return self.col.delete_one({"_id": self.to_object_id(raw_id)})

    def find_one(self, query, projection=None):
        return self.col.find_one(query, projection)

    def update_one(self, query, update):
        return self.col.update_one(query, update)

    def insert(self, doc):
        """Insert one document; returns the new _id."""
        return self.col.insert_one(doc).inserted_id

    def count(self, query):
        return self.col.count_documents(query)

    @staticmethod
    def serialize(doc):
        """Copy a document with its _id stringified (JSON-safe)."""
        if not doc:
            return doc
        out = dict(doc)
        if isinstance(out.get("_id"), ObjectId):
            out["_id"] = str(out["_id"])
        return out

    def paginate(self, query, page=1, limit=20, projection=None, sort=None):
        """Standard skip/limit pagination; returns (items, total)."""
        page = max(int(page or 1), 1)
        limit = max(int(limit or 20), 1)
        cursor = self.col.find(query, projection)
        if sort:
            cursor = cursor.sort(sort)
        items = list(cursor.skip((page - 1) * limit).limit(limit))
        total = self.col.count_documents(query)
        return items, total
