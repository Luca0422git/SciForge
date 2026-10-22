# SPDX-License-Identifier: LGPL-2.1-or-later
"""SciForge's documentation for AI models as a searchable library (Luca, 2026-10-21: "give
all the tools possible, with absolutely all the documentation available": a model that can
look through more documentation works better in SciForge).

What is in the library:
  * every document under the docs root (<Mod>/SciForge/docs/ai, or $SCIFORGE_AI_DOCS): the
    handbook, the selector cookbook, the recipes, one reference page per tool (generated from
    the catalogue by tool_docs.py), the index of the golden models and a copy of SciForge's
    own user documentation (user/: the cheat sheet, known issues, the Fusion parity specs);
  * the golden models (<Mod>/SciForge/SciForgeTests/golden/models, or
    $SCIFORGE_GOLDEN_MODELS): about 450 small designs in the design-step language, each with
    analytic measurements, looked up as examples.

What it answers (the tools docs_search, docs_read and examples_search, the MCP resources of
mcp_resources.py and the in-app assistant's system prompt all use it):
  * search(): keyword search ranked with BM25 (the ranking search engines use: rare words
    count more, long sections do not win by being long; headings and titles weigh more)
    over every section of every document, with a snippet and the section's anchor;
  * read(): a document, or one section of it by anchor, cut into pages for long ones;
  * examples(): recipes and golden models by words, tool, design-step op or tag;
  * prompt_index(): a short list of the documents for a system prompt (the documents
    themselves are fetched with the tools, never pasted into the prompt);
  * export_text(): every document in one Markdown file, for AI apps that load files
    (Claude Desktop projects and the like).

Recipes and handbook pages contain tool calls in fenced blocks marked "sciforge-calls":
call_blocks() reads them; SciForgeTests/headless/docs_runner.py runs every block in real
FreeCAD, so every example in the documentation is known to work.

Pure Python: no FreeCAD, no Qt (the MCP server an AI app starts imports it).
"""

import json
import math
import os
import re

ENV_DOCS = "SCIFORGE_AI_DOCS"
ENV_GOLDEN = "SCIFORGE_GOLDEN_MODELS"
DOC_TYPES = {".md": "text/markdown", ".txt": "text/plain", ".json": "application/json"}
MAX_DOC_BYTES = 2 * 1024 * 1024
PAGE_CHARS = 12000  # one page of docs_read: about 3000 tokens
DOCS_URI = "sciforge://docs/"
GOLDEN_URI = "sciforge://examples/golden/"
CALLS_TAG = "sciforge-calls"  # the fence info word of a block of tool calls

# The order the hand-written documents come in (the export, the prompt index); any other
# document follows in path order.
ORDER = (
    "README.md",
    "handbook.md",
    "concepts.md",
    "sketches.md",
    "selectors.md",
    "checking.md",
    "troubleshooting.md",
    "recipes/index.md",
)


def module_root():
    """<Mod>/SciForge (the folder that holds the sciforge package): in the source tree, an
    install and the Claude extension (where it is the extension's server/ folder)."""
    here = os.path.dirname(os.path.abspath(__file__))  # <Mod>/SciForge/sciforge/ai
    return os.path.dirname(os.path.dirname(here))


def docs_root():
    env = os.environ.get(ENV_DOCS)
    if env:
        return os.path.abspath(env)
    return os.path.join(module_root(), "docs", "ai")


def golden_root():
    env = os.environ.get(ENV_GOLDEN)
    if env:
        return os.path.abspath(env)
    return os.path.join(module_root(), "SciForgeTests", "golden", "models")


# -- Markdown -------------------------------------------------------------------------------------
_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_ANCHOR_TAG = re.compile(r'^\s*<a id="([^"]+)"></a>\s*$')
_FENCE = re.compile(r"^\s*(```+|~~~+)(.*)$")


def slug(text):
    """GitHub's anchor for a heading: lower case, punctuation dropped, spaces to -."""
    text = re.sub(r"[^\w\- ]", "", text.lower(), flags=re.UNICODE)
    return text.strip().replace(" ", "-")


