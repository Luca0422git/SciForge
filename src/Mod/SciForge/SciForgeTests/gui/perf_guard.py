# SPDX-License-Identifier: LGPL-2.1-or-later
"""The speed benchmarks' regression guard (perf_benchmark.py, perf_big_model.py): compare
this run's times with a stored baseline and list every action that got much slower.

Plain Python (no FreeCAD), so the unit tests check it (test_perf_guard.py).

A baseline is either a benchmark report (perf-report.json, perf-big-report.json: a
"results" list of {"label", "change", ...}) or a plain {"label": seconds} map; SciForge
keeps one in SciForgeTests/gui/perf_baseline.json, measured on the sandbox the tests run in.
Machines differ, so by default a slower action is only a warning in the report and the log;
SCIFORGE_PERF_STRICT=1 makes the benchmark fail on it (for a run on the same machine as the
baseline). SCIFORGE_PERF_BASELINE names another baseline file; "none" switches the guard off.
SCIFORGE_PERF_WRITE_BASELINE=<file> stores this run's times there (merged with what the file
already holds: both benchmarks can share one baseline).

The reports also show, next to each time, the baseline's and the one from before the speed work
on big designs (SciForgeTests/gui/perf_before.json: perf_big_model measured at commit 0b1da82,
2026-10-21), so a report says by itself how far things have come (columns()).
"""
import json
import os

FACTOR = 2.0  # "much slower": more than twice the baseline's time
FLOOR = 0.005  # differences under 5 ms are noise (timer jitter, a garbage collection)
DEFAULT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "perf_baseline.json")
BEFORE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "perf_before.json")


def baseline_path(environ=None):
    """The baseline to compare with: SCIFORGE_PERF_BASELINE, else the stored one when it
    exists; None when there is none (or the variable says "none")."""
    env = os.environ if environ is None else environ
    path = (env.get("SCIFORGE_PERF_BASELINE") or "").strip()
    if path.lower() in ("none", "off", "0"):
        return None
    if path:
        return path
    return DEFAULT if os.path.exists(DEFAULT) else None


def strict(environ=None):
    env = os.environ if environ is None else environ
    return (env.get("SCIFORGE_PERF_STRICT") or "").strip().lower() in ("1", "true", "yes", "on")


def times_of(data):
    """{label: seconds} from a report (its "results") or a plain map; measurements that
    failed (an "error") or have no time are left out."""
    if isinstance(data, dict) and isinstance(data.get("results"), list):
        rows = data["results"]
    elif isinstance(data, list):
        rows = data
    elif isinstance(data, dict):
        out = {}
        for key, value in data.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                out[str(key)] = float(value)
        return out
    else:
        return {}
    out = {}
    for row in rows:
        if not isinstance(row, dict) or "error" in row:
            continue
        value = row.get("change")
        if isinstance(value, (int, float)) and not isinstance(value, bool) and "label" in row:
            out[str(row["label"])] = float(value)
    return out


def load(path):
    """The baseline's {label: seconds}; {} when the file is missing or unreadable."""
    if not path:
        return {}
    try:
        with open(path, encoding="utf-8") as handle:
            return times_of(json.load(handle))
    except (OSError, ValueError):
        return {}


def compare(results, path, factor=FACTOR, floor=FLOOR, environ=None):
    """The guard's verdict for this run's results against the baseline file at `path`:
    {"baseline": path, "strict": bool, "compared": n, "slower": [{label, now, before,
    ratio}], "missing": [labels in the baseline not measured now]}."""
    before = load(path)
    now = times_of(results)
    slower = []
    for label, seconds in sorted(now.items()):
        old = before.get(label)
        if old is None:
            continue
        if seconds > factor * old and seconds - old > floor:
            ratio = seconds / old if old > 0 else float("inf")
            slower.append({"label": label, "now": seconds, "before": old, "ratio": ratio})
    slower.sort(key=lambda r: -r["ratio"])
    return {
        "baseline": path,
        "strict": strict(environ),
        "compared": len([k for k in now if k in before]),
        "slower": slower,
        "missing": sorted(k for k in before if k not in now),
    }


def passed(guard):
    """False only when the guard is strict and something got much slower."""
    return not (guard.get("strict") and guard.get("slower"))


def baseline_of(results):
    """A plain {label: seconds} baseline to store from this run's results."""
    return times_of(results)


def write_baseline(results, environ=None):
    """With SCIFORGE_PERF_WRITE_BASELINE set: this run's {label: seconds} merged into that
    file. Returns the path written, or None."""
    env = os.environ if environ is None else environ
    path = (env.get("SCIFORGE_PERF_WRITE_BASELINE") or "").strip()
    if not path:
        return None
    data = load(path)
    data.update(baseline_of(results))
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({k: round(v, 4) for k, v in sorted(data.items())}, handle, indent=1)
        handle.write("\n")
    return path


def markdown(guard):
    """The guard's lines for the report (and the log)."""
    if not guard.get("baseline"):
        return ["Speed guard: no baseline to compare with (SCIFORGE_PERF_BASELINE)."]
    if not guard.get("compared"):
        return ["Speed guard: the baseline %s has none of these measurements." % guard["baseline"]]
    if not guard.get("slower"):
        return [
            "Speed guard: %d measurements compared with %s, none more than %gx slower."
            % (guard["compared"], guard["baseline"], FACTOR)
        ]
    word = "FAIL" if guard.get("strict") else "WARNING"
    lines = [
        "Speed guard %s: %d of %d measurements more than %gx slower than %s:"
        % (word, len(guard["slower"]), guard["compared"], FACTOR, guard["baseline"])
    ]
    for row in guard["slower"]:
        lines.append(
            "- %s: %.1f ms, was %.1f ms (%.1fx)"
            % (row["label"], row["now"] * 1000.0, row["before"] * 1000.0, row["ratio"])
        )
    return lines


def columns(guard, before_path=BEFORE):
    """For the report's table: a function label -> (baseline, before) as text in milliseconds
    ("" when that file has no such measurement): the stored baseline the guard compared with,
    and the time measured before the speed work on big designs."""
    base = load(guard.get("baseline"))
    before = load(before_path)

    def cells(label):
        return tuple(
            "%.1f" % (times[label] * 1000.0) if label in times else "" for times in (base, before)
        )

    return cells
