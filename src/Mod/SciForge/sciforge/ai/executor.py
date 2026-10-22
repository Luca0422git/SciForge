# SPDX-License-Identifier: LGPL-2.1-or-later
"""Runs AI tool calls in SciForge (needs FreeCAD; Qt only through the host).

One place does the work for every way an AI reaches SciForge: the AI bridge inside the
running app (sciforge/ai/bridge.py), the built-in chat panel (through the bridge) and the
headless backend under FreeCAD's command-line mode (sciforge/ai/headless.py: the MCP server's
--headless mode and sciforge-cli). What differs between them is the host: it answers
questions to the person (overwrite a file?), saves the SciForge way (version history in the
app, a plain save headless), knows the active body (the 3D view's, or remembered here) and
takes screenshots (only with a window).

A call is checked against the catalogue (sciforge/ai/catalog: its schema, its rules, then
whether it can run now: availability), then either built as design steps with the ops layer
(sciforge/ai/ops: the same code as the golden models and the dialogs) or done by an action
(sciforge/ai/actions). Every call that changes the design is one Undo step ("AI: Extrude 10
mm"); a failure takes the half-made change back. Answers are bridge_core results: plain
sentences, JSON for the read-only tools, a PNG for screenshots. Never raises.
"""

import json
import math

import FreeCAD as App

from .. import log, warn
from . import bridge_core, catalog

DEFAULT_IDS = {
    "create_sketch": "Sketch",
    "create_curve_sketch": "Sketch",
    "extrude": "Extrude",
    "revolve": "Revolve",
    "fillet": "Fillet",
    "chamfer": "Chamfer",
    "hole": "Hole",
    "pattern": "Pattern",
    "shell": "Shell",
    "set_parameter": "Parameter",
}


MODIFIED = set()  # designs changed since they were last saved (headless; the window knows)


class UserError(Exception):
    """Something the AI has to change; the message is a plain sentence."""


# -- hosts ------------------------------------------------------------------------------------
class Host:
    """Where the executor runs. The headless host is this class (headless.py adds the
    command-line conveniences); the bridge's GUI host overrides what needs the window."""

    gui = False
    allow_overwrite = False

    def __init__(self):
        self._active = {}  # document name -> body name (the window keeps it otherwise)

    # bodies
    def find_body(self, doc):
        from .. import bodies

        name = self._active.get(doc.Name)
        body = doc.getObject(name) if name else None
        if body is not None and bodies.alive(body):
            return body
        return bodies.find_body(doc)

    def ensure_body(self, doc):
        from .. import bodies

        body = self.find_body(doc)
        if body is None:
            body = bodies.new_body(doc)
        self.set_active_body(body)
        return body

    def set_active_body(self, body):
        from .. import bodies

        if body is not None:
            self._active[body.Document.Name] = body.Name
            bodies.set_active_body(body)

    # files
    def confirm_overwrite(self, path):
        return bool(self.allow_overwrite)

    def refuse_overwrite_text(self, path):
        return (
            "%s already exists. Headless SciForge never replaces files unless it was started "
            "with --allow-overwrite; pick another path." % path
        )

    def save(self, doc, path=None):
        """Save (path None: where it is). Returns the path saved."""
        if path:
            doc.saveAs(path)
        else:
            doc.save()
        return doc.FileName

    def open_design(self, path):
        import os

        for doc in App.listDocuments().values():
            if doc.FileName and os.path.normcase(os.path.abspath(doc.FileName)) == (
                os.path.normcase(os.path.abspath(path))
            ):
                App.setActiveDocument(doc.Name)
                return doc
        doc = App.openDocument(path)
        App.setActiveDocument(doc.Name)
        return doc

    def new_document(self, name):
        doc = App.newDocument(_doc_name(name))
        doc.Label = name
        App.setActiveDocument(doc.Name)
        return doc

    def show_document(self, doc):
        """Make the design the active one (the window also brings its tab to the front)."""
        App.setActiveDocument(doc.Name)

    def ready(self, doc):
        """A document made or opened here: undo works (command-line FreeCAD has it off)."""
        try:
            if not doc.UndoMode:
                doc.UndoMode = 1
        except Exception:
            pass

    def busy(self):
        return ""

    def ask(self, title, text):
        return False

    # the window
    def view(self, doc):
        return None

    def selection(self, doc):
        """What the person has selected in the design: [{object, label, elements}] (none
        without the window)."""
        return []

    def push_highlight(self, doc, marked):
        """Show marked faces / edges (render's highlight) in the window; returns what to
        put back with pop_highlight. Nothing to do without the window."""
        return None

    def pop_highlight(self, doc, saved):
        pass

    def screenshot(self, doc, width, height):
        raise UserError(catalog.NEEDS["gui"])

    def after_change(self, doc):
        """After a change: the design has unsaved changes (the window also refreshes its
        panels: the GUI host)."""
        if doc is not None:
            MODIFIED.add(doc.Name)


