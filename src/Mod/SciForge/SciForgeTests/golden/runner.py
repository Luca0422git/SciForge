# SPDX-License-Identifier: LGPL-2.1-or-later
"""Runs the golden models in real FreeCAD and writes a report.

Run headless (this is what CI and tools/sciforge/run_tests.sh do):

    freecadcmd -c "from SciForgeTests.golden import runner; runner.main()"

Environment variables:
    SCIFORGE_GOLDEN_OUT     folder for golden-report.json / .md (default: user data dir)
    SCIFORGE_GOLDEN_FILTER  only run models whose id contains this text

A model passes when every expected measurement matches. Models with an
"xfail" field document a known gap (e.g. a kernel limitation): they are
reported as XFAIL while they fail and as XPASS (attention!) when they start
passing, and neither fails the run.

Models with an "upstream_bug" field hit a bug in stock FreeCAD that SciForge
fixes in its fork. Run against stock FreeCAD they behave like "xfail"; run in
a SciForge build they must pass like any other model.
"""
import glob
import json
import os
import platform
import time
import traceback

from . import schema

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(HERE, "models")
DEFAULT_REL_TOL = 1e-6
DEFAULT_ABS_TOL = 1e-4


def load_models(folder=MODELS_DIR, text_filter=""):
    models = []
    for path in sorted(glob.glob(os.path.join(folder, "*.json"))):
        with open(path, "r", encoding="utf-8") as handle:
            model = json.load(handle)
        schema.validate(model)
        expected_id = os.path.splitext(os.path.basename(path))[0]
        if model["id"] != expected_id:
            raise schema.ModelError("%s: id %r must match the file name" % (path, model["id"]))
        if text_filter and text_filter not in model["id"]:
            continue
        models.append(model)
    return models


def measure(shape):
    try:
        box = shape.optimalBoundingBox(False, False)
    except Exception:
        box = shape.BoundBox
    return {
        "volume": shape.Volume,
        "area": shape.Area,
        "bbox": [box.XMin, box.YMin, box.ZMin, box.XMax, box.YMax, box.ZMax],
        "faces": len(shape.Faces),
        "edges": len(shape.Edges),
        "solids": len(shape.Solids),
        "valid": shape.isValid(),
    }


def compare(expect, got):
    """List of human-readable mismatches (empty list = match)."""
    rel = expect.get("rel_tol", DEFAULT_REL_TOL)
    absolute = expect.get("abs_tol", DEFAULT_ABS_TOL)
    problems = []
    for key in ("volume", "area"):
        if key in expect:
            want, have = expect[key], got[key]
            if abs(have - want) > max(rel * abs(want), absolute):
                problems.append(
                    "%s: expected %.6g, got %.6g (%+.4f%%)"
                    % (key, want, have, 100.0 * (have - want) / want)
                )
    if "bbox" in expect:
        diffs = [abs(a - b) for a, b in zip(expect["bbox"], got["bbox"])]
        if max(diffs) > absolute:
            problems.append(
                "bbox: expected %s, got %s" % (expect["bbox"], [round(v, 6) for v in got["bbox"]])
            )
    for key in ("faces", "edges", "solids"):
        if key in expect and expect[key] != got[key]:
            problems.append("%s: expected %d, got %d" % (key, expect[key], got[key]))
    if expect.get("valid", True) and not got["valid"]:
        problems.append("shape is not a valid solid (BRepCheck failed)")
    return problems


def is_sciforge_build():
    """True when SciForge is built into this FreeCAD (not added as a user add-on)."""
    import FreeCAD as App

    return os.path.isdir(os.path.join(App.getHomePath(), "Mod", "SciForge"))


