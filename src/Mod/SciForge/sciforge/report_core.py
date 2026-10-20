# SPDX-License-Identifier: LGPL-2.1-or-later
"""Report a Problem, the part without FreeCAD and Qt (unit tested:
SciForgeTests/unit/test_report_core.py). report_ui.py is the dialog.

  * redact(): what leaves the computer never carries the person's folder names, user name or
    anything that looks like an API key (the report is shown in full before anything is
    sent, and this is the second line of defence);
  * body(): the text of the report (Save and Copy), laid out the same every time;
  * issue_url(): the GitHub "new issue" address with the form's fields filled in. GitHub's
    issue forms take the fields' ids as address parameters; the ids are the ones of
    .github/ISSUE_TEMPLATE/bug_report.yml. A field the form does not have is ignored by
    GitHub, so a form that differs only loses that one pre-filled field.
Nothing here sends anything: the browser does that, after the person has seen it.
"""

import re
from urllib.parse import quote

REPO = "Luca0422git/SciForge"
NEW_ISSUE = "https://github.com/%s/issues/new" % REPO
TEMPLATE = "bug_report.yml"
URL_LIMIT = 7000  # browsers and GitHub refuse much more than this in an address
PASTE_NOTE = "(The whole report is on your clipboard: paste it here with Ctrl+V.)"
CUT_NOTE = "... (cut: the rest is in the saved report / clipboard)"
TITLE_MAX = 80

# The ids of the form's fields (.github/ISSUE_TEMPLATE/bug_report.yml).
FIELD_ID = {
    "what": "what_happened",
    "expected": "expected",
    "steps": "steps",
    "diagnostics": "diagnostics",
    "version": "version",
    "system": "system",
}

# -- redaction --------------------------------------------------------------------------------
_SECRET_WORDS = (
    r"api[ _-]?key|apikey|access[ _-]?key|secret[ _-]?key|private[ _-]?key|key|token|secret"
    r"|password|passwd|authorization|bearer"
)
_KEY_SHAPES = [
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{8,}"),  # Anthropic
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_\-]{16,}"),  # OpenAI and alike
    re.compile(r"AIza[0-9A-Za-z_\-]{20,}"),  # Google
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),  # GitHub
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"xox[abprs]-[A-Za-z0-9\-]{10,}"),  # Slack
    re.compile(r"AKIA[0-9A-Z]{16}"),  # Amazon
    re.compile(r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]*"),  # a JWT
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/\-]{16,}=*"),
]
# "key = 4f9a...", "token: AbC...", "password is hunter2hunter2..." : the word stays, the
# long value after it goes
_AFTER_WORD = re.compile(
    r"(?i)\b(%s)(\b[\"']?\s*(?:[:=]|\bis\b)?\s*[\"']?)([A-Za-z0-9+/_\-=.]{24,})" % _SECRET_WORDS
)
KEY_GONE = "<key removed>"

_WINDOWS_HOME = re.compile(r"(?i)\b[A-Za-z]:[\\/]+Users[\\/]+([^\\/\s\"'<>|:*?,;()\[\]]+)")
_UNIX_HOME = re.compile(r"(?<![A-Za-z0-9_.\-])/(?:home|Users)/([^/\s\"'<>|:*?,;()\[\]]+)")
_NOT_USERS = {"public", "default", "default user", "all users", "shared", "guest"}
# user names that are also plain words: replacing them everywhere would wreck the text
_PLAIN_NAMES = {"user", "admin", "root", "test", "guest", "home", "default", "public", "me"}


def _home_forms(home):
    """The ways a home folder can be written in a log: as given, with / and with \\, with
    doubled backslashes (a Python repr), without a trailing separator."""
    if not home:
        return []
    base = home.rstrip("\\/")
    if len(base) < 3:
        return []
    forms = {base, base.replace("\\", "/"), base.replace("/", "\\")}
    forms |= {f.replace("\\", "\\\\") for f in list(forms)}
    return sorted(forms, key=len, reverse=True)


def _end_of_name():
    return r"(?![A-Za-z0-9_\-])"


def redact_secrets(text):
    """API keys and tokens replaced by "<key removed>" (the word before a value stays)."""
    if not text:
        return text or ""
    for shape in _KEY_SHAPES:
        text = shape.sub(KEY_GONE, text)

    def after_word(match):
        value = match.group(3)
        # a long run with a digit in it (or very long) is a key; a long plain word is not
        if re.search(r"[0-9]", value) or len(value) >= 40:
            return match.group(1) + match.group(2) + KEY_GONE
        return match.group(0)

    return _AFTER_WORD.sub(after_word, text)


def redact(text, home="", user="", bare_user=True):
    """`text` with the home folder as "~", other people's home folders too ("C:\\Users\\x",
    "/home/x"), the user name as "<user>" (when bare_user; a typed sentence keeps it) and
    keys removed."""
    if not text:
        return text or ""
    try:
        for form in _home_forms(home):
            flags = re.IGNORECASE if re.match(r"^[A-Za-z]:", form) else 0
            text = re.sub(re.escape(form) + _end_of_name(), lambda m: "~", text, flags=flags)

        def windows(match):
            return match.group(0) if match.group(1).lower() in _NOT_USERS else "~"

        text = _WINDOWS_HOME.sub(windows, text)
        text = _UNIX_HOME.sub(lambda m: "~", text)
        text = redact_secrets(text)
        name = (user or "").strip()
        if bare_user and len(name) >= 3 and name.lower() not in _PLAIN_NAMES:
            text = re.sub(
                r"(?i)(?<![A-Za-z0-9_])" + re.escape(name) + r"(?![A-Za-z0-9_])", "<user>", text
            )
        return text
    except Exception:
        return text


