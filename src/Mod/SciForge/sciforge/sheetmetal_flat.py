# SPDX-License-Identifier: LGPL-2.1-or-later
"""Unfold and Refold steps of a sheet metal body (FreeCAD, no Qt).

Fusion's MODIFY > Unfold lays some or all bends of a sheet metal body flat *in the timeline*
(the stationary face stays put), so holes and slots can be cut across the bends while they
are flat; MODIFY > Refold folds the bends back and carries those cuts onto the folded walls
and bends. The pair is grouped in the timeline ("Unfold" ... "Refold").

    make_unfold(body, base, face, bends=None, unfold_all=False)   -> the Unfold step
    update_unfold(step, face, bends, unfold_all)
    make_refold(body, unfold)                                     -> the Refold step
    open_unfold(body)            the Unfold before the marker that has no Refold yet
    k_factor(body)               the K-factor of the body's sheet metal rule

The geometry is sheetmetal_unfold's.
"""

import FreeCAD as App

from . import bodies, log, sheetmetal, sheetmetal_core, warn
from . import sheetmetal_unfold as unfolder

UNFOLD_TYPE = "Unfold"
REFOLD_TYPE = "Refold"
FP_TYPE = "PartDesign::FeaturePython"


class FlatError(ValueError):
    """A refusal with the reason (shown in the dialog)."""


def k_factor(body):
    """K-factor of the body's rule (the library default for a body that is not sheet metal)."""
    try:
        if body is not None and sheetmetal.is_sheet_metal_body(body):
            return float(sheetmetal.rule_for_body(body)["k_factor"])
    except Exception as exc:
        warn("K-factor of %s: %s" % (getattr(body, "Label", "?"), exc))
    return float(sheetmetal_core.library_rule(sheetmetal_core.DEFAULT_RULE)["k_factor"])


def _links(value):
    out = []
    for linked, subs in value or []:
        if isinstance(subs, str):
            subs = [subs]
        for sub in subs or []:
            if sub:
                out.append((linked, sub.lstrip("?")))
    return out


def _face_of(link):
    """(obj, 'FaceN') of a PropertyLinkSub value, or (None, '')."""
    if not link:
        return None, ""
    obj, subs = link
    if isinstance(subs, str):
        subs = [subs]
    subs = [s for s in subs or [] if s]
    return obj, (subs[0].lstrip("?") if subs else "")


def bend_keys(base_shape, names):
    """bend_key of every cylinder face named (other faces are ignored)."""
    keys = []
    for name in names:
        try:
            face = base_shape.getElement(name)
        except Exception:
            continue
        if unfolder.is_cylinder(face):
            keys.append(unfolder.bend_key(face))
    return keys


def run_unfold(step, check=True):
    """The unfold result of an Unfold step from its BaseFeature (sheetmetal_unfold.Result)."""
    base = step.BaseFeature
    if base is None or base.Shape.isNull() or not base.Shape.Solids:
        raise FlatError("Unfold needs a sheet metal body before it in the timeline.")
    _obj, face = _face_of(step.Stationary)
    if not face:
        raise FlatError("Pick the stationary face: a flat top or bottom face of a wall.")
    if step.UnfoldAll:
        keys = None
    else:
        keys = bend_keys(base.Shape, [s for _o, s in _links(step.Bends)])
        if not keys:
            raise FlatError("Pick the bends to unfold, or tick Unfold All Bends.")
    body = bodies.body_of(step)
    try:
        return unfolder.unfold(base.Shape, face, k_factor(body), bends=keys, check=check)
    except unfolder.UnfoldError as exc:
        raise FlatError(str(exc))


class UnfoldFeature:
    """Fusion's Unfold step. Saved files store "sciforge.sheetmetal_flat.UnfoldFeature"."""

    def __init__(self, obj):
        obj.Proxy = self
        self.ensure_properties(obj)

    @staticmethod
    def ensure_properties(obj):
        def add(kind, name, doc, group="Unfold"):
            if name not in obj.PropertiesList:
                obj.addProperty(kind, name, group, doc)
                return True
            return False

        add("App::PropertyLinkSub", "Stationary", "The face that stays put")
        add("App::PropertyLinkSubList", "Bends", "The bends to unfold")
        add("App::PropertyBool", "UnfoldAll", "Unfold every bend")
        if add("App::PropertyInteger", "BendCount", "Bends unfolded (read only)"):
            obj.setEditorMode("BendCount", 1)
        bodies.mark(obj, UNFOLD_TYPE)

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)

    def execute(self, obj):
        try:
            result = run_unfold(obj)
        except Exception:
            bodies.pass_through(obj)
            raise
        obj.Shape = result.shape
        if obj.BendCount != len(result.bends):
            obj.BendCount = len(result.bends)

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


