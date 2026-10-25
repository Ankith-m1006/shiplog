import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "app"))
from fastapi.testclient import TestClient  # noqa: E402

import server  # noqa: E402
from store import LocalStore, Workspaces  # noqa: E402


def test_owner_key_opens_the_real_workspace_even_if_it_does_not_look_like_a_browser_key(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "spaces", Workspaces(LocalStore(tmp_path)))
    monkeypatch.setattr(server, "OWNER_KEY", "ownerKEY_with-Other_chars_123456")
    c = TestClient(server.app)
    s = c.get("/api/state", headers={"X-Workspace": "ownerKEY_with-Other_chars_123456"}).json()
    assert s["owner"] is True and s["entries"] == []
    assert c.get("/api/state", headers={"X-Workspace": "ownerKEY_wrong"}).status_code == 400
    assert c.get("/api/state", headers={"X-Workspace": "wabcdefghij12"}).json()["owner"] is False
