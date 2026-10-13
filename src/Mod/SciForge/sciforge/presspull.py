# SPDX-License-Identifier: LGPL-2.1-or-later
"""The parametric Press/Pull feature that lives in a body's timeline.

It is a PartDesign::FeaturePython, so it behaves like any PartDesign feature:
it takes the previous feature's shape (BaseFeature), later features build on
it, editing earlier steps recomputes it, and it shows in the timeline.
This module has no GUI code, so golden models can create it headless.
Saved documents store the class path "sciforge.presspull.PressPullFeature";
keep the name and properties stable.
"""

import FreeCAD as App

from . import curves
from . import presspull_core as core

TYPE = "PartDesign::FeaturePython"


class PressPullFeature:
    def __init__(self, obj):
        obj.Proxy = self
        self.ensure_properties(obj)

    @staticmethod
    def ensure_properties(obj):
        if "Faces" not in obj.PropertiesList:
            obj.addProperty(
                "App::PropertyLinkSub", "Faces", "Press Pull", "The faces that are pushed or pulled"
            )
        if "Distance" not in obj.PropertiesList:
            obj.addProperty(
                "App::PropertyDistance",
                "Distance",
                "Press Pull",
                "How far the faces move along their outward normal "
                "(positive adds material, negative removes it)",
            )
        if "Refine" not in obj.PropertiesList:
            obj.addProperty(
                "App::PropertyBool",
                "Refine",
                "Press Pull",
                "Merge faces that end up coplanar, like Fusion",
            )
            obj.Refine = True
        if "SciForgeType" not in obj.PropertiesList:
            obj.addProperty("App::PropertyString", "SciForgeType", "Base", "", 4)  # hidden
            obj.SciForgeType = "PressPull"

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)

    def execute(self, obj):
        self.tool = None  # the material taken away, for the dialog's red preview
        base_obj = obj.BaseFeature
        if base_obj is None or base_obj.Shape.isNull():
            raise core.PressPullError("Press Pull needs a solid before it in the timeline.")
        # A face FreeCAD lost (reopened design, an earlier Extrude edited, a sweep or loft in
        # between: "?Face3") is found again where it was (sweep / loft QA).
        curves.refind(obj, ("Faces",))
        link = obj.Faces
        if not link or not link[1]:
            raise core.PressPullError("Select one or more faces to push or pull.")
        source, names = link[0], link[1]
        faces = []
        for name in names:
            try:
                faces.append(source.Shape.getElement(name))
            except Exception:
                raise core.PressPullError(
                    "The face %s no longer exists (an earlier step changed the model). "
                    "Edit this Press Pull and select the face again." % name
                )
        notes = []
        pieces = []
        obj.Shape = core.press_pull(
            base_obj.Shape,
            faces,
            obj.Distance.Value,
            refine=obj.Refine,
            report=notes,
            pieces=pieces,
        )
        if pieces and obj.Distance.Value < 0:
            self.tool = pieces[0]  # body coordinates; not saved (dumps() keeps nothing)
        curves.remember(obj, ("Faces",))
        # Shown by the dialog: e.g. neighbours that could not be extended.
        self.note = " ".join(notes)

    # FreeCAD saves the proxy with the document; nothing extra to store.
    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


KINDS = ("PressPull", "OffsetFace")  # Offset Face (Modify menu) is the same step


def kind_of(obj):
    return getattr(obj, "SciForgeType", "") if obj is not None else ""


def is_press_pull(obj):
    return kind_of(obj) in KINDS


def removed_material(obj):
    """The material a push into the part takes away (body coordinates), or None: what the
    dialog shows in red. execute() keeps it; a design opened from a file has not run
    execute() yet (nothing of it is saved), so it is made again from the pushed faces."""
    proxy = getattr(obj, "Proxy", None)
    tool = getattr(proxy, "tool", None)
    if tool is not None or proxy is None:
        return tool
    try:
        distance = obj.Distance.Value
        link = obj.Faces
        if distance >= 0 or not link or not link[1]:
            return None
        source = link[0]
        slabs = [core.slab(source.Shape.getElement(name), distance) for name in link[1]]
        tool = slabs[0] if len(slabs) == 1 else slabs[0].multiFuse(slabs[1:])
    except Exception:
        return None
    proxy.tool = tool  # until the next execute() makes it again
    return tool


def make(body, base, face_names, distance, name="PressPull", kind="PressPull"):
    """Add a Press Pull (or, ``kind`` "OffsetFace", an Offset Face) to `body` after `base`
    (normally body.Tip). Returns the feature."""
    obj = body.newObject(TYPE, name if kind == "PressPull" else kind)
    PressPullFeature(obj)
    if kind != "PressPull":
        obj.SciForgeType = kind
    obj.BaseFeature = base
    obj.Faces = (base, list(face_names))
    obj.Distance = distance
    body.Tip = obj  # newObject() does not always move the Tip for Python features
    try:
        if App.GuiUp and obj.ViewObject is not None:
            from .presspull_ui import ViewProviderPressPull

            ViewProviderPressPull(obj.ViewObject)
    except Exception:
        pass
    return obj
