"""Resolve the date words in a spoken update ("tomorrow", "next Wednesday", "29 October") against the
moment it was captured, in IST. Returns None when the words can't be resolved reliably, so the
caller marks the date as unresolved instead of guessing."""
import datetime as dt
import re

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august",
          "september", "october", "november", "december"]
NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
                "eight": 8, "nine": 9, "ten": 10, "a": 1}


def now():
    return dt.datetime.now(IST)


def _month(word):
    word = word.lower()
    for i, m in enumerate(MONTHS, 1):
        if len(word) >= 3 and m.startswith(word):
            return i
    return None


def _on_or_after(today, month, day):
    """A day-and-month with no year: this year, or next year if it has already passed by more
    than a week (so "29 October" said on 30 October still means the day before)."""
    try:
        d = dt.date(today.year, month, day)
    except ValueError:
        return None
    if (today - d).days > 7:
        try:
            d = dt.date(today.year + 1, month, day)
        except ValueError:
            return None
    return d


def resolve(words, today=None):
    """words: the phrase the date came from. today: a date (defaults to today in IST)."""
    today = today or now().date()
    s = re.sub(r"[^\w\s/-]", " ", words.lower())
    s = re.sub(r"\b(\d+)(st|nd|rd|th)\b", r"\1", s)
    s = re.sub(r"\s+", " ", s).strip()

    if re.search(r"\bday after tomorrow\b", s):
        return today + dt.timedelta(days=2)
    if re.search(r"\b(tomorrow|tmrw|tmr)\b", s):
        return today + dt.timedelta(days=1)
    if re.search(r"\b(today|tonight|this evening|this morning)\b", s):
        return today
    if re.search(r"\byesterday\b", s):
        return today - dt.timedelta(days=1)

    m = re.search(r"\bin (\d+|" + "|".join(NUMBER_WORDS) + r") (day|days|week|weeks)\b", s)
    if m:
        n = int(m.group(1)) if m.group(1).isdigit() else NUMBER_WORDS[m.group(1)]
        return today + dt.timedelta(days=n * (7 if m.group(2).startswith("week") else 1))

    m = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", s)
    if m:
        try:
            return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None

    m = re.search(r"\b(\d{1,2}) ([a-z]+)(?: (\d{4}))?\b", s)
    if m and _month(m.group(2)):
        if m.group(3):
            try:
                return dt.date(int(m.group(3)), _month(m.group(2)), int(m.group(1)))
            except ValueError:
                return None
        return _on_or_after(today, _month(m.group(2)), int(m.group(1)))
    m = re.search(r"\b([a-z]+) (\d{1,2})(?: (\d{4}))?\b", s)
    if m and _month(m.group(1)):
        if m.group(3):
            try:
                return dt.date(int(m.group(3)), _month(m.group(1)), int(m.group(2)))
            except ValueError:
                return None
        return _on_or_after(today, _month(m.group(1)), int(m.group(2)))

    m = re.search(r"\b(this |next |coming |on )?(" + "|".join(WEEKDAYS) + r")\b", s)
    if m:
        target = WEEKDAYS.index(m.group(2))
        ahead = (target - today.weekday()) % 7
        if ahead == 0:
            # Said on the same weekday: "this Friday" is today, "next Friday" is a week away,
            # a bare "Friday" could be either, so it stays unresolved.
            if m.group(1) == "this ":
                return today
            if m.group(1) in ("next ", "coming "):
                return today + dt.timedelta(days=7)
            return None
        return today + dt.timedelta(days=ahead)
    if re.search(r"\bnext week\b", s):
        return today + dt.timedelta(days=7 - today.weekday())  # the coming Monday
    if re.search(r"\b(end of (the )?week|this weekend|weekend)\b", s):
        return today + dt.timedelta(days=(5 - today.weekday()) % 7)
    return None


def week_bounds(today=None):
    """Monday to Sunday of the current IST week."""
    today = today or now().date()
    start = today - dt.timedelta(days=today.weekday())
    return start, start + dt.timedelta(days=6)
