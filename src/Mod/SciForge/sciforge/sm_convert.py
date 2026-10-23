# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's Convert to Sheet Metal (MODIFY), FreeCAD only, no Qt.

A solid of even thickness (made with Shell, Extrude or imported) becomes a sheet metal body:
its planar walls are the flanges, its cylindrical faces of constant thickness the bends.
The thickness is measured at the picked face (shown, never edited); the rule is either a
new "template" rule from that thickness or a rule of the design / library copied with the
thickness set to the detected value. A solid that is not one sheet of even thickness, or
whose walls meet at sharp corners (Fusion: "add fillets"), is refused with the reason.

    detect(shape, face)                  -> {"thickness", "bends", "radius"} or ConvertError
    rules_for(doc, thickness, matching)  -> the rule names the dialog offers
    rule_for_conversion(doc, choice, thickness, radius) -> the rule dict to use
    make(body, base, face, choice)       -> the step (the body becomes sheet metal)
"""

import FreeCAD as App

from . import bodies, components, log, sheetmetal, sheetmetal_core as core
from . import sheetmetal_unfold as unfolder

CONVERT_TYPE = "ConvertToSheetMetal"
FP_TYPE = "PartDesign::FeaturePython"
TEMPLATE = "Template Rule"


class ConvertError(ValueError):
    """A refusal with the reason."""


def detect(shape, face):
    """Thickness and bends of the solid seen from face ('FaceN'): checks that it is one
    sheet of even thickness made of flat walls and round bends."""
    if shape is None or shape.isNull() or not shape.Solids:
        raise ConvertError("there is no solid to convert")
    try:
        result = unfolder.unfold(shape, face, 0.44)
    except unfolder.UnfoldError as exc:
        text = str(exc)
        if "closes on itself" in text or "overlaps" in text:
            # a closed tube or box is still sheet metal: it needs a Rip before a flat
            # pattern, not before the conversion
            try:
                result = _measure_only(shape, face)
            except unfolder.UnfoldError as exc2:
                raise ConvertError(str(exc2))
        else:
            raise ConvertError(text)
    radii = sorted(set(round(b.inner_radius, 6) for b in result.bends))
    return {
        "thickness": result.thickness,
        "bends": len(result.bends),
        "radius": radii[0] if radii else None,
        "radii": radii,
    }


def _measure_only(shape, face):
    """The walk and the fill check without laying anything flat (closed shapes)."""
    solid = shape.Solids[0]
    index = unfolder.face_index(face)
    start = solid.Faces[index]
    if not unfolder.is_planar(start):
        raise unfolder.UnfoldError("pick a flat face of a wall (a wide top or bottom face)")
    T = unfolder.thickness_at(solid, start)
    # every bend kept: nothing is laid flat, so a closed loop is fine
    result = unfolder.unfold(shape, face, 0.44, bends=[], check=True)
    result.thickness = T
    bends = []
    for fmap in result.maps:
        if fmap.kind == "kept":
            fmap.angle = max(fmap.phi(v.Point) for v in fmap.face.Vertexes)
            bends.append(unfolder.Bend(fmap, ((None, None),) * 3, 0.0))
    result.bends = bends
    return result


def rules_for(doc, thickness, matching=True):
    """[(label, key)] of the rules the dialog offers: the template first, then the design's
    rules, then the library's (with matching=True only those whose thickness is the
    detected one)."""
    out = [(TEMPLATE, TEMPLATE)]
    seen = set()
    for source, rules in (
        ("In This Design", sheetmetal.design_rules(doc)),
        ("Library", core.LIBRARY),
    ):
        for rule in rules:
            name = rule["name"]
            key = "%s|%s" % (source, name)
            if name in seen and source == "Library":
                continue
            seen.add(name)
            if matching and not _same_thickness(rule, thickness):
                continue
            out.append(("%s (%s)" % (name, source), key))
    return out


def _same_thickness(rule, thickness):
    try:
        return abs(core.evaluated(rule)["thickness"] - thickness) < 1e-4
    except ValueError:
        return False


def _format(value):
    text = ("%.4f" % value).rstrip("0").rstrip(".")
    return text or "0"


def rule_for_conversion(doc, choice, thickness, radius=None):
    """The rule the converted body follows (a dict, not saved yet)."""
    if not choice or choice == TEMPLATE:
        base = core.library_rule(core.DEFAULT_RULE)
        name = "Converted %s mm" % _format(thickness)
        values = {"thickness": _format(thickness)}
        if radius is not None:
            values["bend_radius"] = _format(radius)
        rule = core.make_rule(name, **values)
        for key in ("k_factor", "miter_gap", "bend_relief_shape"):
            rule[key] = base[key]
        return rule
    source, _sep, name = choice.partition("|")
    rule = sheetmetal.find_rule(doc, name) if source == "In This Design" else None
    rule = rule or core.library_rule(name)
    if rule is None:
        raise ConvertError("there is no rule named %s" % name)
    if _same_thickness(rule, thickness):
        return dict(rule)
    copy = dict(rule)
    scale = core.MM_PER_UNIT[rule["units"]]
    copy["thickness"] = _format(thickness / scale)
    copy["name"] = "%s %s mm" % (name, _format(thickness))
    return copy


def _is_sheet_metal_component(component):
    try:
        from . import sheetmetal_component

        return sheetmetal_component.is_sheet_metal(component)
    except ImportError:  # without sm-forming's component types: its own rule says so
        return bool(getattr(component, sheetmetal.RULE_PROP, ""))


def _make_sheet_metal_component(component, rule_name):
    try:
        from . import sheetmetal_component

        sheetmetal_component.make_sheet_metal(component, rule_name)
    except ImportError:
        sheetmetal.set_active_rule(component.Document, rule_name, component)


class ConvertFeature:
    """The timeline step of Convert to Sheet Metal (the shape passes through; it records
    the face and the thickness, and turns red when the body stops being sheet metal).
    Saved files store "sciforge.sm_convert.ConvertFeature"."""

    def __init__(self, obj):
        obj.Proxy = self
        self.ensure_properties(obj)

    @staticmethod
    def ensure_properties(obj):
        if "Face" not in obj.PropertiesList:
            obj.addProperty("App::PropertyLinkSub", "Face", "Convert", "The face picked")
        if "Thickness" not in obj.PropertiesList:
            obj.addProperty("App::PropertyLength", "Thickness", "Convert", "Detected thickness")
            obj.setEditorMode("Thickness", 1)
        if "Rule" not in obj.PropertiesList:
            obj.addProperty("App::PropertyString", "Rule", "Convert", "The sheet metal rule")
            obj.setEditorMode("Rule", 1)
        bodies.mark(obj, CONVERT_TYPE)

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)

    def execute(self, obj):
        base = obj.BaseFeature
        try:
            if base is None or base.Shape.isNull() or not base.Shape.Solids:
                raise ConvertError("Convert to Sheet Metal needs a solid before it")
            face = ""
            if obj.Face:
                subs = obj.Face[1]
                subs = [subs] if isinstance(subs, str) else subs
                face = (subs[0] if subs else "").lstrip("?")
            info = detect(base.Shape, face)
            if abs(info["thickness"] - obj.Thickness.Value) > 1e-4:
                raise ConvertError(
                    "the body is %.3f mm thick now, its rule says %.3f mm"
                    % (info["thickness"], obj.Thickness.Value)
                )
        except Exception:
            bodies.pass_through(obj)
            raise
        obj.Shape = bodies.baked(base.Shape)

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def make(body, base, face, choice=TEMPLATE, name="ConvertToSheetMetal"):
    """Convert body (its solid base) to sheet metal from face. Returns the step; raises
    ConvertError with the reason (nothing is changed then)."""
    if body is None or base is None:
        raise ConvertError("pick a face of a solid body")
    info = detect(base.Shape, face)
    doc = body.Document
    component = components.container_of(body)
    rule = None
    comp_rule = ""
    if component is not None and _is_sheet_metal_component(component):
        comp_rule = sheetmetal.active_rule_name(doc, component)
    if sheetmetal.is_sheet_metal_body(body):
        rule = sheetmetal.find_rule(doc, sheetmetal.body_rule_name(body))
    elif comp_rule:
        # Fusion: in a sheet metal component the component's active rule is used
        rule = sheetmetal.find_rule(doc, comp_rule) or core.library_rule(comp_rule)
    if rule is not None and not _same_thickness(rule, info["thickness"]):
        raise ConvertError(
            "the component's rule %s is not %s mm thick: pick a body of that thickness or "
            "change the rule" % (rule["name"], _format(info["thickness"]))
        )
    if rule is None:
        rule = rule_for_conversion(doc, choice, info["thickness"], info["radius"])
    sheetmetal.save_rule(doc, rule)
    step = bodies.insert_after_tip(body, FP_TYPE, name)
    ConvertFeature(step)
    step.BaseFeature = base
    step.Face = (base, [face])
    step.Thickness = info["thickness"]
    step.Rule = rule["name"]
    if App.GuiUp:
        try:
            from .unfold_ui import ViewProviderFlatStep

            ViewProviderFlatStep(step.ViewObject, "convert")
        except Exception:
            pass
    sheetmetal.make_sheet_metal_body(body, rule["name"])
    if component is not None and not comp_rule:
        # Fusion: the Standard component it is in becomes a Sheet Metal component (one way)
        _make_sheet_metal_component(component, rule["name"])
    log(
        "converted %s to sheet metal (%.3f mm, %d bends, rule %s)"
        % (body.Label, info["thickness"], info["bends"], rule["name"])
    )
    return step
