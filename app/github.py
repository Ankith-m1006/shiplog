"""Live status of watched pull requests, read-only from the public GitHub API.

Results are cached for five minutes and shared by every workspace, since the PRs are public. A PR
that can't be fetched is reported as unknown with the reason, never as failed.
"""
import json
import os
import threading
import time
import urllib.error
import urllib.request

import dates

API = "https://api.github.com"
TTL = 300
TOKEN = os.environ.get("SHIPLOG_GITHUB_TOKEN", "")

_cache = {}
_lock = threading.Lock()


def _get(path):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "ShipLog", "X-GitHub-Api-Version": "2022-11-28"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    with urllib.request.urlopen(urllib.request.Request(API + path, headers=headers), timeout=15) as resp:
        return json.loads(resp.read())


def _review(reviews):
    """GitHub's latest decisive review: an approval or change request, ignoring plain comments."""
    latest = {}
    for r in reviews:
        if r.get("state") in ("APPROVED", "CHANGES_REQUESTED", "DISMISSED"):
            latest[(r.get("user") or {}).get("login")] = r["state"]
    states = set(latest.values())
    if "CHANGES_REQUESTED" in states:
        return "changes requested"
    if "APPROVED" in states:
        return "approved"
    return "waiting for review" if not reviews else "reviewed, no decision"


def _checks(runs):
    if not runs:
        return "no checks"
    conclusions = [r.get("conclusion") for r in runs]
    if any(r.get("status") != "completed" for r in runs):
        return "checks running"
    if any(c in ("failure", "timed_out", "cancelled", "action_required") for c in conclusions):
        return "checks failing"
    return "checks passing"


def fetch(repo, number):
    pr = _get(f"/repos/{repo}/pulls/{number}")
    status = {"repo": repo, "number": number, "title": pr.get("title", ""), "url": pr.get("html_url"),
              "author": (pr.get("user") or {}).get("login", ""), "updated": pr.get("updated_at")}
    if pr.get("merged_at"):
        status.update(state="merged", detail="merged " + pr["merged_at"][:10])
        return status
    if pr.get("state") == "closed":
        status.update(state="closed", detail="closed without merging")
        return status
    review = _review(_get(f"/repos/{repo}/pulls/{number}/reviews?per_page=100"))
    checks = _checks(_get(f"/repos/{repo}/commits/{pr['head']['sha']}/check-runs?per_page=100").get("check_runs", []))
    status.update(state="draft" if pr.get("draft") else "open", detail=f"{review} · {checks}")
    return status


def status(repo, number, now=None):
    now = now or time.time()
    key = (repo, number)
    with _lock:
        hit = _cache.get(key)
        if hit and now - hit["at"] < TTL:
            return hit["value"]
    try:
        value = fetch(repo, number)
    except urllib.error.HTTPError as e:
        why = "not found" if e.code == 404 else "GitHub rate limit, try again later" if e.code in (403, 429) else f"GitHub error {e.code}"
        value = {"repo": repo, "number": number, "state": "unknown", "detail": why}
    except (urllib.error.URLError, TimeoutError, ConnectionError, KeyError, ValueError):
        value = {"repo": repo, "number": number, "state": "unknown", "detail": "couldn't reach GitHub"}
    value["checked"] = dates.now().strftime("%H:%M")
    with _lock:
        # An unknown answer is retried after a minute instead of being kept for five.
        _cache[key] = {"at": now if value["state"] != "unknown" else now - TTL + 60, "value": value}
    return value
