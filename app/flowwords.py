"""Flow tune-up: find names Wispr Flow mishears, and what to teach it.

ShipLog knows some words for certain: your project names, your repositories, your GitHub login,
the people in your log, and words you add yourself. When an update has something that sounds like
one of them but is spelled differently ("Shiplock", "Falter DB"), Flow probably misheard it. ShipLog
lists those so you can fix the item, and so you can add the right spelling to Flow's Dictionary,
which is what Flow uses to get your names right next time.
"""
import difflib
import re

SPEAK_WPM, TYPE_WPM = 150, 40
MIN_LEN = 4
STOP = set("a an the is are was were be to of in on at by for and or but it its this that with from as my me i we you he she they not no so do did done has have had will can just also then".split())


def squash(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def known_terms(doc):
    """{squashed: display} for every name ShipLog is sure about."""
    terms = {}

    def add(t):
        t = (t or "").strip()
        if len(squash(t)) >= MIN_LEN:
            terms.setdefault(squash(t), t)

    for p in doc.get("projects", []):
        add(p["name"])
    repos = {w["repo"] for w in doc.get("watch", [])} | set((doc.get("github_user") or {}).get("repos", []))
    for r in repos:
        owner, _, name = r.partition("/")
        add(name)
        add(owner)
    add((doc.get("github_user") or {}).get("login"))
    for it in doc.get("items", []):
        add(it.get("who"))
    for w in doc.get("flow_words", []):
        add(w)
    return terms


def _plural(a, b):
    return a + "s" == b or b + "s" == a or a + "es" == b or b + "es" == a


def misheard(text, terms):
    """Phrases in the text that sound like a known name but aren't spelled like it.
    Returns [{"said": "Shiplock", "meant": "ShipLog"}], each pair once."""
    words = re.findall(r"[A-Za-z0-9][\w'-]*", text or "")
    found, seen = [], set()
    for n in (2, 1):
        for i in range(len(words) - n + 1):
            part = words[i:i + n]
            if n == 2 and any(w.lower() in STOP or squash(w) in terms for w in part):
                continue  # "ShipLog is" is ShipLog plus a word, not a mishearing
            said = " ".join(part)
            s = squash(said)
            if len(s) < MIN_LEN:
                continue
            if s in terms:  # same letters: only a one-word name split in two ("fl carre") is a mishearing
                if " " in said and not re.search(r"[\s_/-]", terms[s]) and (said.lower(), terms[s]) not in seen:
                    seen.add((said.lower(), terms[s]))
                    found.append({"said": said, "meant": terms[s]})
                continue
            for k, display in terms.items():
                if abs(len(k) - len(s)) > 2 or k[0] != s[0] or _plural(k, s) or k.startswith(s) or s.startswith(k):
                    continue
                if difflib.SequenceMatcher(None, s, k).ratio() >= (0.75 if len(k) >= 7 else 0.8):
                    if (said.lower(), display) not in seen and not any(said in f["said"] for f in found if f["meant"] == display):
                        seen.add((said.lower(), display))
                        found.append({"said": said, "meant": display})
                    break
    return found


def tune_up(doc):
    """What the Flow tab shows: words spoken, time saved, misheard names, Dictionary and Snippets."""
    terms = known_terms(doc)
    entries = doc.get("entries", [])
    said = [e for e in entries if e.get("source") != "sample"] or entries  # the sample counts until you talk
    words = sum(len((e.get("text") or "").split()) for e in said)
    counts = {}
    for e in said:
        for m in misheard(e.get("text"), terms):
            key = (m["said"], m["meant"])
            counts[key] = counts.get(key, 0) + 1
    wrong = [{"said": s, "meant": m, "times": n} for (s, m), n in sorted(counts.items(), key=lambda x: -x[1])]
    dictionary = sorted(set(terms.values()), key=str.lower)
    repos = sorted({w["repo"] for w in doc.get("watch", [])} | set((doc.get("github_user") or {}).get("repos", [])))
    snippets = [{"say": "repo " + r.split("/")[1].replace("-", " "), "text": r} for r in repos][:8] + SNIPPETS
    return {
        "updates": len(said), "words": words,
        "talk_min": round(words / SPEAK_WPM, 1), "type_min": round(words / TYPE_WPM, 1),
        "misheard": wrong, "dictionary": dictionary, "snippets": snippets,
        "my_words": doc.get("flow_words", []),
    }


SNIPPETS = [  # spoken shortcuts that remind you what a good update covers
    {"say": "end of day", "text": "End of day. Done today: ... Still open: ... Due next: ... Don't: ..."},
]