# -- the report ---------------------------------------------------------------------------------
def first_line(text, limit=TITLE_MAX):
    for row in (text or "").splitlines():
        row = row.strip()
        if row:
            return row if len(row) <= limit else row[: limit - 3].rstrip() + "..."
    return ""


def make(
    what,
    expected,
    version,
    system,
    diagnostics,
    recent,
    crash_name="",
    crash_text="",
    home="",
    user="",
):
    """The report: {"text": everything (Save, Copy, the preview), "fields": the form's
    parts, "title": ...}. Everything is redacted here, so no caller can forget to."""

    def own(text):  # typed by the person: paths and keys go, their words stay
        return redact(text.strip(), home, user, bare_user=False)

    def machine(text):
        return redact(text.strip("\n"), home, user)

    what_t, expected_t = own(what or ""), own(expected or "")
    version_t, system_t = machine(version or ""), machine(system or "")
    detail = [machine(diagnostics or "").rstrip()]
    recent_t = machine("\n".join(recent or [])).rstrip()
    detail.append("Recent SciForge messages (newest last):")
    detail.append(recent_t if recent_t else "(none)")
    if crash_text:
        detail.append("Crash log %s (last lines):" % (crash_name or ""))
        detail.append(machine(crash_text).rstrip())
    diagnostics_t = "\n\n".join(detail).strip()
    parts = [
        "SciForge problem report",
        "=" * 23,
        "Version: %s" % version_t,
        "System:\n%s" % system_t,
        "",
        "What happened",
        "-" * 13,
        what_t or "(nothing written)",
        "",
        "What I expected",
        "-" * 15,
        expected_t or "(not said)",
        "",
        "Diagnostics",
        "-" * 11,
        diagnostics_t,
    ]
    fields = {
        "what": what_t,
        "expected": expected_t,
        "version": version_t,
        "system": system_t,
        "diagnostics": diagnostics_t,
    }
    return {
        "text": "\n".join(parts).rstrip() + "\n",
        "fields": fields,
        "title": "[Bug] " + first_line(what_t),
    }


SYSTEM_OPTIONS = ("Windows 11", "Windows 10", "Linux", "Something else (tell us below)")


def system_option(text):
    """The issue form's "Operating system" is a dropdown: GitHub only fills it from the exact
    text of one of its options (.github/ISSUE_TEMPLATE/bug_report.yml), so the long system
    text becomes one of those four."""
    text = text or ""
    build = re.search(r"Windows[^\n]*?10\.0\.(\d+)", text)
    if build:  # Windows 11 still calls itself 10; its builds start at 22000
        return SYSTEM_OPTIONS[0] if int(build.group(1)) >= 22000 else SYSTEM_OPTIONS[1]
    if "Windows 11" in text:
        return SYSTEM_OPTIONS[0]
    if "Windows 10" in text:
        return SYSTEM_OPTIONS[1]
    if "Linux" in text:
        return SYSTEM_OPTIONS[2]
    return SYSTEM_OPTIONS[3]


def _url(params):
    return (
        NEW_ISSUE
        + "?"
        + "&".join(
            "%s=%s" % (key, quote(str(value), safe="")) for key, value in params if value != ""
        )
    )


def issue_url(report, limit=URL_LIMIT):
    """(address, cut): the new-issue address with the report's fields. `cut` is the list of
    field names that did not fit whole (the diagnostics become a note to paste from the
    clipboard; if the address is still too long the other long fields are shortened). The
    address is never longer than `limit`."""
    fields = dict(report["fields"])
    cut = []

    def params():
        return [
            ("template", TEMPLATE),
            ("title", report["title"]),
            (FIELD_ID["what"], fields["what"]),
            (FIELD_ID["expected"], fields["expected"]),
            (FIELD_ID["version"], fields["version"]),
            (FIELD_ID["system"], system_option(fields["system"])),
            (FIELD_ID["diagnostics"], fields["diagnostics"]),
        ]

    if len(_url(params())) <= limit:
        return _url(params()), cut
    fields["diagnostics"] = PASTE_NOTE
    cut.append("diagnostics")
    for name in ("expected", "what"):
        if len(_url(params())) <= limit:
            break
        full = fields[name]
        low, high = 0, len(full)
        while low < high:  # the longest start of the text that still fits
            mid = (low + high + 1) // 2
            fields[name] = full[:mid].rstrip() + CUT_NOTE
            if len(_url(params())) <= limit:
                low = mid
            else:
                high = mid - 1
        fields[name] = full[:low].rstrip() + CUT_NOTE if low < len(full) else full
        if low < len(full):
            cut.append(name)
    url = _url(params())
    if len(url) > limit:  # (only possible with a huge version line): drop it
        fields["version"] = ""
        url = _url(params())
    return url, cut
