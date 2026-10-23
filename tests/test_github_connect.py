"""Connect GitHub: the OAuth round trip, what lands in the workspace, and that the token never leaves the server."""
import sys
import urllib.parse
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))
from fastapi.testclient import TestClient  # noqa: E402

import github  # noqa: E402
import server  # noqa: E402
from store import LocalStore, Workspaces  # noqa: E402

KEY = "wtestconnect01"
H = {"X-Workspace": KEY}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "spaces", Workspaces(LocalStore(tmp_path)))
    monkeypatch.setattr(server, "GH_ID", "client-id")
    monkeypatch.setattr(server, "GH_SECRET", "client-secret")
    monkeypatch.setattr(github, "exchange", lambda cid, secret, code: "tok-" + code)
    monkeypatch.setattr(github, "profile", lambda token: {
        "login": "octo", "name": "Octo Cat", "avatar": "https://avatars.example/octo",
        "repos": ["octo/shiplog", "octo/notes"],
        "prs": [{"repo": "octo/shiplog", "number": 12, "title": "Add onboarding"}]})
    return TestClient(server.app, follow_redirects=False)


def start(client):
    r = client.get(f"/auth/github/start?w={KEY}")
    assert r.status_code == 307
    q = urllib.parse.parse_qs(urllib.parse.urlparse(r.headers["location"]).query)
    assert q["client_id"] == ["client-id"] and q["scope"] == ["read:user"]
    return q["state"][0]


def test_connecting_adds_the_users_open_prs_and_repos_but_never_exposes_the_token(client):
    client.post("/api/reset?empty=true", headers=H)
    r = client.get(f"/auth/github/callback?code=abc&state={start(client)}")
    assert r.headers["location"] == "/?github=connected&prs=1"

    s = client.get("/api/state", headers=H).json()
    assert s["github_user"]["login"] == "octo" and s["github_user"]["repos"] == ["octo/shiplog", "octo/notes"]
    assert {"repo": "octo/shiplog", "number": 12, "source": "github"} in s["watch"]
    assert "secrets" not in s and "tok-abc" not in str(s)

    client.post("/api/github/disconnect", headers=H)
    s = client.get("/api/state", headers=H).json()
    assert "github_user" not in s and not any(w.get("source") == "github" for w in s["watch"])


def test_a_callback_with_an_unknown_or_reused_state_is_refused(client):
    assert client.get("/auth/github/callback?code=abc&state=made-up").headers["location"] == "/?github=expired"
    state = start(client)
    client.get(f"/auth/github/callback?code=abc&state={state}")
    assert client.get(f"/auth/github/callback?code=abc&state={state}").headers["location"] == "/?github=expired"


def test_connected_repos_are_known_when_reading_an_update(client, monkeypatch):
    client.post("/api/reset?empty=true", headers=H)
    client.get(f"/auth/github/callback?code=abc&state={start(client)}")
    seen = {}
    monkeypatch.setattr(server.ex, "extract", lambda text, projects, repos, log=(): seen.setdefault("repos", repos) and {"summary": "", "items": [], "dropped": []})
    client.post("/api/read", headers=H, json={"text": "Pushed the fix on PR 12 in shiplog."})
    assert "octo/shiplog" in seen["repos"]
