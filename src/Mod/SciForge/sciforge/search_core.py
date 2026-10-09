"""Fuzzy ranking for the command search box. Pure Python, no FreeCAD/Qt."""


def haystack(entry):
    return ("%s %s" % (entry.get("text", ""), entry.get("name", ""))).lower()


def _score_token(token, text):
    """Score one query token against text; None means no match."""
    index = text.find(token)
    if index >= 0:
        score = 100 - min(index, 50)
        if index == 0 or not text[index - 1].isalnum():
            score += 40  # starts a word
        return score
    # fall back to an in-order subsequence match ("flt" -> "fillet")
    pos = -1
    gaps = 0
    for ch in token:
        nxt = text.find(ch, pos + 1)
        if nxt < 0:
            return None
        if pos >= 0:
            gaps += nxt - pos - 1
        pos = nxt
    return max(1, 40 - gaps)


def score(query, entry):
    text = haystack(entry)
    tokens = query.lower().split()
    if not tokens:
        return 0
    total = 0
    for token in tokens:
        part = _score_token(token, text)
        if part is None:
            return None
        total += part
    return total


def rank(query, entries, limit=30):
    """Best matches first. An empty query returns entries alphabetically."""
    if not query.strip():
        return sorted(entries, key=lambda e: e.get("text", "").lower())[:limit]
    scored = []
    for entry in entries:
        value = score(query, entry)
        if value is not None:
            scored.append((-value, len(haystack(entry)), entry))
    scored.sort(key=lambda t: (t[0], t[1]))
    return [entry for _, _, entry in scored[:limit]]
