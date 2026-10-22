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
from . import bridge_core, catalog, geometry_facts, value_fit

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
    overwrite_option = "--allow-overwrite"  # how this host was told it may replace files
    relative_base = None  # the folder relative paths are read from (the command line's)

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
        """May the file (or the list of files: asked once) be replaced?"""
        return bool(self.allow_overwrite)

    def refuse_overwrite_text(self, path):
        if isinstance(path, (list, tuple)):
            what = "%s already exist" % ", ".join(path)
        else:
            what = "%s already exists" % path
        if self.overwrite_option != Host.overwrite_option:  # (sciforge-cli: --force)
            return "%s: add %s to the command to replace it, or pick another path." % (
                what,
                self.overwrite_option,
            )
        return (
            "%s. Headless SciForge never replaces files unless it was started with %s; pick "
            "another path." % (what, self.overwrite_option)
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
        """Put back what push_highlight changed; False when the marked faces / edges could
        not be drawn."""
        return None

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
        from .. import timeline_ops
        from .actions import verify_actions

        doc = App.ActiveDocument
        before = verify_actions.before_change(doc) if entry["changes_design"] else None
        handler = None
        if entry["kind"] != "steps":
            handler = actions.ACTIONS.get(tool)
            if handler is None:
                return bridge_core.error_result("SciForge cannot do %s yet." % tool)
        # the undo steps SciForge's timeline and history operations open are named after
        # the call too ("AI: Suppress", not "Suppress Fillet 1"): Undo last AI step finds them
        failed = True
        try:
            with timeline_ops.undo_title(ctx.title):
                answer = ctx.build() if handler is None else handler(ctx, args)
            failed = bool(answer.get("is_error"))
        finally:
            if entry["changes_design"]:
                _close_left_transaction(ctx.title, failed)
        if before is not None and not answer.get("is_error"):
            verify_actions.after_change(before["doc"], before)  # (diff_design last_change)
        return answer
    except UserError as exc:
        return bridge_core.error_result(str(exc))
    except Exception as exc:  # never let a tool call end SciForge
        warn("AI tool %s: %s" % (tool, exc))
        return bridge_core.error_result("Not done (%s): %s" % (tool, _plain(exc)))


def _close_left_transaction(title, failed):
    """FreeCAD keeps a transaction open after commitTransaction / abortTransaction when
    nothing was recorded in it yet (a Visibility change is not recorded, for one): the next
    change, made outside a transaction (a failed edit's search for the largest value that
    fits, the person's next click), would land in that step. Close ours (`title`): taken
    back when the call failed (a failed call changes nothing), kept otherwise. A transaction
    someone else opened (a dialog in the window) is left alone."""
    try:
        active = App.getActiveTransaction()
        if active and active[0] == title:
            App.closeActiveTransaction(bool(failed))
    except Exception as exc:
        warn("AI: closing an undo step left open: %s" % exc)


def _plain(exc):
    text = str(exc).strip() or exc.__class__.__name__
    for prefix in ("Exception: ", "<Exception> "):
        if text.startswith(prefix):
            text = text[len(prefix) :]
    return text


class Context:
    """What one call works with: the host, the design, the step builder."""

    _missing = None  # the id the last steps did not find (a KeyError's)

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

    def full_path(self, path):
        """A file path the AI gave: ~ is the home folder. A relative path is refused (the
        AI cannot know which folder SciForge runs in, so the file would land somewhere
        unexpected), except on the command line, where it is read from the folder the
        command was typed in (the host's relative_base)."""
        import os

        if not isinstance(path, str) or not path.strip():
            raise UserError("Give a full path for the file.")
        path = os.path.expanduser(path.strip())
        if not os.path.isabs(path):
            if not self.host.relative_base:
                raise UserError(
                    "%r is not a full path: give the whole path, like %s (SciForge does not "
                    "guess the folder)." % (path, os.path.join(os.path.expanduser("~"), path))
                )
            path = os.path.join(self.host.relative_base, path)
        return os.path.abspath(path)

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
            _close_left_transaction(title, False)
        except BaseException:
            doc.abortTransaction()
            _close_left_transaction(title, True)  # (else the recompute below lands in it)
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
        doc = self.need_doc(create="design" not in self.entry["needs"])
        builder = self.builder(doc)
        step_id = self.new_id(self.entry["id_base"] or DEFAULT_IDS.get(self.tool, "Step"))
        steps = catalog.to_steps(self.tool, self.args, step_id)
        steps = [_at_marker(doc, s) for s in steps]
        before = _broken(doc)
        shapes_before = shape_signature(doc) if self.tool not in KEEPS_SHAPES else None
        limited = bool(value_fit.candidates(self.tool, self.args))
        failed = self._run_steps(doc, builder, steps, step_id, before, shapes_before, limited)
        for _attempt in range(8):  # a step named as get_timeline shows it ("Sketch 1")
            args = _ids_for_names(doc, self.args, self._missing) if failed else None
            if args is None:
                break
            self.args = args
            steps = [_at_marker(doc, s) for s in catalog.to_steps(self.tool, args, step_id)]
            failed = self._run_steps(doc, builder, steps, step_id, before, shapes_before, limited)
        if failed is not None:
            text, no_change = failed
            if limited and (no_change or value_fit.is_limit(text)):
                extra = self._largest(doc, builder, step_id, before, shapes_before)
                if extra:
                    text = text.rstrip()
                    if not text.endswith("."):
                        text += "."
                    return bridge_core.error_result(
                        "Not done (%s): %s%s" % (self.title, text, extra)
                    )
            if not no_change:
                return bridge_core.error_result("Not done (%s): %s" % (self.title, text))
            # changed nothing and no smaller value helps: built as asked, with the warning
            # below (as before value_fit)
            steps = [_at_marker(doc, s) for s in catalog.to_steps(self.tool, self.args, step_id)]
            failed = self._run_steps(doc, builder, steps, step_id, before, shapes_before, False)
            if failed is not None:
                return bridge_core.error_result("Not done (%s): %s" % (self.title, failed[0]))
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
        broke = broke_text(doc, before)
        unchanged = ""
        if (
            shapes_before is not None
            and not broke
            and _marker_at_end(doc)
            and shape_signature(doc) == shapes_before
        ):
            unchanged = NOTHING_CHANGED
            log("%s changed no solid" % self.title)
        return bridge_core.result(
            "Done: %s.%s %s%s%s" % (self.title, named, summary(doc), broke, unchanged)
        )

    def _run_steps(self, doc, builder, steps, step_id, before, shapes_before, limited):
        """Build the steps as one Undo step. None when done; else (the reason in words,
        True when the steps built but changed no solid: only checked when `limited`, a
        call with a size value that may not fit). A failure takes everything back."""
        from .ops.core import BuildError

        self._missing = None
        doc.openTransaction(self.title)
        try:
            for step in steps:
                builder.run(step)
            if limited and self._changed_nothing(doc, before, shapes_before):
                raise _NoChange(self.title)  # (a shell thicker than the part)
            doc.commitTransaction()
            _close_left_transaction(self.title, False)
            return None
        except Exception as exc:
            doc.abortTransaction()
            _close_left_transaction(self.title, True)
            try:
                doc.recompute()
            except Exception:
                pass
            builder.objects.pop(step_id, None)
            text = _plain(exc)
            if isinstance(exc, KeyError):  # an id the design does not have
                self._missing = exc.args[0] if exc.args else None
                text = (
                    "there is no step, sketch or body called %s here (get_design and "
                    "get_timeline list the ids)" % text
                )
            elif not isinstance(exc, (BuildError, UserError, _NoChange)):
                warn("AI %s: %s" % (self.tool, text))
            return _clean(text), isinstance(exc, _NoChange)

    def _changed_nothing(self, doc, before, shapes_before):
        """True when the steps just built left every solid's volume and size as they were
        (no step broke and the history marker is at the end, so the bodies show the
        result). For a call with a size value: a shell as thick as the part gives back a
        solid of the same volume with other faces, which is no shell either."""
        if shapes_before is None or not _marker_at_end(doc):
            return False
        if broke_text(doc, before):
            return False
        return _volumes(shape_signature(doc)) == _volumes(shapes_before)

    def _trial(self, doc, builder, step_id, args, before, shapes_before):
        """Build this call with other arguments in a transaction that is taken back: True
        when it builds, breaks no step and (for a tool that changes solids) changes one."""
        ok = False
        doc.openTransaction("AI: trying a value")
        try:
            steps = catalog.to_steps(self.tool, args, step_id)
            for step in [_at_marker(doc, s) for s in steps]:
                builder.run(step)
            ok = (
                not broke_text(doc, before)
                and not self._changed_nothing(doc, before, shapes_before)
                and _solids_valid(doc, shapes_before)
            )
        except Exception:
            ok = False
        finally:
            doc.abortTransaction()
            _close_left_transaction("AI: trying a value", True)
            builder.objects.pop(step_id, None)
        return ok

    def _largest(self, doc, builder, step_id, before, shapes_before):
        """The sentence giving the largest value that fits (value_fit), or "". The design
        is left exactly as it was."""
        try:
            return value_fit.largest(
                self.tool,
                self.args,
                lambda args: self._trial(doc, builder, step_id, args, before, shapes_before),
            )
        except Exception as exc:
            warn("AI %s: the largest value that fits was not found (%s)" % (self.tool, exc))
            return ""
        finally:
            try:
                doc.recompute()
            except Exception:
                pass

    def done(self, text, doc=None, before=None):
        doc = doc or self.doc
        tail = ""
        if doc is not None:
            tail = " " + summary(doc) + (broke_text(doc, before) if before is not None else "")
        return bridge_core.result(text.rstrip() + tail)


_BUILDERS = {}


def _volumes(signature):
    """{body: (volume, bounding box)} of a shape_signature (None stays None)."""
    if signature is None:
        return None
    return {name: (sig[0], sig[3]) for name, sig in signature.items()}


def _solids_valid(doc, shapes_before):
    """True when every body a trial changed is a valid shape (a trial is stricter than a
    real call, so the largest value it finds always builds)."""
    from .. import bodies

    try:
        found = bodies.solid_bodies(doc)
    except Exception:
        return True
    now = shape_signature(doc) or {}
    for body in found:
        if shapes_before is not None and now.get(body.Name) == shapes_before.get(body.Name):
            continue
        try:
            if not body.Shape.isValid():
                return False
        except Exception:
            return False
    return True


class _NoChange(Exception):
    """A step with a size value built but changed no solid (the size does not fit)."""

    def __init__(self, title):
        Exception.__init__(
            self,
            "%s left every solid's volume as it was: the value does not fit here "
            "(OpenCASCADE gave the part back unchanged)." % title.replace("AI: ", ""),
        )


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


_NOT_IDS = ("label", "name", "text", "title", "comment", "description", "value", "expression")


def _ids_for_names(doc, args, missing):
    """The arguments with `missing` (an id the steps did not find) replaced by the id of the
    step it names: the timeline's name for it ("Sketch 1", what get_timeline shows) or its
    label. None when it names nothing, or is already an id."""
    if not isinstance(missing, str) or not missing or doc.getObject(missing) is not None:
        return None
    try:
        obj = resolve(doc, missing)
    except UserError:
        return None
    if obj is None or obj.Name == missing:
        return None
    found = []

    def swap(value, key=None):
        if isinstance(value, dict):
            return {k: (v if k in _NOT_IDS else swap(v, k)) for k, v in value.items()}
        if isinstance(value, list):
            return [swap(v, key) for v in value]
        if value == missing:
            found.append(key)
            return obj.Name
        return value

    out = swap(args)
    return out if found else None


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
        box = geometry_facts.tight_box(shape)
        parts.append(
            "%s: %.6g mm3, %.4g x %.4g x %.4g mm"
            % (body.Label, shape.Volume, box.XLength, box.YLength, box.ZLength)
        )
    return ("Bodies now: " + "; ".join(parts) + ".") if parts else "No solid body yet."


# Step tools that never change a solid's shape by themselves (sketches, parameters,
# construction geometry, surfaces, components): no "nothing changed" warning for them.
KEEPS_SHAPES = frozenset(
    (
        "create_sketch",
        "create_curve_sketch",
        "sketch_polygon",
        "sketch_trim",
        "set_parameter",
        "capture_design_history",
        "construct_plane",
        "construct_axis",
        "construct_point",
        "surface",
        "thread",  # (a cosmetic thread changes no geometry)
        "components_from_bodies",
        "copy_component",
        "pattern_components",
        "insert_hardware",
    )
)
NOTHING_CHANGED = (
    " Warning: no solid changed (every body has the same volume, area, faces and size as "
    "before), so this step did nothing to the part. Usual causes: it points away from the "
    "part (an extrude goes along its sketch's normal, so a cut from a sketch on the top face "
    "needs flip: true; a hole drills into the part from its sketch, and flip: true makes it "
    "drill along the sketch's normal), a size that cannot fit (a wall thicker than the part), or a pick that missed. "
    "Undo takes it back; diff_design since last_change confirms."
)


def _marker_at_end(doc):
    """True unless the timeline's history marker is rolled back (then a new feature goes in
    at the marker and the bodies show it only once the marker is at the end again)."""
    try:
        from .. import timeline_ops

        return bool(timeline_ops.timeline(doc).at_end)
    except Exception:
        return True


def shape_signature(doc):
    """What a step can change about the solids: per body its volume, area, number of faces
    and bounding box (rounded), and which bodies there are. Equal before and after a step
    means the step changed nothing (a cut that missed, a shell thicker than the part)."""
    from .. import bodies

    out = {}
    try:
        found = bodies.solid_bodies(doc)
    except Exception:
        return None
    for body in found:
        try:
            shape = body.Shape
            box = shape.BoundBox
            out[body.Name] = (
                round(shape.Volume, 6),
                round(shape.Area, 6),
                len(shape.Faces),
                tuple(
                    round(v, 6)
                    for v in (box.XMin, box.YMin, box.ZMin, box.XMax, box.YMax, box.ZMax)
                ),
            )
        except Exception:
            return None
    return out


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
