# SPDX-License-Identifier: LGPL-2.1-or-later
"""SHEET METAL > CREATE > Lofted Flange (Fusion has it as the Lofted type of its Flange dialog;
SciForge gives it its own entry right under Flange until the two dialogs are merged).

Click a curve of the first profile, then one of the second (each click takes the whole
connected chain of lines and arcs of that sketch, Fusion's auto-chain); the profiles sit on
separate planes, both open or both closed. Forming Type Brake Form (flat facets, sized by the
Facet Control: Chord Tolerance, Facet Angle, Facet Distance or Face Number) or Die Form
(smooth; cannot be laid flat exactly, which the flat pattern explains); Orientation Side 1 /
Side 2 / Center; Operation New Body (a new sheet metal body with the active rule) or Join
(into the active sheet metal body). Geometry: sheetmetal_lofted.py.
"""

import FreeCAD as App

from . import bodies, sheetmetal, sheetmetal_bend as sb, sheetmetal_bend_core as core
from . import sheetmetal_lofted as sl
from . import ui_icon_path
from . import sheetmetal_bend_panel as smp

FORMING_ITEMS = [
    ("Brake Form", "brake", True, "Flat facets joined by folds: a press-brake part"),
    ("Die Form", "die", True, "One smooth surface: a stamped part (cannot be laid flat exactly)"),
]
CONTROL_ITEMS = [
    ("Chord Tolerance", "chord_tolerance", True, "Largest gap (mm) between a facet and the arc"),
    ("Facet Angle", "facet_angle", True, "Largest angle (°) between a facet and the arc"),
    ("Facet Distance", "facet_distance", True, "Widest facet (mm)"),
    ("Face Number", "facet_number", True, "Facets per arc"),
]
ORIENT_ITEMS = [("Side 1", "side1"), ("Side 2", "side2"), ("Center", "center")]


def chain(sketch, short):
    """The names of the connected chain of sketch curves holding edge `short`."""
    import Part

    edges = list(sketch.Shape.Edges)
    try:
        picked = sketch.Shape.getElement(short)
    except Exception:
        return [short]
    for group in Part.sortEdges(edges):
        if any(e.isSame(picked) for e in group):
            names = []
            for e in group:
                for i, f in enumerate(edges, start=1):
                    if f.isSame(e):
                        names.append("Edge%d" % i)
            return names
    return [short]