def _doc_name(label):
    import re

    name = re.sub(r"[^A-Za-z0-9_]", "_", label or "") or "Design"
    if name[0].isdigit():
        name = "D_" + name
    return name


# -- the state tools need ---------------------------------------------------------------------
def state(host):
    doc = App.ActiveDocument
    out = {"gui": bool(host.gui), "design": doc is not None, "solid": False, "drawing": False}
    if doc is None:
        return out
    try:
        from .. import bodies

        out["solid"] = bool(bodies.solid_bodies(doc))
    except Exception:
        out["solid"] = any(
            o.TypeId == "PartDesign::Body" and not o.Shape.isNull() and o.Shape.Solids
            for o in doc.Objects
        )
    out["drawing"] = any(o.TypeId == "TechDraw::DrawPage" for o in doc.Objects)
    return out


# -- one call -------------------------------------------------------------------------------
def run(tool, args, host):
    """One tool call -> a bridge_core result. Never raises."""
    if args is None:
        args = {}
    try:
        problems = catalog.validate(tool, args)
        if problems:
            return bridge_core.error_result("Not done: " + "; ".join(problems) + ".")
        entry = catalog.tool(tool)
        ok, why = catalog.availability(tool, state(host))
        if not ok:
            return bridge_core.error_result(why)
        ctx = Context(host, tool, args)
        from . import actions
        from .actions import verify_actions

        doc = App.ActiveDocument
        before = verify_actions.before_change(doc) if entry["changes_design"] else None
        if entry["kind"] == "steps":
            answer = ctx.build()
        else:
            handler = actions.ACTIONS.get(tool)
            if handler is None:
                return bridge_core.error_result("SciForge cannot do %s yet." % tool)
            answer = handler(ctx, args)
        if before is not None and not answer.get("is_error"):
            verify_actions.after_change(before["doc"], before)  # (diff_design last_change)
        return answer
    except UserError as exc:
        return bridge_core.error_result(str(exc))
    except Exception as exc:  # never let a tool call end SciForge
        warn("AI tool %s: %s" % (tool, exc))
        return bridge_core.error_result("Not done (%s): %s" % (tool, _plain(exc)))


def _plain(exc):
    text = str(exc).strip() or exc.__class__.__name__
    for prefix in ("Exception: ", "<Exception> "):
        if text.startswith(prefix):
            text = text[len(prefix) :]
    return text


