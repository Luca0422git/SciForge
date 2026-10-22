# SPDX-License-Identifier: LGPL-2.1-or-later
"""An AI agent's end-to-end test (docs/sciforge/dev/cadcraft-lessons.md idea 3, after
CADCraft's agent_draws_a_plate_with_holes): a real part is built ONLY through MCP and
checked ONLY through MCP, the way an AI app does it.

The MCP server is started as an AI app starts it (by default `tools/sciforge/sciforge-cli
mcp --headless`: SciForge without its window, the tools run in that process) and this
script speaks JSON-RPC to it over stdin / stdout. It makes a 60 x 40 x 10 plate (sketch,
extrude), a 6 mm hole through it, a row of three holes (pattern), rounds the top edges
(fillet), takes the fillet back and puts it again (undo / redo), makes the plate 12 mm
thick by editing the extrude in the timeline, and fails once on purpose. Every result is
checked with numbers from inspect_design, query_geometry, check_design, diff_design and the
resource sciforge://design, and render must return a PNG image as MCP image content.

    python3 agent_e2e.py [--out DIR] [-- SERVER COMMAND...]

tools/sciforge/run_tests.sh runs it with --only headless / base. It writes
agent-e2e-report.json / .md to --out; exit status 0 when every check passed. The GUI
scenario ai_agent_e2e runs the same SCRIPT against the running SciForge through the bridge.
Plain Python (the server is the one that needs FreeCAD).
"""

import argparse
import base64
import json
import math
import os
import queue
import re
import struct
import subprocess
import sys
import threading
import time
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
TIMEOUT = 180.0

PLATE = 60.0 * 40.0 * 10.0
HOLE_10 = math.pi * 3.0**2 * 10.0  # one 6 mm hole through 10 mm
TOP4 = {"type": "line", "at": {"axis": "z", "value": "max"}, "count": 4}
FILLET_LOSS = (150.0, 175.0)  # r = 2 on the 200 mm of top edges: about 200 * 4 * (1 - pi / 4)


class Mcp:
    """The AI app's side: one request at a time, answers read by a thread."""

    def __init__(self, command, env=None):
        self.proc = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
        self.answers = queue.Queue()
        self.next_id = 1
        self.stderr = []
        threading.Thread(target=self._read, daemon=True).start()
        threading.Thread(target=self._read_err, daemon=True).start()

    def _read(self):
        for line in self.proc.stdout:
            try:
                self.answers.put(json.loads(line))
            except ValueError:
                self.answers.put({"unreadable": line.decode("utf-8", "replace")})
        self.answers.put(None)

    def _read_err(self):
        for line in self.proc.stderr:
            self.stderr.append(line.decode("utf-8", "replace").rstrip())
            del self.stderr[:-200]

    def notify(self, method, params=None):
        message = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            message["params"] = params
        self.proc.stdin.write((json.dumps(message) + "\n").encode("utf-8"))
        self.proc.stdin.flush()

    def request(self, method, params=None):
        ident = self.next_id
        self.next_id += 1
        message = {"jsonrpc": "2.0", "id": ident, "method": method}
        if params is not None:
            message["params"] = params
        self.proc.stdin.write((json.dumps(message) + "\n").encode("utf-8"))
        self.proc.stdin.flush()
        end = time.time() + TIMEOUT
        while time.time() < end:
            try:
                answer = self.answers.get(timeout=max(0.1, end - time.time()))
            except queue.Empty:
                break
            if answer is None:
                raise RuntimeError("the MCP server stopped: %s" % "\n".join(self.stderr[-20:]))
            if answer.get("id") == ident:
                return answer
        raise RuntimeError("no answer to %s within %d s" % (method, TIMEOUT))

    def close(self):
        try:
            self.proc.stdin.close()
            self.proc.wait(30)
        except Exception:
            self.proc.kill()


# -- what the checks read ------------------------------------------------------------------------
def text_of(result):
    return " ".join(c.get("text", "") for c in result.get("content", []) if c["type"] == "text")


def json_of(result):
    text = text_of(result)
    start = text.find("{")
    return json.loads(text[start:]) if start >= 0 else None


def png_size(data):
    if data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        return None
    return struct.unpack(">II", data[16:24])