def sections(text):
    """The sections of a Markdown text: [{level, title, anchor, aliases, start, end, body_end}]
    with line numbers (start: the heading line, end: before the next heading of the same or
    a higher level, body_end: before the next heading of any level). Lines in code fences are
    never headings. The text before the first heading is a section of level 0 ("top")."""
    lines = text.split("\n")
    found = [{"level": 0, "title": "", "anchor": "top", "aliases": [], "start": 0}]
    fence = None
    pending_alias = []
    seen = {"top": 1}
    for number, line in enumerate(lines):
        match = _FENCE.match(line)
        if match:
            mark = match.group(1)[0]
            if fence is None:
                fence = mark
            elif fence == mark:
                fence = None
            continue
        if fence is not None:
            continue
        tag = _ANCHOR_TAG.match(line)
        if tag:
            pending_alias.append(tag.group(1))
            continue
        head = _HEADING.match(line)
        if not head:
            if line.strip():
                pending_alias = []
            continue
        title = head.group(2).strip()
        anchor = slug(title) or "section"
        if anchor in seen:
            seen[anchor] += 1
            anchor = "%s-%d" % (anchor, seen[anchor] - 1)
        else:
            seen[anchor] = 1
        found.append(
            {
                "level": len(head.group(1)),
                "title": title,
                "anchor": anchor,
                "aliases": list(pending_alias),
                "start": number,
            }
        )
        pending_alias = []
    for i, sec in enumerate(found):
        later = found[i + 1 :]
        sec["body_end"] = later[0]["start"] if later else len(lines)
        end = len(lines)
        for other in later:
            if sec["level"] and other["level"] <= sec["level"]:
                end = other["start"]
                break
        sec["end"] = end if sec["level"] else sec["body_end"]
    if found[0]["body_end"] == 0 or not "\n".join(lines[: found[0]["body_end"]]).strip():
        found = found[1:]
    return found


def title_of_text(text, fallback):
    for line in text.split("\n")[:40]:
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def call_blocks(text):
    """The tool-call blocks of a document: [(line number, [call, ...])] where each call is
    {"tool", "args", "expect"?}. A block is a fenced block whose info string has
    "sciforge-calls"; its content is a JSON list of calls. ValueError names a bad block."""
    blocks = []
    lines = text.split("\n")
    inside = None
    other = None  # the mark of another fenced block being skipped (its content is not ours)
    for number, line in enumerate(lines):
        match = _FENCE.match(line)
        if other is not None:
            if match and match.group(1)[0] == other and not match.group(2).strip():
                other = None
            continue
        if inside is None:
            if match and CALLS_TAG in match.group(2).split():
                inside = (number, match.group(1), [])
            elif match:
                other = match.group(1)[0]
            continue
        if match and match.group(1)[0] == inside[1][0] and not match.group(2).strip():
            start, _mark, body = inside
            try:
                calls = json.loads("\n".join(body))
            except ValueError as exc:
                raise ValueError("the block at line %d is not JSON: %s" % (start + 1, exc))
            if not isinstance(calls, list) or not all(
                isinstance(c, dict) and isinstance(c.get("tool"), str) for c in calls
            ):
                raise ValueError(
                    'the block at line %d must be a list of {"tool", "args"}' % (start + 1)
                )
            blocks.append((start + 1, calls))
            inside = None
            continue
        inside[2].append(line)
    if inside is not None:
        raise ValueError("the block at line %d is not closed" % (inside[0] + 1))
    return blocks


CODE_WEIGHT = 0.25  # words in code blocks (calls, recorded answers) count a quarter
LOW_WEIGHT = 0.3  # and the words of sections that only point elsewhere
LOW_SECTIONS = ("see also", "contents")
REPEATED = 3  # a section found word for word in this many documents is indexed once
USER_WEIGHT = 0.6  # the words of user/ (Luca's documents, about the dialogs)


def _section_key(sec, lines):
    """What makes two sections the same: their title and their text (not the heading line)."""
    first = sec["start"] + (1 if sec["level"] else 0)
    text = " ".join("\n".join(lines[first : sec["body_end"]]).split())
    return (sec["title"].lower(), text)


def split_code(text):
    """(the prose of a Markdown text, the content of its fenced code blocks)."""
    prose, code = [], []
    fence = None
    for line in text.split("\n"):
        match = _FENCE.match(line)
        if match:
            mark = match.group(1)[0]
            if fence is None:
                fence = mark
            elif fence == mark:
                fence = None
            continue
        (code if fence is not None else prose).append(line)
    return "\n".join(prose), "\n".join(code)


# -- words ----------------------------------------------------------------------------------------
_WORD = re.compile(r"[a-z0-9]+(?:_[a-z0-9]+)*")
STOP = frozenset(
    "a an and are as at be by can do does for from has have how i if in into is it its me my "
    "of on or so than that the then there this to was what when where which while who why "
    "will with you your".split()
)


def stem(word):
    """A very small English stemmer: holes -> hole, sketches -> sketch, rounded -> round."""
    if word.isdigit() or len(word) <= 3:
        return word
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith(("ches", "shes", "sses", "xes")):
        return word[:-2]
    if word.endswith("s") and not word.endswith(("ss", "us", "is")):
        return word[:-1]
    if word.endswith("ing") and len(word) > 5:
        return word[:-3]
    if word.endswith("ed") and len(word) > 4:
        return word[:-2]
    return word


def words(text):
    """The search words of a text: lower case, stemmed, stop words dropped; snake_case names
    count as themselves and as their parts (fillet_sets -> fillet_sets, fillet, set)."""
    out = []
    for word in _WORD.findall(text.lower()):
        if word in STOP:
            continue
        out.append(stem(word) if "_" not in word else word)
        if "_" in word:
            out.extend(stem(p) for p in word.split("_") if p and p not in STOP)
    return out


