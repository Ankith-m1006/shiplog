"""One JSON document per workspace: local files in development, a Cloud Storage bucket in production
(set SHIPLOG_BUCKET). A workspace holds projects, log entries, items and watched PRs."""
import copy
import json
import os
import pathlib
import threading

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEMO = ROOT / "data" / "demo.json"
LOCAL = ROOT / "data" / "workspaces"


def empty():
    return {"projects": [], "entries": [], "items": [], "watch": [], "github": {}}


def demo():
    return json.loads(DEMO.read_text(encoding="utf-8"))


class LocalStore:
    def __init__(self, folder=LOCAL):
        self.folder = pathlib.Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)

    def get(self, key):
        f = self.folder / f"{key}.json"
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None

    def put(self, key, doc):
        tmp = self.folder / f"{key}.json.tmp"
        tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(self.folder / f"{key}.json")


class BucketStore:
    def __init__(self, bucket):
        from google.cloud import storage  # only needed in production
        self.bucket = storage.Client().bucket(bucket)

    def get(self, key):
        blob = self.bucket.blob(f"workspaces/{key}.json")
        return json.loads(blob.download_as_text()) if blob.exists() else None

    def put(self, key, doc):
        self.bucket.blob(f"workspaces/{key}.json").upload_from_string(
            json.dumps(doc, ensure_ascii=False), content_type="application/json")


class Workspaces:
    """Loads a workspace, creating it from the demo seed (or empty, for the owner) the first time.
    A lock per process keeps read-modify-write safe on one Cloud Run instance."""

    def __init__(self, backend=None):
        bucket = os.environ.get("SHIPLOG_BUCKET")
        self.backend = backend or (BucketStore(bucket) if bucket else LocalStore())
        self.lock = threading.Lock()
        self.cache = {}

    def load(self, key, seed="demo"):
        if key in self.cache:
            return self.cache[key]
        doc = self.backend.get(key)
        if doc is None:
            doc = demo() if seed == "demo" else empty()
            self.backend.put(key, doc)
        self.cache[key] = doc
        while len(self.cache) > 200:  # keep memory flat when many judges open demo copies
            self.cache.pop(next(iter(self.cache)))
        return doc

    def save(self, key, doc):
        self.cache[key] = doc
        self.backend.put(key, doc)

    def reset(self, key):
        doc = demo()
        self.save(key, doc)
        return doc

    def edit(self, key, fn, seed="demo"):
        """Apply fn(doc) under the lock and save. fn returns whatever the caller needs back."""
        with self.lock:
            doc = copy.deepcopy(self.load(key, seed))
            out = fn(doc)
            self.save(key, doc)
            return out