class RefoldFeature:
    """Fusion's Refold step. Saved files store "sciforge.sheetmetal_flat.RefoldFeature"."""

    def __init__(self, obj):
        obj.Proxy = self
        self.ensure_properties(obj)

    @staticmethod
    def ensure_properties(obj):
        if "Unfold" not in obj.PropertiesList:
            obj.addProperty("App::PropertyLink", "Unfold", "Refold", "The Unfold it closes")
        bodies.mark(obj, REFOLD_TYPE)

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)

    def execute(self, obj):
        try:
            obj.Shape = refold_shape(obj)
        except Exception:
            bodies.pass_through(obj)
            raise

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def refold_shape(step):
    unfold = step.Unfold
    if unfold is None or not bodies.alive(unfold):
        raise FlatError("This Refold has lost its Unfold.")
    base = step.BaseFeature
    if base is None or base.Shape.isNull() or not base.Shape.Solids:
        raise FlatError("Refold needs the unfolded body before it.")
    result = run_unfold(unfold, check=False)
    folded = unfold.BaseFeature.Shape
    flat_after = base.Shape
    if len(flat_after.Solids) != 1:
        raise FlatError("The unfolded body fell apart into %d pieces" % len(flat_after.Solids))
    try:
        out = unfolder.refold(folded, result, flat_after.Solids[0])
    except unfolder.UnfoldError as exc:
        raise FlatError(str(exc))
    solids = out.Solids
    if not solids:
        raise FlatError("Nothing is left after the Refold.")
    return solids[0] if len(solids) == 1 else out


def _view_provider(obj, kind):
    if not App.GuiUp:
        return
    try:
        from .unfold_ui import ViewProviderFlatStep

        ViewProviderFlatStep(obj.ViewObject, kind)
    except Exception as exc:
        warn("Unfold view: %s" % exc)


def _check_body(body):
    if body is None:
        raise FlatError("There is no body to unfold.")
    if not sheetmetal.is_sheet_metal_body(body):
        raise FlatError(
            "%s is not sheet metal: use Convert to Sheet Metal first (MODIFY menu)" % body.Label
        )


def make_unfold(body, base, face, bends=None, unfold_all=False, name="Unfold"):
    """A new Unfold at the marker. face: 'FaceN' of base. bends: 'FaceN' names of bend faces
    (inner or outer). Recomputes; raises FlatError (and removes the step) when it fails."""
    _check_body(body)
    if open_unfold(body) is not None:
        raise FlatError("This body is already unfolded: Refold it first.")
    step = bodies.insert_after_tip(body, FP_TYPE, name)
    UnfoldFeature(step)
    step.BaseFeature = base
    _view_provider(step, "unfold")
    update_unfold(step, base, face, bends, unfold_all)
    return step


def update_unfold(step, base, face, bends=None, unfold_all=False):
    step.Stationary = (base, [face]) if face else None
    step.Bends = [(base, list(bends))] if bends else []
    step.UnfoldAll = bool(unfold_all)
    step.touch()


def make_refold(body, unfold=None, name="Refold"):
    """A Refold at the marker that closes unfold (default: the open one). Groups the pair."""
    unfold = unfold or open_unfold(body)
    if unfold is None:
        raise FlatError("There is nothing to refold: Unfold first.")
    step = bodies.insert_after_tip(body, FP_TYPE, name)
    RefoldFeature(step)
    step.Unfold = unfold
    _view_provider(step, "refold")
    _group(body.Document, unfold, step)
    log("refold %s closes %s" % (step.Name, unfold.Name))
    return step


def _group(doc, first, last):
    """Fusion groups everything between an Unfold and its Refold in the timeline."""
    try:
        from . import timeline_core, timeline_ops

        tl = timeline_ops.timeline(doc, deps=False)
        names = [i.name for i in tl.items]
        if first.Name not in names or last.Name not in names:
            return
        a, b = names.index(first.Name), names.index(last.Name)
        members = names[min(a, b) : max(a, b) + 1]
        gid = timeline_core.new_group_id(tl)
        title = "Unfold %s" % first.Label
        for n in members:
            timeline_ops._set_group(doc.getObject(n), gid, title)
    except Exception as exc:
        log("unfold group not made: %s" % exc)


def steps_of(body, kind):
    return [o for o in getattr(body, "Group", []) if bodies.kind(o) == kind]


def open_unfold(body):
    """The last Unfold of the body (up to its Tip) that no Refold closes yet, or None."""
    if body is None:
        return None
    chain = []
    obj = body.Tip
    seen = set()
    while obj is not None and obj.Name not in seen:
        seen.add(obj.Name)
        chain.append(obj)
        obj = getattr(obj, "BaseFeature", None)
    closed = set()
    for obj in chain:  # newest first
        kind = bodies.kind(obj)
        if kind == REFOLD_TYPE and obj.Unfold is not None:
            closed.add(obj.Unfold.Name)
        elif kind == UNFOLD_TYPE and obj.Name not in closed:
            return obj
    return None