# -- the library ----------------------------------------------------------------------------------
class Doc:
    def __init__(self, rel, full):
        self.rel = rel
        self.full = full
        self.kind = DOC_TYPES[os.path.splitext(rel)[1].lower()]
        self._text = None

    @property
    def text(self):
        if self._text is None:
            if os.path.getsize(self.full) > MAX_DOC_BYTES:
                self._text = "(This document is too big to read: %d bytes.)" % os.path.getsize(
                    self.full
                )
            else:
                with open(self.full, encoding="utf-8") as handle:
                    self._text = handle.read()
        return self._text

    @property
    def title(self):
        fallback = os.path.splitext(os.path.basename(self.rel))[0]
        if self.kind != "text/markdown":
            return fallback
        return title_of_text(self.text, fallback)

    @property
    def uri(self):
        return DOCS_URI + self.rel


def doc_files(root=None):
    """[(relative path with /, absolute path)] of the documents, sorted. Hidden files and
    folders starting with . or _ are left out."""
    root = root or docs_root()
    found = []
    if not os.path.isdir(root):
        return found
    for folder, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if not d.startswith((".", "_")))
        for name in sorted(files):
            if name.startswith(".") or os.path.splitext(name)[1].lower() not in DOC_TYPES:
                continue
            full = os.path.join(folder, name)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            found.append((rel, full))
    return sorted(found, key=lambda item: _order_key(item[0]))


def _order_key(rel):
    if rel in ORDER:
        return (0, ORDER.index(rel), rel)
    group = 1
    if rel.startswith("recipes/"):
        group = 2
    elif rel == "tools.md" or rel.startswith("reference/"):
        group = 3
    elif rel.startswith("examples/"):
        group = 4
    elif rel.startswith("user/"):
        group = 5
    return (group, 0, rel)


