"""Live status of watched GitLab merge requests, read-only from the public GitLab API (gitlab.com).

Same shape and caching as github.py: five minutes, shared by every workspace, and a merge request
that can't be fetched is reported as unknown with the reason, never as failed.
"""
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

import dates

API = "https://gitlab.com/api/v4"
TTL = 300

_cache = {}
_lock = threading.Lock()


def _get(path):
    req = urllib.request.Request(API + path, headers={"User-Agent": "ShipLog", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def fetch(path, iid):
    mr = _get(f"/projects/{urllib.parse.quote(path, safe='')}/merge_requests/{iid}")
    status = {"repo": path, "number": iid, "host": "gitlab", "title": mr.get("title", ""), "url": mr.get("web_url"),
              "author": (mr.get("author") or {}).get("username", ""), "updated": mr.get("updated_at"),
              "notes": mr.get("user_notes_count", 0)}
    if mr.get("state") == "merged":
        status.update(state="merged", detail="merged " + (mr.get("merged_at") or "")[:10])
        return status
    if mr.get("state") == "closed":
        status.update(state="closed", detail="closed without merging")
        return status
    pipe = (mr.get("head_pipeline") or mr.get("pipeline") or {}).get("status")
    checks = {"success": "pipeline passing", "failed": "pipeline failing", "running": "pipeline running",
              "pending": "pipeline running", "canceled": "pipeline failing"}.get(pipe, "no pipeline")
    merge = (mr.get("detailed_merge_status") or "").replace("_", " ")
    review = "approved" if merge == "mergeable" else "changes requested" if merge == "requested changes" else "waiting for review"
    needs = "pipeline failing" if checks == "pipeline failing" else "changes requested" if review == "changes requested" else ""
    status.update(state="draft" if mr.get("draft") else "open", detail=f"{review} · {checks}", needs=needs)
    return status


def status(path, iid, now=None):
    now = now or time.time()
    key = (path, iid)
    with _lock:
        hit = _cache.get(key)
        if hit and now - hit["at"] < TTL:
            return hit["value"]
    try:
        value = fetch(path, iid)
    except urllib.error.HTTPError as e:
        why = "not found (private or wrong path)" if e.code in (401, 404) else "GitLab rate limit, try again later" if e.code == 429 else f"GitLab error {e.code}"
        value = {"repo": path, "number": iid, "host": "gitlab", "state": "unknown", "detail": why}
    except (urllib.error.URLError, TimeoutError, ConnectionError, KeyError, ValueError):
        value = {"repo": path, "number": iid, "host": "gitlab", "state": "unknown", "detail": "couldn't reach GitLab"}
    value["checked"] = dates.now().strftime("%H:%M")
    with _lock:
        _cache[key] = {"at": now if value["state"] != "unknown" else now - TTL + 60, "value": value}
    return value
