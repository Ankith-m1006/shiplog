"""End to end on a phone viewport: capture -> review -> save -> Today -> Log, against the real server.

Only /api/read (the Gemini call) is stubbed, so the run needs no key; saving still goes through the server,
which re-checks every quote against the update. Skipped when no Chrome/Chromium is available.
"""
import os
import pathlib
import socket
import subprocess
import sys
import time
import uuid

import pytest

pw = pytest.importorskip("playwright.sync_api")
ROOT = pathlib.Path(__file__).resolve().parent.parent
CHROME = os.environ.get("SHIPLOG_CHROME", r"C:\Program Files\Google\Chrome\Application\chrome.exe")

UPDATE = ("Pushed the review fixes on PR 1063. The GitLab submission is due on the twenty-seventh. "
          "Don't ping the reviewer again.")
READ = {
    "summary": "Pushed the review fixes on PR 1063; GitLab due on the 27th.",
    "items": [
        {"kind": "done", "text": "Pushed the review fixes on PR 1063", "quote": "Pushed the review fixes on PR 1063",
         "due": None, "date_words": "", "project": "Kestra Hacktober", "repo": "kestra-io/plugin-jdbc", "number": 1063,
         "who": "", "flags": []},
        {"kind": "deadline", "text": "GitLab submission", "quote": "The GitLab submission is due on the twenty-seventh",
         "due": "2026-10-27", "date_words": "the twenty-seventh", "project": "GitLab", "repo": "", "number": None,
         "who": "", "flags": []},
        {"kind": "rule", "text": "Don't ping the reviewer again", "quote": "Don't ping the reviewer again",
         "due": None, "date_words": "", "project": "Kestra Hacktober", "repo": "", "number": None, "who": "",
         "flags": []},
    ],
    "dropped": [{"text": "Ship the release on Monday"}],
}


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def server():
    port = free_port()
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "server:app", "--app-dir", str(ROOT / "app"),
                             "--port", str(port)], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
            break
        except OSError:
            time.sleep(0.1)
    yield url
    proc.terminate()
    proc.wait(timeout=10)


@pytest.fixture
def page(server):
    exe = CHROME if pathlib.Path(CHROME).exists() else None
    with pw.sync_playwright() as p:
        try:
            browser = p.chromium.launch(executable_path=exe)
        except Exception as e:  # no browser on this machine
            pytest.skip(f"no Chromium available: {e}")
        ctx = browser.new_context(viewport={"width": 390, "height": 844})
        key = "w" + uuid.uuid4().hex[:12]
        ctx.add_init_script(f"localStorage.setItem('shiplog.ws', '{key}')")
        pg = ctx.new_page()
        pg.route("**/api/read", lambda route: route.fulfill(json=READ))
        pg.goto(server)
        yield pg
        browser.close()
        (ROOT / "data" / "workspaces" / f"{key}.json").unlink(missing_ok=True)


def test_capture_review_save_then_today_and_log(page):
    page.fill("#say", UPDATE)
    page.click("#read")

    review = page.locator("#review")
    review.get_by_text("Here's what I understood").wait_for()
    assert review.locator(".item").count() == 3
    assert "couldn't trace" in review.locator(".dropped").inner_text()
    assert "The GitLab submission is due on the twenty-seventh" in review.inner_text()

    review.locator(".item").nth(0).locator("[data-del]").click()  # the user removes one item before saving
    page.click("#save")

    page.locator("section#today.on").wait_for()
    assert "Don't ping the reviewer again" in page.locator("#rules").inner_text()
    assert "GitLab submission" in page.locator("#later, #week").all_inner_texts().__str__()

    page.click("nav button[data-tab=log]")
    page.fill("#q", "GitLab")
    entries = page.locator("#entries .entry")
    assert entries.count() == 1
    entries.first.locator("summary").click()
    assert UPDATE in entries.first.locator("blockquote").inner_text()
    assert "Pushed the review fixes" not in entries.first.locator(".chips").inner_text()


SPOKEN = ("Fixing the login bug is urgent. The DEV post is due Tuesday, no wait, Wednesday. "
          "Email Marco, actually scratch that. I think the results come out Monday.")