def golden_models(root=None):
    """[{id, title, tags, ops, note, path}] of the golden models, sorted by id."""
    root = root or golden_root()
    out = []
    if not os.path.isdir(root):
        return out
    for name in sorted(os.listdir(root)):
        if not name.endswith(".json") or name.startswith("."):
            continue
        path = os.path.join(root, name)
        try:
            with open(path, encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            continue
        steps = data.get("steps") if isinstance(data.get("steps"), list) else []
        ops = []
        for step in steps:
            op = step.get("op") if isinstance(step, dict) else None
            if isinstance(op, str) and op not in ops:
                ops.append(op)
        expect = data.get("expect") if isinstance(data.get("expect"), dict) else {}
        out.append(
            {
                "id": data.get("id") or name[:-5],
                "title": str(data.get("title", "")),
                "tags": [str(t) for t in data.get("tags", []) if isinstance(t, str)],
                "ops": ops,
                "steps": len(steps),
                "note": str(expect.get("note", "")),
                "xfail": bool(data.get("xfail")),
                "path": path,
            }
        )
    return out


def op_tools():
    """{op: [tool names that build it]} from the catalogue."""
    from . import catalog

    out = {}
    for entry in catalog.TOOLS:
        for op in entry["ops"]:
            out.setdefault(op, []).append(entry["name"])
    return out


class _Unit:
    """One searchable piece: a section of a document, or one example."""

    __slots__ = ("doc", "anchor", "title", "level", "body", "terms", "length", "extra")

    def __init__(self, doc, anchor, title, level, body, weighted, extra=None):
        self.doc = doc
        self.anchor = anchor
        self.title = title
        self.level = level
        self.body = body
        self.extra = extra or {}
        counts = {}
        for word, weight in weighted:
            counts[word] = counts.get(word, 0) + weight
        self.terms = counts
        self.length = sum(counts.values()) or 1


class _Index:
    """BM25 over units (k1 1.2, b 0.75: the usual values)."""

    K1 = 1.2
    B = 0.75

    def __init__(self, units):
        self.units = units
        self.df = {}
        for unit in units:
            for word in unit.terms:
                self.df[word] = self.df.get(word, 0) + 1
        self.avg = (sum(u.length for u in units) / len(units)) if units else 1.0

    def scores(self, query_words):
        n = len(self.units)
        wanted = []
        for word in query_words:
            if word not in wanted:
                wanted.append(word)
        out = []
        for unit in self.units:
            score = 0.0
            for word in wanted:
                tf = unit.terms.get(word)
                if not tf:
                    continue
                df = self.df.get(word, 0)
                idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
                norm = tf + self.K1 * (1 - self.B + self.B * unit.length / self.avg)
                score += idf * tf * (self.K1 + 1) / norm
            if score > 0:
                out.append((score, unit))
        out.sort(key=lambda item: (-item[0], item[1].doc, item[1].anchor))
        return out


_CACHE = {}


def _signature(root, golden):
    parts = []
    for rel, full in doc_files(root):
        try:
            stat = os.stat(full)
        except OSError:
            continue
        parts.append((rel, stat.st_mtime_ns, stat.st_size))
    try:
        parts.append(("golden", os.stat(golden).st_mtime_ns if os.path.isdir(golden) else 0))
    except OSError:
        pass
    return tuple(parts)


class Library:
    """The documents and examples of one docs root (and golden models folder)."""

    def __init__(self, root=None, golden=None):
        self.root = os.path.abspath(root or docs_root())
        self.golden = os.path.abspath(golden or golden_root())
        self.docs = [Doc(rel, full) for rel, full in doc_files(self.root)]
        self.by_rel = {d.rel: d for d in self.docs}
        self._sections = {}
        self._doc_index = None
        self._examples = None
        self._example_index = None

    # documents
    def doc(self, rel):
        return self.by_rel.get(rel)

    def sections_of(self, rel):
        if rel not in self._sections:
            doc = self.by_rel[rel]
            self._sections[rel] = sections(doc.text) if doc.kind == "text/markdown" else []
        return self._sections[rel]

    def find_section(self, rel, anchor):
        for sec in self.sections_of(rel):
            if anchor == sec["anchor"] or anchor in sec["aliases"]:
                return sec
        return None

    def anchors(self, rel):
        out = set()
        for sec in self.sections_of(rel):
            out.add(sec["anchor"])
            out.update(sec["aliases"])
        return out

    def doc_index(self):
        if self._doc_index is None:
            units = []
            seen = set()
            repeated = self._repeated_sections()
            for doc in self.docs:
                lines = doc.text.split("\n")
                head = words(doc.title) + words(doc.rel.replace("/", " ").replace("-", " "))
                secs = self.sections_of(doc.rel) or [
                    {
                        "level": 0,
                        "title": doc.title,
                        "anchor": "top",
                        "aliases": [],
                        "start": 0,
                        "body_end": len(lines),
                    }
                ]
                for sec in secs:
                    body = "\n".join(lines[sec["start"] : sec["body_end"]])
                    key = _section_key(sec, lines)
                    if key in repeated:
                        # the same section on many pages (every reference page's Answer):
                        # indexed once and weighted down, so it does not fill the results
                        # for its words ahead of the page that explains them
                        if key in seen:
                            continue
                        seen.add(key)
                    # Luca's documents (user/) describe the dialogs: the AI's own pages first
                    scale = USER_WEIGHT if doc.rel.startswith("user/") else 1.0
                    weighted = [(w, 3 * scale) for w in words(sec["title"])]
                    weighted += [(w, scale) for w in head]
                    prose, code = split_code(body)
                    low = sec["title"].lower() in LOW_SECTIONS or key in repeated
                    weighted += [(w, (LOW_WEIGHT if low else 1) * scale) for w in words(prose)]
                    weighted += [(w, CODE_WEIGHT * scale) for w in words(code)]
                    units.append(
                        _Unit(doc.rel, sec["anchor"], sec["title"], sec["level"], body, weighted)
                    )
            self._doc_index = _Index(units)
        return self._doc_index

    def _repeated_sections(self):
        """The keys (_section_key) of sections that several documents have word for word."""
        count = {}
        for doc in self.docs:
            lines = doc.text.split("\n")
            for sec in self.sections_of(doc.rel):
                key = _section_key(sec, lines)
                count[key] = count.get(key, 0) + 1
        return {k for k, n in count.items() if n >= REPEATED and k[1]}

    # examples
    def examples(self):
        if self._examples is None:
            found = []
            tools_of = op_tools()
            for model in golden_models(self.golden):
                tools = []
                for op in model["ops"]:
                    for name in tools_of.get(op, []):
                        if name not in tools:
                            tools.append(name)
                found.append(
                    {
                        "kind": "golden",
                        "id": model["id"],
                        "title": model["title"],
                        "tags": model["tags"],
                        "ops": model["ops"],
                        "tools": tools,
                        "note": model["note"],
                        "known_gap": model["xfail"],
                        "uri": GOLDEN_URI + model["id"],
                        "_path": model["path"],
                    }
                )
            for doc in self.docs:
                if not doc.rel.startswith("recipes/") or doc.rel == "recipes/index.md":
                    continue
                if doc.kind != "text/markdown":
                    continue
                try:
                    blocks = call_blocks(doc.text)
                except ValueError:
                    blocks = []
                tools = []
                for _line, calls in blocks:
                    for call in calls:
                        if call["tool"] not in tools:
                            tools.append(call["tool"])
                tags = []
                summary = ""
                for line in doc.text.split("\n"):
                    if line.lower().startswith("tags:"):
                        tags = [t.strip() for t in line[5:].split(",") if t.strip()]
                    elif not summary and line.strip() and not line.startswith(("#", "<!--")):
                        summary = line.strip()
                found.append(
                    {
                        "kind": "recipe",
                        "id": os.path.splitext(os.path.basename(doc.rel))[0],
                        "title": doc.title,
                        "tags": tags,
                        "ops": [],
                        "tools": tools,
                        "note": summary,
                        "calls": sum(len(c) for _l, c in blocks),
                        "uri": doc.uri,
                    }
                )
            self._examples = found
        return self._examples

    def example_index(self):
        if self._example_index is None:
            units = []
            for ex in self.examples():
                weighted = [(w, 3) for w in words(ex["title"] + " " + ex["id"].replace("_", " "))]
                weighted += [(w, 2) for w in words(" ".join(ex["tags"]))]
                weighted += [(w, 1) for w in words(" ".join(ex["ops"] + ex["tools"]))]
                weighted += [(w, 1) for w in words(ex["note"])]
                if ex["kind"] == "recipe":
                    weighted += [(w, 1) for w in words("recipe step by step tool calls")]
                units.append(_Unit(ex["uri"], "", ex["title"], 0, ex["note"], weighted, ex))
            self._example_index = _Index(units)
        return self._example_index


def library(root=None, golden=None):
    """The library for these folders, built once and again when a file changes."""
    root = os.path.abspath(root or docs_root())
    golden = os.path.abspath(golden or golden_root())
    key = (root, golden)
    sig = _signature(root, golden)
    cached = _CACHE.get(key)
    if cached is None or cached[0] != sig:
        cached = (sig, Library(root, golden))
        _CACHE[key] = cached
    return cached[1]


# -- answers --------------------------------------------------------------------------------------
def snippet(body, query_words, width=40):
    """About `width` words of body around the most query words (Markdown marks kept)."""
    tokens = body.split()
    if not tokens:
        return ""
    wanted = set(query_words)
    hits = [1 if wanted & set(words(t)) else 0 for t in tokens]
    best, best_at, run = -1, 0, 0
    for i in range(len(tokens)):
        run += hits[i]
        if i >= width:
            run -= hits[i - width]
        if run > best:
            best, best_at = run, max(0, i - width + 1)
    start = max(0, best_at - 4) if best > 0 else 0
    piece = tokens[start : start + width]
    text = " ".join(piece)
    if start > 0:
        text = "... " + text
    if start + width < len(tokens):
        text += " ..."
    return text


def search(query, limit=8, scope="all", per_doc=3, lib=None):
    """docs_search: the sections that best match the query. scope: all, or a folder of the
    docs root ("recipes", "reference", "user", "examples") or a file ("handbook.md").
    Returns {query, results: [{uri, path, anchor, document, section, score, snippet}],
    total}."""
    lib = lib or library()
    scope = known_scope(scope, lib)
    query_words = words(query or "")
    index = lib.doc_index()
    results = []
    per = {}
    total = 0
    for score, unit in index.scores(query_words):
        if scope != "all":
            folder = scope.rstrip("/") + "/"
            if unit.doc != scope and not unit.doc.startswith(folder):
                continue
        total += 1
        if per.get(unit.doc, 0) >= per_doc or len(results) >= limit:
            continue
        per[unit.doc] = per.get(unit.doc, 0) + 1
        doc = lib.doc(unit.doc)
        anchor = "" if unit.anchor == "top" else "#" + unit.anchor
        body = unit.body
        if unit.level:
            body = body.split("\n", 1)[1] if "\n" in body else ""
        results.append(
            {
                "uri": doc.uri + anchor,
                "path": unit.doc,
                "anchor": unit.anchor,
                "document": doc.title,
                "section": unit.title or doc.title,
                "score": round(score, 3),
                "snippet": snippet(body, query_words),
            }
        )
    return {"query": query, "results": results, "total": total}


class UnknownScope(ValueError):
    """docs_search was given a scope that is no folder or document of the docs root."""


def known_scope(scope, lib):
    """The scope as search() uses it: "all", a folder ("recipes") or a document
    ("handbook.md"; "handbook" is taken for it). UnknownScope for anything else."""
    scope = (scope or "all").strip().strip("/") or "all"
    if scope == "all":
        return scope
    rels = [d.rel for d in lib.docs]
    if scope in rels or any(r.startswith(scope + "/") for r in rels):
        return scope
    if scope + ".md" in rels:
        return scope + ".md"
    folders = sorted({r.split("/", 1)[0] for r in rels if "/" in r})
    raise UnknownScope(
        "%r is not a folder or document of the documentation: give all, a folder (%s) or a "
        "document such as handbook.md (docs_read with path index lists them)."
        % (scope, ", ".join(folders))
    )


def parse_target(target):
    """A docs_read target -> ("doc", relative path, anchor) or ("golden", id, "").
    Accepts sciforge://docs/<path>[#anchor], sciforge://examples/golden/<id>, a path under the
    docs root ("recipes/bracket.md#holes") or golden/<id>."""
    if not isinstance(target, str) or not target.strip():
        return None
    text = target.strip()
    if text.startswith(GOLDEN_URI):
        return ("golden", text[len(GOLDEN_URI) :].strip("/"), "")
    if text.startswith("golden/"):
        return ("golden", text[len("golden/") :].replace(".json", "").strip("/"), "")
    if text.startswith(DOCS_URI):
        text = text[len(DOCS_URI) :]
    elif text.startswith(TOOLS_URI):  # a tool's MCP resource: its reference page
        name, _sep, anchor = text[len(TOOLS_URI) :].partition("#")
        return ("doc", "reference/%s.md" % name.strip("/"), anchor.strip())
    elif text.rstrip("/") == "sciforge://tools":
        return ("doc", "tools.md", "")
    elif text.startswith("sciforge://handbook"):  # every document in one file: the list
        return ("doc", "index", "")
    elif text.startswith("sciforge://"):
        return None
    rel, _sep, anchor = text.partition("#")
    return ("doc", rel.strip().lstrip("./"), anchor.strip())


def safe_rel(rel, root):
    """The absolute path of a document inside root, or None (no .., no hidden parts)."""
    root = os.path.realpath(root)
    if not rel or rel.startswith(("/", "\\")) or "\\" in rel or ":" in rel:
        return None
    parts = rel.split("/")
    if any(p in ("", ".", "..") or p.startswith(".") for p in parts):
        return None
    full = os.path.realpath(os.path.join(root, *parts))
    if not full.startswith(root + os.sep) or not os.path.isfile(full):
        return None
    if os.path.splitext(full)[1].lower() not in DOC_TYPES:
        return None
    return full


class NotFound(Exception):
    """docs_read was given something that is not there; the message says what is."""


def _pages(text, size):
    """The text cut into pages of at most `size` characters, at line ends."""
    if len(text) <= size:
        return [text]
    pages, current, length = [], [], 0
    for line in text.split("\n"):
        while len(line) > size:  # (a single very long line)
            if current:
                pages.append("\n".join(current))
                current, length = [], 0
            pages.append(line[:size])
            line = line[size:]
        if length + len(line) + 1 > size and current:
            pages.append("\n".join(current))
            current, length = [], 0
        current.append(line)
        length += len(line) + 1
    if current:
        pages.append("\n".join(current))
    return pages


def _close_names(name, choices, n=5):
    import difflib

    return difflib.get_close_matches(name, list(choices), n=n, cutoff=0.4)


def read(target, page=1, page_chars=PAGE_CHARS, toc=None, lib=None):
    """docs_read: {uri, title, section, page, pages, text, sections?}. A section (an anchor
    after #) is that heading and everything under it. Raises NotFound with a sentence that
    names what exists."""
    lib = lib or library()
    parsed = parse_target(target)
    if parsed is None:
        raise NotFound(
            "%r is not a document: give a path such as handbook.md or recipes/bracket.md "
            "(docs_search finds them), a URI sciforge://docs/<path>, or "
            "sciforge://examples/golden/<id>." % (target,)
        )
    kind, rel, anchor = parsed
    if kind == "doc" and rel in ("index", "index.md") and lib.doc(rel) is None:
        text = index_text(lib)
        pages = _pages(text, page_chars)
        page = min(max(1, int(page)), len(pages))
        return {
            "uri": DOCS_URI + "index",
            "title": "SciForge documentation for AI models",
            "section": "",
            "page": page,
            "pages": len(pages),
            "text": pages[page - 1],
        }
    if kind == "golden":
        models = {m["id"]: m for m in golden_models(lib.golden)}
        model = models.get(rel)
        if model is None:
            near = _close_names(rel, models)
            raise NotFound(
                "There is no golden model %r.%s examples_search finds them."
                % (rel, " Close: %s." % ", ".join(near) if near else "")
            )
        with open(model["path"], encoding="utf-8") as handle:
            data = json.load(handle)
        tools_of = op_tools()
        made_by = {op: tools_of.get(op, []) for op in model["ops"]}
        head = (
            "Golden model %s: %s. Its steps are SciForge's design-step language (what the AI "
            "tools build), not tool calls; the tools that build each op: %s. expect holds the "
            "measurements the finished part has (expect.note says where they come from)."
            % (
                model["id"],
                model["title"],
                "; ".join(
                    "%s: %s" % (op, ", ".join(t) or "(a test helper, no tool)")
                    for op, t in made_by.items()
                ),
            )
        )
        text = head + "\n" + _compact(data)
        pages = _pages(text, page_chars)
        page = min(max(1, int(page)), len(pages))
        return {
            "uri": GOLDEN_URI + model["id"],
            "title": model["title"],
            "section": "",
            "page": page,
            "pages": len(pages),
            "text": pages[page - 1],
        }
    doc = lib.doc(rel)
    if doc is None or safe_rel(rel, lib.root) is None:
        near = _close_names(rel, lib.by_rel)
        raise NotFound(
            "There is no document %r.%s docs_search finds documents; sciforge://docs/index "
            "lists them all." % (rel, " Close: %s." % ", ".join(near) if near else "")
        )
    text = doc.text
    section_title = ""
    if anchor:
        sec = lib.find_section(rel, anchor)
        if sec is None:
            near = _close_names(anchor, lib.anchors(rel))
            raise NotFound(
                "%s has no section #%s.%s Read it without # to see its sections."
                % (rel, anchor, " Close: %s." % ", ".join("#" + n for n in near) if near else "")
            )
        lines = text.split("\n")
        text = "\n".join(lines[sec["start"] : sec["end"]]).strip("\n")
        section_title = sec["title"]
    pages = _pages(text, page_chars)
    page = min(max(1, int(page)), len(pages))
    out = {
        "uri": doc.uri + ("#" + anchor if anchor else ""),
        "title": doc.title,
        "section": section_title,
        "page": page,
        "pages": len(pages),
        "text": pages[page - 1],
    }
    if toc or (toc is None and not anchor and page == 1 and len(pages) > 1):
        out["sections"] = [
            {"anchor": s["anchor"], "title": s["title"], "level": s["level"]}
            for s in lib.sections_of(rel)
            if s["level"]
        ][:300]
    return out


def index_text(lib=None):
    """Every document with its title, as a Markdown list."""
    lib = lib or library()
    lines = ["# SciForge documentation for AI models", ""]
    for doc in lib.docs:
        lines.append("- %s: %s" % (doc.rel, doc.title))
    count = len(golden_models(lib.golden))
    if count:
        lines += [
            "",
            "Golden models: %d, read as golden/<id> (examples/golden-models.md lists them by "
            "feature)." % count,
        ]
    return "\n".join(lines) + "\n"


def examples(query="", tool=None, op=None, tag=None, kind="all", limit=10, lib=None):
    """examples_search: recipes (tested tool-call sequences) and golden models (design-step
    lists with measured results) that match. Returns {results: [...], total}."""
    lib = lib or library()
    pool = lib.examples()

    def keep(ex):
        if kind not in (None, "", "all") and ex["kind"] != kind:
            return False
        if tool and tool not in ex["tools"]:
            return False
        if op and op not in ex["ops"]:
            return False
        if tag and tag.lower() not in [t.lower() for t in ex["tags"]]:
            return False
        return True

    query_words = words(query or "")
    if query_words:
        ranked = [
            (score, unit.extra)
            for score, unit in lib.example_index().scores(query_words)
            if keep(unit.extra)
        ]
    else:
        ranked = [
            (0.0, ex)
            for ex in sorted(pool, key=lambda e: (e["kind"] != "recipe", e["id"]))
            if keep(ex)
        ]
    results = []
    for score, ex in ranked[: max(1, int(limit))]:
        row = {k: v for k, v in ex.items() if not k.startswith("_")}
        if query_words:
            row["score"] = round(score, 3)
        if len(row.get("note", "")) > 300:
            row["note"] = row["note"][:297] + "..."
        results.append(row)
    return {"results": results, "total": len(ranked)}


# -- for prompts and files ------------------------------------------------------------------------
def prompt_index(lib=None, max_chars=3000):
    """A short list of the documentation for a system prompt: what to read when."""
    lib = lib or library()
    if not lib.docs:
        return ""
    lines = [
        "SciForge's documentation for you (search it with docs_search, read a document or one "
        "section with docs_read, find tested examples with examples_search; read a tool's "
        "reference page before using its less common options):"
    ]
    recipes, reference, user, other = [], 0, 0, []
    for doc in lib.docs:
        if doc.rel.startswith("recipes/") and doc.rel != "recipes/index.md":
            recipes.append(os.path.splitext(os.path.basename(doc.rel))[0])
        elif doc.rel.startswith("reference/"):
            reference += 1
        elif doc.rel.startswith("user/"):
            user += 1
        else:
            other.append("- %s: %s" % (doc.rel, doc.title))
    lines += other
    if recipes:
        lines.append("- recipes/<name>.md, tested step-by-step tool calls: %s" % ", ".join(recipes))
    if reference:
        lines.append(
            "- reference/<tool>.md: one page per tool (%d), every argument with its type, "
            "unit, default and limits, the errors, and a complete example call with its "
            "real answer" % reference
        )
    if user:
        lines.append(
            "- user/...: SciForge's own documentation for people (%d documents: cheat sheet, "
            "known issues, feature outline, one Fusion parity spec per feature)" % user
        )
    text = "\n".join(lines)
    if len(text) > max_chars:
        text = text[: max_chars - 4].rsplit("\n", 1)[0] + "\n..."
    return text


EXPORT_TITLE = "SciForge for AI models (all the documentation in one file)"


def export_text(full=False, lib=None, compact=False):
    """Every document in one Markdown file, for AI apps that load files. Leaves out the copy
    of the user documentation (user/) unless full; compact also leaves out the reference
    pages and the golden model index (the handbook, guides, recipes and tools.md stay). A
    link sciforge://docs/<path> points to the part of this file headed "File: <path>"."""
    lib = lib or library()

    def wanted(doc):
        if doc.kind != "text/markdown":
            return False
        if doc.rel.startswith("user/"):
            return bool(full)
        if compact and doc.rel.startswith(("reference/", "examples/")):
            return False
        return True

    chosen = [d for d in lib.docs if wanted(d)]
    what = "the handbook, the guides, the recipes and the list of tools"
    if not compact:
        what = "the handbook, the guides, the recipes, the reference page of every tool"
    if full:
        what += " and SciForge's documentation for people"
    out = [
        "# " + EXPORT_TITLE,
        "",
        "SciForge is a parametric CAD program built on FreeCAD that works like Autodesk "
        "Fusion. This file holds SciForge's documentation for AI models: %s. Each part "
        'starts with a line "File: <path>"; a link sciforge://docs/<path> in the text means '
        "that part. When SciForge's MCP server is connected, the same documents are "
        "resources and the tools docs_search / docs_read / examples_search search them." % what,
        "",
        "## Contents",
        "",
    ]
    for doc in chosen:
        out.append("- File: %s (%s)" % (doc.rel, doc.title))
    for doc in chosen:
        text = doc.text.rstrip("\n")
        out += ["", "---", "", "File: %s" % doc.rel, "", text]
    return "\n".join(out).rstrip() + "\n"


# -- the tools ------------------------------------------------------------------------------------
TOOLS = ("docs_search", "docs_read", "examples_search")


def _compact(value):
    from . import bridge_core

    return bridge_core.compact_json(value)


def tool_answer(tool, args, lib=None):
    """The answer of docs_search / docs_read / examples_search: (text, is_error). Never
    raises (a broken docs folder is told in a sentence)."""
    args = args if isinstance(args, dict) else {}
    try:
        lib = lib or library()
        if not lib.docs and tool != "examples_search":
            return (
                "SciForge's documentation for AI models is not installed here (%s is empty)."
                % lib.root,
                True,
            )
        if tool == "docs_search":
            try:
                found = search(
                    args.get("query", ""),
                    int(args.get("limit", 8)),
                    args.get("scope", "all"),
                    lib=lib,
                )
            except UnknownScope as exc:
                return str(exc), True
            if not found["results"]:
                return (
                    "Nothing in the documentation matches %r%s. Try other or fewer words; "
                    "docs_read with path index lists every document."
                    % (
                        found["query"],
                        "" if args.get("scope", "all") == "all" else " in %s" % args["scope"],
                    ),
                    False,
                )
            head = "%d of %d matching sections (read one with docs_read and its path):" % (
                len(found["results"]),
                found["total"],
            )
            return head + "\n" + _compact(found), False
        if tool == "docs_read":
            target = args.get("path", "")
            if args.get("section") and "#" not in target:
                target = target + "#" + str(args["section"]).lstrip("#")
            got = read(target, int(args.get("page", 1)), lib=lib)
            where = got["uri"]
            head = "%s (%s)%s, page %d of %d%s:" % (
                where,
                got["title"],
                ", section %s" % got["section"] if got["section"] else "",
                got["page"],
                got["pages"],
                "; ask page %d for more" % (got["page"] + 1) if got["page"] < got["pages"] else "",
            )
            text = head + "\n\n" + got["text"].rstrip("\n")
            if got.get("sections"):
                text += "\n\nSections (give one as section, or path#anchor):\n" + "\n".join(
                    "%s#%s %s" % ("  " * (s["level"] - 1), s["anchor"], s["title"])
                    for s in got["sections"]
                )
            return text, False
        if tool == "examples_search":
            found = examples(
                args.get("query", ""),
                args.get("tool"),
                args.get("op"),
                args.get("tag"),
                args.get("kind", "all"),
                int(args.get("limit", 10)),
                lib=lib,
            )
            if not found["results"]:
                return (
                    "No example matches. Try fewer words, or kind recipe / golden alone.",
                    False,
                )
            head = (
                "%d of %d examples (read one with docs_read and its uri; a golden model's "
                "steps are design steps, the tools that build them are listed):"
                % (len(found["results"]), found["total"])
            )
            return head + "\n" + _compact(found), False
        return "There is no documentation tool called %r." % tool, True
    except NotFound as exc:
        return str(exc), True
    except Exception as exc:  # never let a docs problem end a tool call badly
        return "SciForge could not read its documentation: %s" % exc, True
