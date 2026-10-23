"""What only spoken updates have, checked in code.

Dictated updates are long and unedited: people correct themselves ("Tuesday, no wait, Wednesday"),
take things back ("scratch that"), hedge ("I think"), say how urgent something is, and say numbers
as words ("PR twenty one six ninety four"). Gemini points at these; this module confirms each one
against the words actually said, so a flag only shows when the speaker really said it.
"""
import re

CORRECTION = r"(?:no wait|no,? wait|wait,? no|actually|i mean|sorry|correction|make that|rather|no no)"
RETRACTION = r"(?<!don't )(?<!do not )(?<!not )(?:scratch that|forget that|forget about that|ignore that|never ?mind|cancel that|strike that|delete that)"
HEDGES = ["i think", "i guess", "maybe", "probably", "not sure", "might", "possibly", "perhaps",
          "kind of", "sort of", "i believe", "hopefully"]
URGENT = ["urgent", "urgently", "asap", "as soon as possible", "right away", "immediately", "top priority",
          "really important", "super important", "critical", "first thing", "before anything else"]
TALK_WPM, TYPE_WPM = 150, 40  # conversational speech vs average typing

UNITS = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve "
                                     "thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split())}
UNITS["oh"] = 0
TENS = {w: 10 * i for i, w in enumerate("_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()) if w != "_"}
NUM_WORD = r"(?:" + "|".join(sorted(list(UNITS) + list(TENS) + ["hundred", "and"], key=len, reverse=True)) + r")"
TRIGGER = r"(?:\bpr|\bpull request|\bissue|\bnumber|\bticket|\bmr|\bmerge request|#)"


def low(s):
    return re.sub(r"\s+", " ", (s or "").lower().replace("’", "'")).strip()


def has(text, phrase):
    return bool(phrase) and re.search(r"(?<!\w)" + re.escape(low(phrase)) + r"(?!\w)", low(text)) is not None


def words_to_number(words):
    """'twenty one six ninety four' -> 21694; 'two one six nine four' -> 21694; None if not a number."""
    toks = [t for t in re.split(r"[\s-]+", low(words)) if t]
    groups, i = [], 0
    while i < len(toks):
        t = toks[i]
        if t == "and":
            i += 1
            continue
        if t in TENS:
            v = TENS[t]
            if i + 1 < len(toks) and toks[i + 1] in UNITS and 0 < UNITS[toks[i + 1]] < 10:
                v += UNITS[toks[i + 1]]
                i += 1
            groups.append(str(v))
        elif t in UNITS:
            if i + 1 < len(toks) and toks[i + 1] == "hundred":
                v, i = UNITS[t] * 100, i + 1
                j = i + 1
                if j < len(toks) and toks[j] == "and":
                    j += 1
                if j < len(toks) and toks[j] in TENS:
                    v += TENS[toks[j]]
                    if j + 1 < len(toks) and toks[j + 1] in UNITS and 0 < UNITS[toks[j + 1]] < 10:
                        v += UNITS[toks[j + 1]]
                        j += 1
                    i = j
                elif j < len(toks) and toks[j] in UNITS:
                    v += UNITS[toks[j]]
                    i = j
                groups.append(str(v))
            else:
                groups.append(str(UNITS[t]))
        else:
            return None
        i += 1
    return int("".join(groups)) if groups else None


def spoken_numbers(text):
    """Numbers said as words right after 'PR', 'issue', 'number', '#'... -> {number: the words said}."""
    out = {}
    for m in re.finditer(TRIGGER + r"\s*(?:number\s+)?((?:" + NUM_WORD + r"[\s-]+)*" + NUM_WORD + r")\b", low(text)):
        n = words_to_number(m.group(1))
        if n:
            out[n] = m.group(1)
    return out


def correction(text, before, after):
    """True when 'before' is said, then a correction phrase, then 'after' (within one breath)."""
    if not before or not after or low(before) == low(after):
        return False
    pat = (r"(?<!\w)" + re.escape(low(before)) + r"(?!\w)[\s,.;:!-]*(?:\w+[\s,]+){0,3}?" + CORRECTION +
           r"[\s,.;:!-]+(?:\w+[\s,]+){0,4}?" + re.escape(low(after)) + r"(?!\w)")
    return re.search(pat, low(text)) is not None


def self_corrects(quote):
    return re.search(r"(?<!\w)" + CORRECTION + r"(?!\w)", low(quote)) is not None


def retracted(text, quote):
    """True when the speaker takes the quoted words back right after saying them."""
    q = low(quote)
    i = low(text).find(q)
    if not q or i < 0:
        return False
    if re.search(r"[\s,.;:!-]" + RETRACTION + r"(?!\w)", q):  # the take-back is inside the quoted words
        return True
    tail = low(text)[i + len(q): i + len(q) + 40]
    return re.match(r"[\s,.;:!-]*(?:\w+[\s,]+){0,2}?" + RETRACTION, tail) is not None


def hedge_in(quote):
    return next((h for h in HEDGES if has(quote, h)), "")


def urgent_in(quote):
    return next((u for u in URGENT if has(quote, u)), "")


def stats(text):
    words = len((text or "").split())
    return {"words": words, "talk_s": round(words / TALK_WPM * 60), "type_s": round(words / TYPE_WPM * 60)}


def clause(text, quote):
    """The clause the quote sits in (split at sentence ends and commas), for hedges and urgency
    said just outside the quoted words."""
    t, q = low(text), low(quote)
    i = t.find(q)
    if not q or i < 0:
        return quote or ""
    start = max(t.rfind(c, 0, i) for c in ".!?;,\n") + 1
    ends = [j for j in (t.find(c, i + len(q)) for c in ".!?;\n") if j >= 0]
    return t[start: min(ends) if ends else len(t)]


def corrected_away(text, words):
    """True when 'words' is immediately followed by a correction ('Tuesday, no wait, ...'), so it
    is the value the speaker replaced, not the one they meant."""
    return bool(words) and re.search(r"(?<!\w)" + re.escape(low(words)) + r"(?!\w)[\s,.;:!-]*" + CORRECTION + r"(?!\w)",
                                     low(text)) is not None
