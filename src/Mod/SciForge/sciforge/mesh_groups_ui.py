# SPDX-License-Identifier: LGPL-2.1-or-later
"""MESH > PREPARE > Create Face Group and Combine Face Groups.

Create Face Group: faces picked with the brush (as Erase and Fill picks them; joined or not)
become one new face group. Fusion offers it inside Direct Edit (MODIFY > Direct Edit has it
too, as one of its edits); here it is also a timeline step of its own, like SciForge's Erase
and Fill.

Combine Face Groups: click two or more face groups that share an edge; they become one face
group (Fusion's PREPARE > Combine Face Groups, a timeline feature). Groups that do not touch
are refused with the reason.

Face groups show in their own colours on the body. Spec and sources:
docs/sciforge/parity/mesh.md."""

import FreeCAD as App

from . import insert_ui, mesh, mesh_pick_ui, mesh_ui
from . import mesh_core as core


class CreateFaceGroupPanel(mesh_pick_ui.FacePickPanel):
    """Fusion's Create Face Group: the picked faces become one face group."""

    title = "Create Face Group"
    icon = "mesh_create_group"
    step_kind = "MeshCreateFaceGroup"
    wait_text = "Click the mesh body, then paint over the faces of the new face group."

    def report(self):
        mesh_pick_ui.FacePickPanel.report(self)
        if self.step is not None and not self.picked_faces:
            self.say(
                "Click the faces of the new face group (each click takes the faces within "
                "the Brush Size; Ctrl+click takes them off)."
            )


class CombineFaceGroupsPanel(mesh_ui.MeshPanel):
    """Fusion's Combine Face Groups: two or more face groups that touch become one."""

    title = "Combine Face Groups"
    icon = "mesh_combine_groups"
    step_kind = "MeshCombineFaceGroups"
    preview_box = False
    wait_text = "Click the mesh body, then the face groups to combine."

    def build(self):
        self.chosen = []  # [(group number, centre of the face clicked)]
        self.groups_field = self.add_field("groups", "Face Groups", "Select face groups")

    def first_waiting(self):
        return "groups"

    def after_body(self):
        groups = self._body_groups()
        self.groups_field.widget.setEnabled(core.group_count(groups) > 1)

    def _body_groups(self):
        src = self.body
        return list(getattr(src, "FaceGroups", []) or []) if src is not None else []

    def pick_other(self, name, obj, sub, point):
        if name != "groups":
            return
        if obj not in self.own_objects() and obj is not self.body:
            if mesh_ui.body_end(obj) and not self.chosen:
                self.pick_body(obj)
            return
        groups = self._body_groups()
        if core.group_count(groups) < 2:
            self.message.setText(
                "⚠ The body has no face groups to combine: PREPARE > Generate Face Groups "
                "first (or Create Face Group)."
            )
            return
        index = mesh_ui.facet_at(self.body, point)
        if index is None or index >= len(groups):
            return
        group = groups[index]
        known = [g for g, _c in self.chosen]
        if group in known:
            self.chosen.pop(known.index(group))
        else:
            points, facets = mesh.topology(mesh.global_mesh(self.body))
            self.chosen.append((group, core.centroid(points, facets[index])))
        self._show_groups()
        self.changed()

    def cleared(self, name):
        if name == "groups":
            self.chosen = []
            self._show_groups()
            self.changed()

    def _show_groups(self):
        count = len(self.chosen)
        self.groups_field.set_text(
            "%d face group%s" % (count, "" if count == 1 else "s") if count else ""
        )

    def load(self, feature):
        try:
            source = mesh.global_mesh(feature.Source)
            state = mesh.edit_state(source, list(getattr(feature.Source, "FaceGroups", []) or []))
            self.chosen = []
            for pick in feature.Picks:
                which, _lost = state.find([tuple(pick)])
                if which:
                    self.chosen.append((state.groups[which[0]], tuple(pick)))
        except Exception:
            self.chosen = [(None, tuple(p)) for p in feature.Picks]
        self._show_groups()

    def write(self, step):
        step.Picks = [App.Vector(*c) for _g, c in self.chosen]
        mesh.hold(step, len(self.chosen) < 2)  # until two are picked: the body as it is

    def _hold_by_preview(self):
        if self.step is not None:
            mesh.hold(self.step, len(self.chosen) < 2)

    def report(self):
        mesh_ui.MeshPanel.report(self)
        if self.step is not None and len(self.chosen) < 2:
            self.message.setText("")
            self.say(
                "Click two or more face groups that touch (a click on a picked group drops it)."
            )

    def _accept(self):
        if self.step is not None and len(self.chosen) < 2:
            self.message.setText("⚠ Pick two or more face groups that touch.")
            return False
        return mesh_ui.MeshPanel._accept(self)


class CreateFaceGroupCommand(mesh_ui._MeshCommand):
    text = "Create Face Group"
    tip = "Make faces of a mesh body one face group"
    icon = "mesh_create_group"
    panel = CreateFaceGroupPanel


class CombineFaceGroupsCommand(mesh_ui._MeshCommand):
    text = "Combine Face Groups"
    tip = "Join face groups of a mesh body that touch into one"
    icon = "mesh_combine_groups"
    panel = CombineFaceGroupsPanel


def _edit(panel_class):
    def edit(obj):
        return insert_ui._edit(panel_class, mesh.step_of(obj))

    return edit


COMMANDS = {
    "SciForge_MeshCreateFaceGroup": CreateFaceGroupCommand,
    "SciForge_MeshCombineFaceGroups": CombineFaceGroupsCommand,
}
EDITORS = {
    "SciForge::MeshCreateFaceGroup": _edit(CreateFaceGroupPanel),
    "SciForge::MeshCombineFaceGroups": _edit(CombineFaceGroupsPanel),
}