def run_model(model, sciforge_build=False):
    import FreeCAD as App

    from .builder import Builder

    result = {
        "id": model["id"],
        "title": model["title"],
        "tags": model.get("tags", []),
        "status": "error",
        "problems": [],
        "steps": [],
    }
    doc = App.newDocument("golden_" + model["id"])
    start = time.time()
    try:
        builder = Builder(doc)
        for index, step in enumerate(model["steps"]):
            t0 = time.time()
            if step["op"] == "check":
                got = measure(builder.shape())
                problems = compare(step["expect"], got)
                result["problems"].extend("after step %d: %s" % (index, p) for p in problems)
            else:
                builder.run(step)
            result["steps"].append(
                {"op": step["op"], "id": step.get("id"), "seconds": round(time.time() - t0, 4)}
            )
        got = measure(builder.shape())
        result["measured"] = got
        result["problems"].extend(compare(model["expect"], got))
        result["status"] = "pass" if not result["problems"] else "fail"
    except Exception as exc:
        result["problems"].append("%s: %s" % (type(exc).__name__, exc))
        result["traceback"] = traceback.format_exc()
        result["status"] = "error"
    finally:
        result["seconds"] = round(time.time() - start, 3)
        App.closeDocument(doc.Name)

    reason = model.get("xfail")
    if not reason and model.get("upstream_bug") and not sciforge_build:
        reason = "stock FreeCAD bug, fixed in SciForge: " + model["upstream_bug"]
    if reason:
        result["xfail_reason"] = reason
        result["status"] = "xpass" if result["status"] == "pass" else "xfail"
    return result


def summarize(results):
    counts = {}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    return counts


def markdown(report):
    icons = {
        "pass": "PASS",
        "fail": "**FAIL**",
        "error": "**ERROR**",
        "xfail": "xfail",
        "xpass": "**XPASS**",
    }
    lines = [
        "# Golden-model report",
        "",
        "%s %s, %s. %s"
        % (
            "SciForge build of FreeCAD" if report["sciforge_build"] else "Stock FreeCAD",
            report["freecad"],
            report["platform"],
            ", ".join("%s: %d" % kv for kv in sorted(report["summary"].items())),
        ),
        "",
        "| Model | Result | Time (s) | Details |",
        "|---|---|---|---|",
    ]
    for r in report["results"]:
        detail = "; ".join(r["problems"]) or ""
        if r.get("xfail_reason"):
            detail = ("known gap: %s. " % r["xfail_reason"]) + detail
        lines.append(
            "| `%s` %s | %s | %.2f | %s |"
            % (r["id"], r["title"], icons[r["status"]], r["seconds"], detail.replace("|", "/"))
        )
    return "\n".join(lines) + "\n"


def main():
    import FreeCAD as App

    out_dir = os.environ.get("SCIFORGE_GOLDEN_OUT") or App.getUserAppDataDir()
    os.makedirs(out_dir, exist_ok=True)
    sciforge_build = is_sciforge_build()
    report = {
        "freecad": ".".join(App.Version()[:3]),
        "platform": platform.platform(),
        "sciforge_build": sciforge_build,
        "results": [],
    }
    try:
        models = load_models(text_filter=os.environ.get("SCIFORGE_GOLDEN_FILTER", ""))
    except Exception as exc:
        report["results"].append(
            {
                "id": "model-files",
                "title": "loading model files",
                "status": "error",
                "problems": [str(exc)],
                "seconds": 0.0,
            }
        )
        models = []
    for model in models:
        result = run_model(model, sciforge_build)
        report["results"].append(result)
        App.Console.PrintMessage(
            "[SciForge] golden %-6s %s %s\n"
            % (result["status"].upper(), model["id"], "; ".join(result["problems"]))
        )
    report["summary"] = summarize(report["results"])
    report["passed"] = all(r["status"] in ("pass", "xfail", "xpass") for r in report["results"])
    with open(os.path.join(out_dir, "golden-report.json"), "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
    with open(os.path.join(out_dir, "golden-report.md"), "w", encoding="utf-8") as handle:
        handle.write(markdown(report))
    App.Console.PrintMessage("[SciForge] golden summary: %s\n" % report["summary"])
    return report