class Context:
    """What one call works with: the host, the design, the step builder."""

    def __init__(self, host, tool, args):
        self.host = host
        self.tool = tool
        self.args = args
        self.entry = catalog.tool(tool)
        self.title = catalog.step_title(tool, args)

    # -- the design -------------------------------------------------------------------------
    @property
    def doc(self):
        return App.ActiveDocument

    def need_doc(self, create=False):
        doc = App.ActiveDocument
        if doc is None and create:
            doc = self.host.new_document("Untitled")
            self.host.ready(doc)
            self.host.ensure_body(doc)
            log("AI: new design %s" % doc.Name)
        if doc is None:
            raise UserError(catalog.NEEDS["design"])
        self.host.ready(doc)
        return doc

    def builder(self, doc=None):
        from .ops import core

        doc = doc or self.need_doc()
        body = self.host.find_body(doc) or self.host.ensure_body(doc)
        builder = _BUILDERS.get(doc.Name)
        if builder is None or builder.doc is not doc or not _alive(builder.body):
            builder = _BUILDERS[doc.Name] = core.Builder.attach(doc, body)
        else:
            builder.learn()
            builder.body = body
        for key in [k for k, obj in builder.objects.items() if not _alive(obj)]:
            builder.objects.pop(key, None)
            builder.ops.pop(key, None)
        for key, obj in builder.objects.items():  # every sketch is a sketch step (a sketch of
            if obj.TypeId == "Sketcher::SketchObject":  # open curves too: paths, rails)
                builder.ops[key] = "sketch"
        builder.measure_bodies = None
        builder.measure_components = None
        return builder

    def resolve(self, ident, what="step, body or component"):
        """The object an id names: its Name, its Label, or the timeline's name for it."""
        doc = self.need_doc()
        return resolve(doc, ident, what)

    def body_of(self, ident):
        from .. import bodies

        obj = self.resolve(ident, "body or step")
        body = obj if bodies.is_body(obj) else bodies.body_of(obj)
        if body is None:
            raise UserError("%r is not in a body." % ident)
        return body

    def new_id(self, base):
        doc = self.need_doc()
        taken = {o.Name for o in doc.Objects} | {o.Label for o in doc.Objects}
        builder = _BUILDERS.get(doc.Name)
        if builder is not None:
            taken |= set(builder.objects)
        n = 1
        while "%s%d" % (base, n) in taken:
            n += 1
        return "%s%d" % (base, n)

    # -- changing -----------------------------------------------------------------------------
    def change(self, fn, title=None):
        """Run fn() as one Undo step; a failure takes it back. Returns fn's value."""
        doc = self.need_doc()
        title = title or self.title
        doc.openTransaction(title)
        try:
            value = fn()
            doc.commitTransaction()
        except BaseException:
            doc.abortTransaction()
            try:
                doc.recompute()
            except Exception:
                pass
            raise
        try:
            doc.recompute()
        except Exception:
            pass
        self.host.after_change(doc)
        log(title)
        return value

    def build(self):
        """A tool that is design steps: built with sciforge/ai/ops in one Undo step."""
        from .ops.core import BuildError

        doc = self.need_doc(create="design" not in self.entry["needs"])
        builder = self.builder(doc)
        step_id = self.new_id(self.entry["id_base"] or DEFAULT_IDS.get(self.tool, "Step"))
        steps = catalog.to_steps(self.tool, self.args, step_id)
        steps = [_at_marker(doc, s) for s in steps]
        before = _broken(doc)
        doc.openTransaction(self.title)
        try:
            for step in steps:
                builder.run(step)
            doc.commitTransaction()
        except Exception as exc:
            doc.abortTransaction()
            try:
                doc.recompute()
            except Exception:
                pass
            builder.objects.pop(step_id, None)
            text = _plain(exc)
            if isinstance(exc, KeyError):  # an id the design does not have
                text = (
                    "there is no step, sketch or body called %s here (get_design and "
                    "get_timeline list the ids)" % text
                )
            elif not isinstance(exc, (BuildError, UserError)):
                warn("AI %s: %s" % (self.tool, text))
            return bridge_core.error_result("Not done (%s): %s" % (self.title, _clean(text)))
        doc.recompute()
        if builder.body is not None and _alive(builder.body):
            self.host.set_active_body(builder.body)
        self.host.after_change(doc)
        made = builder.objects.get(step_id) if self.entry["own_id"] else None
        named = ""
        if made is not None and _alive(made):
            named = " Its id is %r." % made.Name
            if made.Label not in (made.Name, step_id):
                named = " Its id is %r (shown as %r)." % (made.Name, made.Label)
        log(self.title)
        return bridge_core.result(
            "Done: %s.%s %s%s" % (self.title, named, summary(doc), broke_text(doc, before))
        )

    def done(self, text, doc=None, before=None):
        doc = doc or self.doc
        tail = ""
        if doc is not None:
            tail = " " + summary(doc) + (broke_text(doc, before) if before is not None else "")
        return bridge_core.result(text.rstrip() + tail)


_BUILDERS = {}


def forget(doc_name, closed=False):
    """Drop the step builder kept for a design (its steps changed under it); closed: the
    design was closed, so its snapshots for diff_design go too."""
    _BUILDERS.pop(doc_name, None)
    if not closed:
        return
    try:
        from .actions import verify_actions

        verify_actions.forget(doc_name)
    except Exception:
        pass


def _alive(obj):
    try:
        return obj is not None and obj.isAttachedToDocument()
    except Exception:
        return False


def _clean(text):
    """A BuildError's text without the step-language prefix ("extrude 'Extrude1': ")."""
    import re

    return re.sub(r"^[a-z_0-9]+ '[^']*': ", "", text)