def png_rgb(data):
    """The pixels of a PNG (8-bit RGB or RGBA, not interlaced, any row filter: what SciForge's
    renderer and Qt write) as rows of (r, g, b), or None."""
    size = png_size(data)
    if size is None or data[24:25] != b"\x08" or data[25:26] not in (b"\x02", b"\x06"):
        return None
    if data[28:29] != b"\x00":
        return None
    width, height = size
    channels = 3 if data[25:26] == b"\x02" else 4
    pos, idat = 8, b""
    while pos < len(data):
        length = struct.unpack(">I", data[pos : pos + 4])[0]
        if data[pos + 4 : pos + 8] == b"IDAT":
            idat += data[pos + 8 : pos + 8 + length]
        pos += 12 + length
    raw = zlib.decompress(idat)
    stride = width * channels
    rows, prev = [], bytearray(stride)
    for y in range(height):
        kind = raw[y * (stride + 1)]
        line = bytearray(raw[y * (stride + 1) + 1 : (y + 1) * (stride + 1)])
        for i in range(stride):
            left = line[i - channels] if i >= channels else 0
            up = prev[i]
            corner = prev[i - channels] if i >= channels else 0
            if kind == 1:
                line[i] = (line[i] + left) & 255
            elif kind == 2:
                line[i] = (line[i] + up) & 255
            elif kind == 3:
                line[i] = (line[i] + (left + up) // 2) & 255
            elif kind == 4:
                p = left + up - corner
                pa, pb, pc = abs(p - left), abs(p - up), abs(p - corner)
                near = left if pa <= pb and pa <= pc else up if pb <= pc else corner
                line[i] = (line[i] + near) & 255
        rows.append([tuple(line[x * channels : x * channels + 3]) for x in range(width)])
        prev = line
    return rows


def orange_pixels(rows):
    """How many pixels are the highlight's orange (render_core.HIGHLIGHT, shaded)."""
    return sum(1 for row in rows for r, g, b in row if r > 200 and 90 < g < 180 and b < 80)


def made_id(result):
    match = re.search(r"Its id is '([^']+)'", text_of(result))
    return match.group(1) if match else None


class Agent:
    """Calls tools through a transport (MCP over stdio here, the bridge in the GUI
    scenario) and records every check."""

    def __init__(self, call, read=None):
        self.call_raw = call  # (tool, args) -> MCP CallToolResult dict
        self.read = read  # (uri) -> resources/read result or None
        self.results = []
        self.ids = {}

    def check(self, label, ok, detail=""):
        self.results.append({"check": label, "ok": bool(ok), "detail": str(detail)[:600]})
        return bool(ok)

    def call(self, tool, args=None, expect_error=False):
        result = self.call_raw(tool, args or {})
        bad = bool(result.get("isError")) != bool(expect_error)
        self.check(
            "%s %s" % (tool, "fails as it should" if expect_error else "works"),
            not bad,
            text_of(result)[:400],
        )
        return result

    def body(self):
        data = json_of(self.call("inspect_design"))
        bodies = [b for b in (data or {}).get("bodies", []) if b.get("solid")]
        return (bodies[0] if bodies else {}), data

    def volume_is(self, label, expected, rel=1e-6):
        body, data = self.body()
        got = body.get("volume_mm3")
        ok = got is not None and abs(got - expected) <= rel * max(1.0, abs(expected))
        self.check(label, ok, "expected %.6f, got %s" % (expected, got))
        return got, data


def script(agent, out_dir=None):
    """The part, built and checked only through tools (and resources when the transport
    has them). Returns the agent's results."""
    a = agent
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    # 1. nothing open yet (headless) or a fresh design (the app: new_design)
    a.call("new_design", {"name": "AgentPlate"})
    data = json_of(a.call("inspect_design"))
    solids = [b for b in (data or {}).get("bodies", []) if b.get("solid")]
    a.check("the new design has no solid", data is not None and not solids, data)
    # 2. the plate
    r = a.call(
        "create_sketch",
        {"plane": "XY", "geometry": [{"rect": [0, 0, 60, 40], "name": "plate"}]},
    )
    a.ids["sketch"] = made_id(r)
    r = a.call("extrude", {"profile": a.ids["sketch"], "distance": 10})
    a.ids["extrude"] = made_id(r)
    _vol, data = a.volume_is("the plate is 60 x 40 x 10 (24000 mm3)", PLATE)
    snapshot = (data or {}).get("snapshot")
    a.check("inspect_design gives a snapshot id", snapshot, data and data.get("snapshot"))
    body, _ = a.body()
    a.check("one valid solid", body.get("valid") and body.get("solids") == 1, body)
    a.check(
        "its bounding box is 60 x 40 x 10",
        (body.get("bbox_mm") or {}).get("size") == [60.0, 40.0, 10.0],
        body.get("bbox_mm"),
    )
    # 3. a hole through it, from a circle sketched on the top face (so it follows the face)
    r = a.call(
        "create_sketch",
        {"face": {"normal": [0, 0, 1], "count": 1}, "geometry": [{"circle": [12, 12, 3]}]},
    )
    a.ids["hole_sketch"] = made_id(r)
    r = a.call("hole", {"sketch": a.ids["hole_sketch"], "diameter": 6, "through_all": True})
    a.ids["hole"] = made_id(r)
    a.volume_is("the hole took pi * 3^2 * 10 away", PLATE - HOLE_10)
    diff = json_of(a.call("diff_design", {"since": "last_change"}))
    added = [s["id"] for s in (diff or {}).get("steps", {}).get("added", [])]
    a.check("diff_design last_change: the hole was added", a.ids["hole"] in added, diff)
    # 4. a row of three holes
    r = a.call(
        "pattern",
        {
            "kind": "rectangular",
            "features": [a.ids["hole"]],
            "direction": "X",
            "count": 3,
            "spacing": 18,
        },
    )
    a.ids["pattern"] = made_id(r)
    a.volume_is("three holes", PLATE - 3 * HOLE_10)
    found = json_of(a.call("query_geometry", {"select": {"type": "cylinder", "radius": 3}}))
    a.check("query_geometry finds three 6 mm holes", found and found["count"] == 3, found)
    xs = sorted(round(e["axis_point_mm"][0], 6) for e in (found or {}).get("elements", []))
    a.check("the holes are at x = 12, 30, 48", xs == [12.0, 30.0, 48.0], xs)
    a.check(
        "every hole has a ref",
        found and all(e.get("ref") for e in found["elements"]),
        found and [e.get("ref") for e in found["elements"]],
    )
    # 5. round the top edges, then undo / redo
    edges = json_of(a.call("query_geometry", {"element": "edges", "select": TOP4}))
    a.check(
        "query_geometry: the 4 top edges are 60, 40, 60, 40 mm",
        edges and sorted(e["length_mm"] for e in edges["elements"]) == [40.0, 40.0, 60.0, 60.0],
        edges,
    )
    before_fillet = PLATE - 3 * HOLE_10
    r = a.call("fillet", {"edges": TOP4, "radius": 2})
    a.ids["fillet"] = made_id(r)
    body, _ = a.body()
    filleted = body.get("volume_mm3") or 0.0
    loss = before_fillet - filleted
    a.check(
        "the fillet took %g to %g mm3 away" % FILLET_LOSS,
        FILLET_LOSS[0] < loss < FILLET_LOSS[1],
        "loss %.6f" % loss,
    )
    cyl = json_of(a.call("query_geometry", {"select": {"type": "cylinder", "radius": 2}}))
    a.check("4 round fillet faces of r 2", cyl and cyl["count"] == 4, cyl and cyl["count"])
    a.call("undo")
    a.volume_is("undo takes the fillet back", before_fillet)
    a.call("redo")
    a.volume_is("redo puts it again", filleted, 1e-9)
    # 6. a timeline edit: the plate 12 mm thick
    a.call("edit_step", {"step": a.ids["extrude"], "set": {"distance": 12}})
    body, data = a.body()
    a.check(
        "the edited plate is 12 mm thick",
        (body.get("bbox_mm") or {}).get("size") == [60.0, 40.0, 12.0],
        body.get("bbox_mm"),
    )
    expected = 60 * 40 * 12 - 3 * math.pi * 9 * 12 - loss  # the holes go through all
    got = body.get("volume_mm3") or 0
    a.check(
        "its volume follows (holes through 12 mm, same fillet)",
        abs(got - expected) < 0.5,
        "expected about %.3f, got %s" % (expected, got),
    )
    failed = [s["id"] for s in (data or {}).get("timeline", []) if s.get("status") == "error"]
    a.check("no step failed after the edit", not failed, failed)
    holes = json_of(a.call("query_geometry", {"select": {"type": "cylinder", "radius": 3}}))
    tops = sorted({e["bbox_mm"][5] for e in (holes or {}).get("elements", [])})
    a.check("the holes still go through: up to z = 12", tops == [12.0], tops)
    top = json_of(a.call("query_geometry", {"select": {"normal": [0, 0, 1], "count": 1}}))
    centre = top and top["elements"][0]["center_mm"][2]
    a.check("the top face is at z = 12", centre == 12.0, centre)
    timeline = json_of(a.call("get_timeline"))
    names = [s["id"] for s in (timeline or {}).get("steps", [])]
    a.check(
        "the timeline has every step in order",
        [n for n in names if n in a.ids.values()]
        == [a.ids[k] for k in ("sketch", "extrude", "hole_sketch", "hole", "pattern", "fillet")],
        names,
    )
    # 6b. a ref from query_geometry drives a change: the plate's front bottom edge
    edge = json_of(
        a.call(
            "query_geometry",
            {
                "element": "edges",
                "select": {
                    "type": "line",
                    "parallel": [1, 0, 0],
                    "at": [{"axis": "y", "value": "min"}, {"axis": "z", "value": "min"}],
                },
            },
        )
    )
    ref = ((edge or {}).get("elements") or [{}])[0].get("ref")
    a.check("query_geometry gives the edge a ref", ref and ref.get("count") == 1, edge)
    r = a.call("chamfer", {"edges": ref, "distance": 2})
    a.ids["chamfer"] = made_id(r)
    body, _ = a.body()
    chamfered = body.get("volume_mm3") or 0
    a.check(
        "the ref chamfered exactly that edge: 2 x 2 / 2 x 60 = 120 mm3 less",
        abs((got - chamfered) - 120.0) < 1e-6,
        "before %s, after %s" % (got, chamfered),
    )
    got = chamfered
    # 7. a mistake: changes nothing and says why
    r = a.call("fillet", {"edges": TOP4, "radius": 50}, expect_error=True)
    a.check(
        "the mistake is told in a sentence: those edges are smooth now",
        "Not done" in text_of(r) and "smooth" in text_of(r),
        text_of(r),
    )
    a.volume_is("the failed fillet changed nothing", got, 1e-9)
    # 8. check everything, with numbers and a picture
    check = json_of(a.call("check_design"))
    a.check("check_design: ok", check and check["ok"], check and check["problems"])
    diff = json_of(a.call("diff_design", {"since": snapshot}))
    added = [s["id"] for s in (diff or {}).get("steps", {}).get("added", [])]
    a.check(
        "diff_design since the first snapshot: hole, pattern, fillet added",
        all(a.ids[k] in added for k in ("hole", "pattern", "fillet")),
        added,
    )
    changed = [s["id"] for s in (diff or {}).get("steps", {}).get("changed", [])]
    a.check("... and the extrude changed", a.ids["extrude"] in changed, diff and diff["steps"])
    pictures = {}
    for args in (
        {},
        {
            "view": "top",
            "width": 400,
            "height": 300,
            "renderer": "software",
            "highlight": {"faces": {"type": "cylinder", "radius": 3}},
        },
        {  # the default renderer (the window's when SciForge is open): holes seen from above
            "view": "iso",
            "width": 400,
            "height": 300,
            "highlight": {"faces": {"normal": [0, 0, 1], "count": 1}},
        },
    ):
        r = a.call("render", args)
        images = [c for c in r.get("content", []) if c["type"] == "image"]
        size = None
        if images and images[0].get("mimeType") == "image/png":
            data = base64.b64decode(images[0]["data"])
            size = png_size(data)
            pictures[len(pictures)] = data
            if out_dir:
                name = "agent-render-%s%s.png" % (
                    args.get("view") or "iso",
                    "-highlight" if args.get("highlight") else "",
                )
                with open(os.path.join(out_dir, name), "wb") as handle:
                    handle.write(data)
        want = (args.get("width", 800), args.get("height", 600))
        a.check(
            "render %s returns a %d x %d PNG" % (args or "iso", want[0], want[1]),
            size == want,
            size,
        )
        rows = png_rgb(data) if size == want else None
        count = orange_pixels(rows) if rows else None
        if not args.get("highlight"):
            a.check("a plain render has no orange", count == 0, count)
        elif args.get("view") == "iso":  # the top face, seen from above, is a big orange area
            a.check(
                "the highlighted top face is orange in the picture (%s)" % text_of(r)[:60],
                count is not None and count > 0.1 * want[0] * want[1] and "in orange" in text_of(r),
                "%s orange pixels: %s" % (count, text_of(r)[:200]),
            )
    if out_dir:
        path = os.path.join(out_dir, "agent-plate.FCStd")
        if os.path.exists(path):
            os.remove(path)
        a.call("save_as", {"path": path})
        a.ids["file"] = path
    if a.read is not None:
        result = a.read("sciforge://design")
        contents = (result or {}).get("contents") or [{}]
        try:
            design = json.loads(contents[0].get("text", ""))
        except ValueError:
            design = None
        bodies = [b for b in (design or {}).get("bodies", []) if b.get("solid")]
        a.check(
            "the resource sciforge://design has the same volume",
            bodies and abs(bodies[0]["volume_mm3"] - got) < 1e-6,
            contents[0].get("text", "")[:300],
        )
    return a.results


def command_line(agent, path, out_dir):
    """The saved part checked and drawn from the command line (sciforge-cli check / render)."""
    cli = os.path.join(REPO, "tools", "sciforge", "sciforge-cli")
    done = subprocess.run([cli, "check", path], capture_output=True, timeout=TIMEOUT)
    out = done.stdout.decode("utf-8", "replace")
    agent.check(
        "sciforge-cli check: the saved part is OK",
        done.returncode == 0 and "Design check: OK" in out,
        out[:300] + done.stderr.decode()[-300:],
    )
    png = os.path.join(out_dir, "agent-cli-top.png")
    if os.path.exists(png):
        os.remove(png)
    done = subprocess.run(
        [cli, "render", path, png, "--view", "top", "--size", "300x200"],
        capture_output=True,
        timeout=TIMEOUT,
    )
    size = None
    if os.path.isfile(png):
        with open(png, "rb") as handle:
            size = png_size(handle.read(32))
    agent.check(
        "sciforge-cli render writes a 300 x 200 PNG",
        done.returncode == 0 and size == (300, 200),
        (size, done.stderr.decode()[-300:]),
    )


# -- the headless run ----------------------------------------------------------------------------
def default_command():
    return [os.path.join(REPO, "tools", "sciforge", "sciforge-cli"), "mcp", "--headless"]


def run_over_mcp(command, out_dir=None):
    client = Mcp(command)
    results = []
    agent = None
    try:
        init = client.request(
            "initialize",
            {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "sciforge-agent-test", "version": "1"},
            },
        )
        caps = init.get("result", {}).get("capabilities", {})
        client.notify("notifications/initialized")
        tools = client.request("tools/list")["result"]["tools"]
        names = {t["name"] for t in tools}

        def call(tool, args):
            answer = client.request("tools/call", {"name": tool, "arguments": args})
            if "error" in answer:
                return {
                    "content": [{"type": "text", "text": answer["error"]["message"]}],
                    "isError": True,
                }
            return answer["result"]

        def read(uri):
            return client.request("resources/read", {"uri": uri}).get("result")

        agent = Agent(call, read)
        agent.check(
            "initialize offers tools, resources and prompts",
            {"tools", "resources", "prompts"} <= set(caps),
            caps,
        )
        agent.check(
            "tools/list has the checking tools",
            {"inspect_design", "query_geometry", "check_design", "render", "diff_design"} <= names,
            sorted(names)[:10],
        )
        prompt = client.request(
            "prompts/get", {"name": "model_part", "arguments": {"description": "a plate"}}
        )
        agent.check("prompts/get model_part", "result" in prompt, prompt)
        listed = client.request("resources/list")["result"]["resources"]
        agent.check(
            "resources/list has the design",
            any(r["uri"] == "sciforge://design" for r in listed),
            listed[:3],
        )
        docs = read("sciforge://docs/tools.md")
        agent.check(
            "the tool reference is a resource",
            docs and "inspect_design" in docs["contents"][0]["text"],
            str(docs)[:200],
        )
        script(agent, out_dir)
        if agent.ids.get("file"):
            client.close()
            command_line(agent, agent.ids["file"], out_dir)
        results = agent.results
    except Exception as exc:
        results = (agent.results if agent else []) + [
            {
                "check": "the run",
                "ok": False,
                "detail": "%s; server said: %s" % (exc, " | ".join(client.stderr[-10:])),
            }
        ]
    finally:
        client.close()
    return results


def write_report(results, out_dir, name="agent-e2e"):
    report = {"passed": bool(results) and all(r["ok"] for r in results), "results": results}
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, name + "-report.json"), "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
        with open(os.path.join(out_dir, name + "-report.md"), "w", encoding="utf-8") as handle:
            handle.write("# AI agent end-to-end test\n\n| Check | Result |\n|---|---|\n")
            for r in results:
                handle.write(
                    "| %s | %s |\n"
                    % (r["check"], "pass" if r["ok"] else "FAIL: " + r["detail"].replace("|", "/"))
                )
    return report


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    command = None
    if "--" in argv:
        command = argv[argv.index("--") + 1 :]
        argv = argv[: argv.index("--")]
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", default=None)
    options = parser.parse_args(argv)
    results = run_over_mcp(command or default_command(), options.out)
    report = write_report(results, options.out)
    for r in results:
        print(
            "[SciForge] agent %s %s %s"
            % ("PASS" if r["ok"] else "FAIL", r["check"], "" if r["ok"] else r["detail"])
        )
    print(
        "[SciForge] agent summary: %d checks, %d failed"
        % (len(results), len([r for r in results if not r["ok"]]))
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