class LoftedPanel(smp.SmPanel):
    title = "Lofted Flange"
    icon = "sm_lofted_flange"
    NEEDS_BASE = False
    SKETCH_BOXES = ("profile1", "profile2")
    BOXES = [
        ("profile1", "Profile 1", "Select a profile", False),
        ("profile2", "Profile 2", "Select a profile", False),
    ]
    last = None

    def default_options(self):
        opts = sl.default_options()
        self.join_body = self.body if self.body is not None else None
        self.made_body = None
        return opts

    def build_fields(self):
        self.add_combo("forming", "Forming Type", FORMING_ITEMS)
        self.add_combo("control", "Facet Control", CONTROL_ITEMS)
        self.add_number(
            "value",
            "Value",
            "Chord tolerance (mm), angle (°), width (mm) or count",
            0.001,
            1000.0,
            3,
        )
        self.add_combo(
            "orientation",
            "Orientation",
            ORIENT_ITEMS,
            "Which side of the profiles the thickness goes",
        )
        join_ok = getattr(self, "join_body", None) is not None
        self.add_combo(
            "operation",
            "Operation",
            [
                ("New Body", "new_body", True, "A new sheet metal body with the active rule"),
                (
                    "Join",
                    "join",
                    join_ok,
                    (
                        "Into the active sheet metal body"
                        if join_ok
                        else "No sheet metal body to join"
                    ),
                ),
            ],
        )
        self.add_combo(
            "rule",
            "Rule",
            self._rule_items(),
            "The sheet metal rule of the new body (thickness, bend radius)",
        )
        self.fields_changed("forming")

    def _rule_items(self):
        """The design's rules, then the library's (Fusion's Rule box of a new flange body);
        the component's active rule first."""
        from . import components, sheetmetal_core

        doc = self.doc
        try:
            component = components.active_component(doc)
        except Exception:
            component = None
        active = sheetmetal.active_rule_name(doc, component)
        names = [r["name"] for r in sheetmetal.design_rules(doc)]
        names += [r["name"] for r in sheetmetal_core.LIBRARY if r["name"] not in names]
        names.sort(key=lambda n: n != active)
        if self.options.get("rule") is None:
            self.options["rule"] = active
        return [(n, n) for n in names]

    def fields_changed(self, key):
        brake = self.value("forming") == "brake"
        self.show_row("control", brake)
        self.show_row("value", brake)
        self.show_row("rule", self.value("operation") == "new_body" and not self.editing)
        if key == "rule" and self.target is not None and not self.editing:
            target, self.target = self.target, None
            self.drop_preview(target)
            self.quiet_recompute()
        if key == "control":
            control = self.value("control")
            self.set_value("value", core.FACET_DEFAULTS.get(control, 1.0))
        if key == "operation" and self.target is not None and not self.editing:
            target, self.target = self.target, None
            self.drop_preview(target)
            self.quiet_recompute()

    def hint(self):
        if not self.picks["profile1"]:
            return "Click a curve of the first profile (its whole chain of lines and arcs)."
        if not self.picks["profile2"]:
            return "Click a curve of the second profile, on another plane."
        return "Choose Brake Form or Die Form, then OK."

    def accept_pick(self, box, obj, short):
        if obj.TypeId != "Sketcher::SketchObject" or not short.startswith("Edge"):
            return False
        import Part

        edge = obj.Shape.getElement(short)
        if not isinstance(edge.Curve, (Part.Line, Part.LineSegment, Part.Circle, Part.ArcOfCircle)):
            return False
        other = "profile2" if box == "profile1" else "profile1"
        return not any(o is obj for o, _s, _p in self.picks[other])

    def shown(self):
        grouped = []
        for box in self.picks:
            for obj, short, _p in self.picks[box]:
                names = chain(obj, short)
                root, path = smp.rooted(obj, names[0])
                if root is obj:
                    grouped.append((obj, names))
                else:
                    prefix = path[: -len(names[0])]
                    grouped.append((root, [prefix + n for n in names]))
        return grouped

    def _profile(self, box):
        obj, short, _p = self.picks[box][0]
        return [(obj, chain(obj, short))]

    def check(self, options):
        if options.get("forming") == "brake":
            try:
                core.facets_for_arc(10.0, 90.0, options["control"], float(options["value"]))
            except ValueError as exc:
                raise sb.SheetMetalError(str(exc))

    def make_feature(self, options):
        body = sl.target_body(
            self.doc, options.get("operation"), self.join_body, options.get("rule")
        )
        if body is not self.join_body:
            self.made_body = body
        self.body = body
        return sl.make(
            body, self._profile("profile1"), self._profile("profile2"), options, hide=False
        )

    def apply_feature(self, options):
        sl.apply(self.target, self._profile("profile1"), self._profile("profile2"), options)
        self.target.touch()

    def drop_preview(self, target):
        made = self.made_body
        bodies.remove_step(target)
        if made is not None and bodies.alive(made):
            bodies.remove_body(made)
        self.made_body = None
        self.body = self.join_body

    def read_feature(self, feature):
        one, two, options = sl.read(feature)
        self.join_body = bodies.body_of(feature)
        self.made_body = None
        if one:
            self.picks["profile1"] = [(one[0][0], one[0][1][0], None)]
        if two:
            self.picks["profile2"] = [(two[0][0], two[0][1][0], None)]
        return options

    def show_preview(self, on):
        try:
            if self.target is not None and self.target.ViewObject is not None:
                self.target.ViewObject.Visibility = True
        except Exception:
            pass

    def finished(self, obj):
        sl.hide_sketches(obj)
        body = bodies.body_of(obj)
        if body is not None and sheetmetal.is_sheet_metal_body(body):
            from . import pickpanel

            pickpanel.activate(body)


class ViewProviderLofted(smp.StepViewProvider):
    ICON = "sm_lofted_flange"

    def edit(self, obj):
        edit(obj)


def edit(obj):
    smp.edit(LoftedPanel, obj)


class LoftedCommand:
    def GetResources(self):
        return {
            "MenuText": "Lofted Flange",
            "ToolTip": "A sheet metal flange lofted between two profiles on separate planes: "
            "Brake Form (flat facets) or Die Form (smooth)",
            "Pixmap": ui_icon_path("sm_lofted_flange"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        smp.start(LoftedPanel, needs_sheet=False)


COMMANDS = {"SciForge_SheetMetalLoftedFlange": LoftedCommand}
EDITORS = {"SciForge::" + sl.KIND: edit}
smp.register_kinds(
    {sl.KIND: ("Lofted Flange", "sm_lofted_flange")}, {sl.KIND: [("FacetValue", "Facet Value")]}
)