def _at_marker(doc, step):
    """A Fillet / Chamfer made while the history marker is rolled back goes in at the
    marker and keeps the later blends' edges (blend_insert, as the dialog does)."""
    if step.get("op") not in ("blend_fillet", "blend_chamfer"):
        return step
    try:
        from .. import timeline_ops

        if timeline_ops.timeline(doc).at_end:
            return step
    except Exception:
        return step
    out = dict(
        step, op="blend_insert", kind="fillet" if step["op"] == "blend_fillet" else "chamfer"
    )
    if "features" in out:
        raise UserError(
            "With the history marker rolled back, pick the edges with edges / faces (features "
            "only works at the end of the timeline)."
        )
    return out


def resolve(doc, ident, what="step, body or component"):
    if not isinstance(ident, str) or not ident:
        raise UserError("Give the id of a %s." % what)
    obj = doc.getObject(ident)
    if obj is not None:
        return obj
    found = [o for o in doc.Objects if o.Label == ident]
    if len(found) == 1:
        return found[0]
    try:
        from .. import timeline_ops

        for item in timeline_ops.timeline(doc).items:
            if item.display == ident or item.title == ident:
                return doc.getObject(item.name)
    except Exception:
        pass
    if len(found) > 1:
        raise UserError("Several things are called %r: use the id get_design lists." % ident)
    raise UserError("There is no %s called %r (get_design lists them)." % (what, ident))


# -- what a change answers ------------------------------------------------------------------
def summary(doc):
    from .. import bodies

    parts = []
    try:
        found = bodies.solid_bodies(doc)
    except Exception:
        found = []
    for body in found:
        shape = body.Shape
        box = shape.BoundBox
        parts.append(
            "%s: %.6g mm3, %.4g x %.4g x %.4g mm"
            % (body.Label, shape.Volume, box.XLength, box.YLength, box.ZLength)
        )
    return ("Bodies now: " + "; ".join(parts) + ".") if parts else "No solid body yet."


def _broken(doc):
    try:
        from .. import timeline_ops

        return {i.name: i.message for i in timeline_ops.timeline(doc).items if i.status == "error"}
    except Exception:
        return {}


def broke_text(doc, before):
    """ " These steps now fail: ..." for steps that broke with this change."""
    now = _broken(doc)
    new = {k: v for k, v in now.items() if k not in (before or {})}
    if not new:
        return ""
    names = []
    for name, why in new.items():
        obj = doc.getObject(name)
        names.append("%s (%s)" % (obj.Label if obj is not None else name, why))
    return " These steps now fail: %s." % "; ".join(names)


# -- JSON helpers -----------------------------------------------------------------------------
def jsonable(value, depth=0):
    """FreeCAD values as JSON: objects by Name, (object, sub) pairs, quantities as numbers,
    vectors as [x, y, z], placements as {base, rotation}."""
    if depth > 8:
        return str(value)
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return round(value, 9) if math.isfinite(value) else str(value)
    if hasattr(value, "Value") and hasattr(value, "Unit"):
        return round(float(value.Value), 9)
    if hasattr(value, "TypeId") and hasattr(value, "Name"):
        try:
            return value.Name
        except Exception:
            return "<deleted>"
    if hasattr(value, "x") and hasattr(value, "y") and hasattr(value, "z"):
        return [round(float(value.x), 9), round(float(value.y), 9), round(float(value.z), 9)]
    if hasattr(value, "Base") and hasattr(value, "Rotation"):
        return {
            "base": jsonable(value.Base),
            "axis": jsonable(value.Rotation.Axis),
            "angle": round(math.degrees(value.Rotation.Angle), 9),
        }
    if isinstance(value, dict):
        return {str(k): jsonable(v, depth + 1) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        items = list(value)
        if (
            len(items) == 2
            and hasattr(items[0], "TypeId")
            and isinstance(items[1], (str, list, tuple))
        ):
            subs = items[1] if isinstance(items[1], (list, tuple)) else [items[1]]
            subs = [s for s in subs if s]
            name = jsonable(items[0])
            return name if not subs else ["%s.%s" % (name, s) for s in subs]
        return [jsonable(v, depth + 1) for v in items]
    return str(value)


def json_result(data, text=None, compact=False):
    """A result whose text is the data as JSON (after a sentence when text is given).
    compact: short lists and objects stay on one line (a bounding box, a selector), so a
    long answer costs the AI far fewer tokens and stays easy to read."""
    if compact:
        body = bridge_core.compact_json(data)
    else:
        body = json.dumps(data, indent=1, ensure_ascii=False, default=str)
    return bridge_core.result(body if text is None else text + "\n" + body)