SPOKEN_READ = {
    "summary": "Login bug urgent; DEV post Wednesday.",
    "items": [
        {"kind": "task", "text": "Fix the login bug", "quote": "Fixing the login bug is urgent", "due": None,
         "date_words": "", "project": "", "who": "", "flags": [], "urgent": "urgent"},
        {"kind": "deadline", "text": "DEV post", "quote": "The DEV post is due Tuesday, no wait, Wednesday",
         "due": "2026-10-28", "date_words": "Wednesday", "project": "", "who": "", "flags": [],
         "corrected": {"from": "Tuesday", "to": "Wednesday"}},
        {"kind": "deadline", "text": "Results out", "quote": "I think the results come out Monday", "due": "2026-10-26",
         "date_words": "Monday", "project": "", "who": "", "flags": [], "unsure": "i think"},
    ],
    "dropped": [{"text": "Email Marco", "why": "you took it back", "taken_back": True}],
    "speech": {"words": 25, "talk_s": 10, "type_s": 38},
}


def test_flow_burst_is_read_without_a_tap_and_speech_marks_survive_saving(page):
    page.unroute("**/api/read")
    page.route("**/api/read", lambda route: route.fulfill(json=SPOKEN_READ))
    page.fill("#say", SPOKEN)  # arrives in one go, like Flow; nobody clicks Read
    review = page.locator("#review")
    review.get_by_text("Here's what I understood").wait_for(timeout=6000)
    text = review.inner_text()
    assert "you corrected “Tuesday” to “Wednesday”" in text
    assert "urgent: “urgent”" in text and "still unsure?" in text
    assert "You took these back" in text and "Email Marco" in text
    assert "25 words: about 10 s to say, 38 s to type." in text
    page.click("#save")
    page.locator("section#today.on").wait_for()
    today = page.locator("section#today").inner_text()
    assert "urgent" in today and "unsure" in today


def test_typing_key_by_key_waits_for_the_button(page):
    page.locator("#say").press_sequentially("Fix the build today.", delay=20)
    page.wait_for_timeout(2500)
    assert "Here's what I understood" not in page.locator("#review").inner_text()


def test_a_spoken_change_to_the_log_is_shown_and_applied(page):
    page.fill("#say", UPDATE)
    page.click("#read")
    page.locator("#review .item").first.wait_for()
    page.click("#save")
    page.locator("section#today.on").wait_for()
    state = page.evaluate("fetch('/api/state', {headers: {'X-Workspace': localStorage.getItem('shiplog.ws')}}).then(r => r.json())")
    gitlab = next(i for i in state["items"] if i["text"] == "GitLab submission")
    said = "The GitLab one is submitted."
    page.unroute("**/api/read")
    page.route("**/api/read", lambda route: route.fulfill(json={
        "summary": "GitLab submitted.", "items": [], "dropped": [],
        "changes": [{"id": gitlab["id"], "action": "done", "quote": said, "item": "GitLab submission",
                     "kind": "deadline", "was_due": "2026-10-27"}]}))
    page.click("nav button[data-tab=capture]")
    page.fill("#say", said)
    page.click("#read")
    review = page.locator("#review")
    review.get_by_text("Changes to your log").wait_for()
    assert "mark done" in review.inner_text() and "Save 1 change" in review.inner_text()
    page.click("#save")
    page.locator("section#today.on").wait_for()
    state = page.evaluate("fetch('/api/state', {headers: {'X-Workspace': localStorage.getItem('shiplog.ws')}}).then(r => r.json())")
    assert next(i for i in state["items"] if i["id"] == gitlab["id"])["status"] == "done"


def test_a_spoken_question_in_capture_is_answered_by_ask(page):
    page.route("**/api/ask", lambda route: route.fulfill(json={"found": False, "answer": "That isn't in your log yet.", "cites": []}))
    page.fill("#say", "What is due this week?")
    page.click("#read")
    page.locator("section#ask.on").wait_for()
    assert page.locator("#askq").input_value() == "What is due this week?"
