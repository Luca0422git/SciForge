# SPDX-License-Identifier: LGPL-2.1-or-later
"""Thread command with Fusion's dialog.

Click cylindrical faces (only they light up): the side of a shaft gets an outside thread, the
wall of a hole an inside one, and the size is taken from the diameter. Fields as in Fusion:
Faces, Modeled, Full Length (else Thread Length and Offset, from the end nearer to where you
clicked; the blue arrow drags the length), Thread Type (ISO Metric profile / ANSI Unified
Screw Threads), Size, Designation, Class, Direction. One undo step; double-click the thread in
the timeline to edit it.

A cosmetic thread (Modeled off) leaves the part as it is and is drawn as a dashed helix on
the face (CosmeticThreads below); so are tapped holes that are not modeled.
"""
import math

import FreeCAD as App
import FreeCADGui as Gui

from . import commands, log, preview, ui_icon_path, warn
from . import hole_common as common
from . import thread
from . import thread_core as core
from . import thread_tables as tables
from .compat import QtCore, QtWidgets
from .taskui import ArrowDragger, DistanceField, Panel

DIRECTION_LABELS = [("Right hand", "right"), ("Left hand", "left")]

PLAIN = (
    ("multiple solids", "This thread would cut the part into pieces. Make it shorter."),
    ("could not be built", "This thread cannot be modeled here. Untick Modeled."),
)


def plain(text):
    for needle, said in PLAIN:
        if needle.lower() in (text or "").lower():
            return said
    return text


class ViewProviderThread:
    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.Object = vobj.Object

    def getIcon(self):
        return ui_icon_path("thread")

    def setEdit(self, vobj, mode=0):
        if mode != 0:
            return None
        edit(vobj.Object)
        return True

    def unsetEdit(self, vobj, mode=0):
        return None

    def doubleClicked(self, vobj):
        edit(vobj.Object)
        return True

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def _base_face(base, body, point):
    """'FaceN' of `base` under a clicked point (global), or None."""
    from . import hole

    local = hole.to_local(body, point)
    return hole.base_face_at(base, local)


class ThreadPanel(Panel):
    title = "Thread"
    icon = "thread"
    last = None
    remembered = {}  # Fusion starts with the settings of the last thread

    def __init__(self, doc, feature=None, selection=None):
        super().__init__(doc, "Thread" if feature is None else "Edit Thread")
        ThreadPanel.last = self
        self.escape = preview.EscapeCancels(self)
        self.target = feature
        self.editing = feature is not None
        self.body = thread.owner_body(feature) if feature is not None else commands.find_body()
        self.base = feature.BaseFeature if feature is not None else self._tip()
        self.options = dict(thread.DEFAULTS)
        self.faces = []  # "FaceN" of self.source
        self.source = self.base
        if feature is not None:
            try:
                self.options.update(thread.read(feature))
                if feature.Faces:
                    self.source = feature.Faces[0]
                    self.faces = list(feature.Faces[1])
            except Exception as exc:
                warn("could not read %s: %s" % (feature.Label, exc))
        else:
            self.options.update(ThreadPanel.remembered)
            self.options.update({"size": "", "designation": "", "thread_class": ""})
        self.error = ""
        self.dirty = False
        self._quiet = False
        self.active = "faces"
        self.draggers = {}
        self.dragger = None
        self.observer = None
        self.gate = None
        self.watch = common.DocumentWatch(self)
        self._build_form()
        self._show_options()
        self._watch()
        self.activate("faces")
        if feature is not None:
            self._refresh()
            self._make_draggers()
        else:
            self._start(selection)

    # -- form -----------------------------------------------------------------------------
    def _build_form(self):
        form = self.layout
        self.what = QtWidgets.QLabel(
            "Click the side of a shaft or the wall of a hole. Click it again to drop it."
        )
        self.what.setWordWrap(True)
        form.addRow(self.what)
        self.fields = {"faces": common.SelectionField(self, "faces", "Select a cylindrical face")}
        form.addRow("Faces", self.fields["faces"].widget)
        self.info = QtWidgets.QLabel("")
        form.addRow(self.info)
        self.modeled = QtWidgets.QCheckBox("Modeled")
        self.modeled.setToolTip("Cut the real thread; off: the thread is recorded and drawn only")
        form.addRow("", self.modeled)
        self.full_length = QtWidgets.QCheckBox("Full Length")
        form.addRow("", self.full_length)
        self.length = DistanceField(self.options["length"], on_change=self._length_typed)
        self.length_label = QtWidgets.QLabel("Thread Length")
        form.addRow(self.length_label, self.length.widget)
        self.offset = DistanceField(self.options["offset"], on_change=self._typed)
        self.offset_label = QtWidgets.QLabel("Offset")
        form.addRow(self.offset_label, self.offset.widget)
        self.standard = common.combo([(label, key) for key, label in tables.STANDARDS])
        form.addRow("Thread Type", self.standard)
        self.size = QtWidgets.QComboBox()
        form.addRow("Size", self.size)
        self.designation = QtWidgets.QComboBox()
        form.addRow("Designation", self.designation)
        self.thread_class = QtWidgets.QComboBox()
        form.addRow("Class", self.thread_class)
        self.direction = common.combo(DIRECTION_LABELS, self.options["direction"])
        form.addRow("Direction", self.direction)
        self.finish_layout()
        self.modeled.toggled.connect(self._typed)
        self.full_length.toggled.connect(self._full_toggled)
        self.standard.currentIndexChanged.connect(self._standard_changed)
        self.size.currentIndexChanged.connect(self._size_changed)
        for box in (self.designation, self.thread_class, self.direction):
            box.currentIndexChanged.connect(self._typed)

    def _internal(self):
        c = self._first_cylinder()
        return bool(c.internal) if c is not None else False

    def _first_cylinder(self):
        if self.source is None or not self.faces:
            return None
        try:
            return thread.cylinder_of(self.source.Shape, self.faces[0])
        except Exception:
            return None

    def _show_options(self):
        o = self.options
        self._quiet = True
        try:
            common.set_combo(self.standard, o["standard"])
            self._fill_sizes(o["standard"], o.get("size", ""), o.get("designation", ""))
            common.set_combo(self.direction, o["direction"])
            self.modeled.setChecked(bool(o["modeled"]))
            self.full_length.setChecked(bool(o["full_length"]))
            self.length.set_value(o["length"])
            self.offset.set_value(o["offset"])
        finally:
            self._quiet = False
        self._update_visibility()

    def _fill_sizes(self, standard, size, designation):
        d = tables.find(standard, designation) if designation else None
        if d is not None:
            size = d.size
        sizes = tables.sizes(standard)
        if size not in sizes:
            size = "6" if standard == "iso" else "1/4"
        common.fill_combo(self.size, [(s, s) for s in sizes], size)
        found = tables.designations(standard, self.size.currentData())
        common.fill_combo(self.designation, [(x.label, x.label) for x in found], designation)
        self._fill_classes()

    def _fill_classes(self):
        standard = self.standard.currentData()
        internal = self._internal()
        wanted = thread.thread_class(
            {"standard": standard, "thread_class": self.options.get("thread_class", "")},
            internal,
        )
        common.fill_combo(
            self.thread_class, [(c, c) for c in tables.classes(standard, internal)], wanted
        )

    def _update_visibility(self):
        partial = not self.full_length.isChecked()
        for widget in (self.length.widget, self.length_label, self.offset.widget):
            widget.setVisible(partial)
        self.offset_label.setVisible(partial)

    def _collect(self):
        o = self.options
        o["standard"] = self.standard.currentData()
        o["size"] = self.size.currentData() or ""
        o["designation"] = self.designation.currentData() or ""
        o["thread_class"] = self.thread_class.currentData() or ""
        o["direction"] = self.direction.currentData()
        o["modeled"] = self.modeled.isChecked()
        o["full_length"] = self.full_length.isChecked()
        o["length"] = self.length.value()
        o["offset"] = self.offset.value()

    # -- what can be picked -------------------------------------------------------------------
    def allow(self, obj, name):
        if not name.startswith("Face"):
            return False
        try:
            if obj.isDerivedFrom("Sketcher::SketchObject") or not obj.Shape.Solids:
                return False
            return thread.is_cylinder(obj.Shape.getElement(name))
        except Exception:
            return False

    def activate(self, name):
        self.active = name
        for key, field in self.fields.items():
            field.set_active(key == name)

    def clear_field(self, name):
        self.faces = []
        self._faces_changed()
        self.activate(name)

    # -- starting ---------------------------------------------------------------------------
    def _tip(self):
        body = self.body
        tip = body.Tip if body is not None else None
        if tip is None or tip.Shape.isNull() or not tip.Shape.Solids:
            return None
        return tip

    def _start(self, selection=None):
        found = list(selection) if selection is not None else common.picks()
        try:
            Gui.Selection.clearSelection()
        except Exception:
            pass
        faces = [(o, s, p) for o, s, p in found if s.startswith("Face") and self.allow(o, s)]
        if self.base is None and faces:
            owner = thread.owner_body(faces[0][0])
            if owner is not None:
                self._use_body(owner)
        if self.base is None:
            self.message.setText("⚠ Make a solid first: Create Sketch, then Extrude.")
            self._refresh()
            return
        for obj, short, point in faces:
            self._face_clicked(obj, short, point)
        self._refresh()
        if self.target is not None:
            self._timer.stop()
            self._recompute()

    def _use_body(self, body):
        self.body = body
        self.base = self._tip()
        self.source = self.base
        try:
            Gui.ActiveDocument.ActiveView.setActiveObject("pdbody", body)
        except Exception:
            pass

    def _watch(self):
        panel = self

        class Observer:
            def addSelection(self, doc, obj, sub, pnt):
                QtCore.QTimer.singleShot(30, panel._selection_changed)

        self.observer = Observer()
        Gui.Selection.addObserver(self.observer)
        self.gate = common.install_gate(self)

    def _unwatch(self):
        if self.observer is not None:
            Gui.Selection.removeObserver(self.observer)
            self.observer = None
        common.remove_gate(self.gate)
        self.gate = None

    # -- clicks -----------------------------------------------------------------------------
    def _selection_changed(self):
        if self._closed:
            return
        try:
            found = common.picks()
            if not found:
                return
            Gui.Selection.clearSelection()
            for obj, short, point in found:
                if short.startswith("Face"):
                    self._face_clicked(obj, short, point)
            self._refresh()
        except Exception as exc:
            warn("thread pick: %s" % exc)

    def _face_clicked(self, obj, short, point):
        face = common.global_shape(obj, short)
        if face is None or not thread.is_cylinder(face):
            self.message.setText("Pick a cylindrical face: the side of a shaft or a hole's wall.")
            return
        owner = thread.owner_body(obj)
        if owner is None:
            return
        if owner is not self.body:
            if self.editing:
                self.message.setText(
                    "Pick a face of %s, the body this thread is on."
                    % (self.body.Label if self.body is not None else "its body")
                )
                return
            if self.target is not None:
                self._drop_target()
            self.faces = []
            self._use_body(owner)
            if self.base is None:
                return
        if point is None:
            u0, u1, v0, v1 = face.ParameterRange
            point = face.valueAt((u0 + u1) / 2.0, (v0 + v1) / 2.0)
        # A face of the part as it is before this thread is taken as it is; one clicked on the
        # preview is looked up on the part before it.
        name = short if obj is self.source else _base_face(self.source, self.body, point)
        if name is None:
            self.message.setText("That face is made by this thread. Pick a face of the part.")
            return
        if name in self.faces:
            self.faces = [f for f in self.faces if f != name]
        else:
            first = not self.faces
            self.faces = self.faces + [name]
            if first:
                self._first_face(name, point)
        self._faces_changed()

    def _first_face(self, name, point):
        """Fusion takes the size from the first face, and starts the thread at the end of the
        face nearer to where it was clicked."""
        from . import hole

        try:
            c = thread.cylinder_of(self.source.Shape, name)
        except thread.ThreadError as exc:
            self.message.setText("⚠ %s" % exc)
            return
        local = hole.to_local(self.body, point)
        z = (local - c.base).dot(c.axis)
        self.options["from_end"] = (z - c.z0) > (c.z1 - z)
        d = thread.size_for(c, self.standard.currentData())
        if d is not None:
            self.options["thread_class"] = ""
            self._quiet = True
            try:
                self._fill_sizes(d.standard, d.size, d.label)
            finally:
                self._quiet = False
        if not self.editing and abs(self.length.value()) < 1e-9:
            self._quiet = True
            self.length.set_value(round(min(c.length, 10.0), 3))
            self._quiet = False

    def _faces_changed(self):
        if not self.faces:
            if self.target is not None and not self.editing:
                self._drop_target()
            self._refresh()
            if self.editing:
                self.error = "Pick at least one cylindrical face."
                self.message.setText("⚠ " + self.error)
            return
        self.message.setText("")
        self.error = ""
        try:
            cylinders = [thread.cylinder_of(self.source.Shape, f) for f in self.faces]
            thread.check_faces(cylinders)
        except thread.ThreadError as exc:
            self.faces = self.faces[:-1]
            self.message.setText("⚠ %s" % exc)
            self._refresh()
            return
        self._refresh()
        self._changed()

    def _drop_target(self):
        if self.target is None or self.editing:
            return
        target, self.target = self.target, None
        self._remove_draggers()
        try:
            thread.remove(target)
        except Exception as exc:
            warn("thread: could not remove the preview: %s" % exc)
        self.schedule()

    def _refresh(self):
        count = len(self.faces)
        self.fields["faces"].set_text("%d selected" % count if count else "")
        c = self._first_cylinder()
        if c is None:
            self.info.setText("")
        else:
            self.info.setText(
                "%s thread, %s %.3g mm, %.3g mm long"
                % ("Inside" if c.internal else "Outside", "⌀", c.diameter, c.length)
            )
        if self.base is None and self.target is None:
            self.what.setText("Make a solid first (Create Sketch, then Extrude).")
        self._update_visibility()

    # -- changes ----------------------------------------------------------------------------
    def _typed(self, *_):
        if not self._quiet:
            self._changed()

    def _full_toggled(self, *_):
        if self._quiet:
            return
        self._update_visibility()
        self._changed()

    def _length_typed(self, value):
        if self._quiet:
            return
        arrow = self.draggers.get("length")
        if arrow is not None:
            arrow.set_distance(value)
        self._changed()

    def _standard_changed(self, *_):
        if self._quiet:
            return
        standard = self.standard.currentData()
        c = self._first_cylinder()
        d = thread.size_for(c, standard) if c is not None else None
        self._quiet = True
        try:
            self.options["thread_class"] = ""
            self._fill_sizes(standard, d.size if d else "", d.label if d else "")
        finally:
            self._quiet = False
        self._changed()

    def _size_changed(self, *_):
        if self._quiet:
            return
        found = tables.designations(self.standard.currentData(), self.size.currentData())
        common.fill_combo(self.designation, [(d.label, d.label) for d in found], None)
        self._changed()

    def _changed(self):
        self._collect()
        self.dirty = True
        self.schedule()

    def _recompute(self):
        if self._closed:
            return
        if self.doc.Recomputing:
            # A long recompute lets Qt run timers meanwhile: never start a second one.
            self._timer.start()
            return
        try:
            if self.dirty:
                self.dirty = False
                self._apply()
            preview.recompute(self.doc)
            self.show_status()
            self._make_draggers()
        except Exception as exc:
            self.message.setText("⚠ %s" % exc)

    def _apply(self):
        if not self.faces:
            return
        self._collect()
        try:
            if self.target is None:
                self.target = thread.make(self.body, self.source, self.faces, self.options)
            else:
                thread.apply(self.target, (self.source, self.faces), self.options)
            self.error = ""
        except thread.ThreadError as exc:
            self.error = str(exc)
        except Exception as exc:
            self.error = "This thread cannot be built: %s" % exc

    def feature(self):
        return self.target

    def show_status(self):
        if self.error:
            self.message.setText("⚠ " + self.error)
            return
        text = plain(preview.failure(self.target))
        self.message.setText("⚠ " + text if text else "")

    # -- the length arrow -------------------------------------------------------------------
    def _remove_draggers(self):
        for handle in self.draggers.values():
            try:
                handle.remove()
            except Exception:
                pass
        self.draggers = {}
        self.dragger = None

    def _make_draggers(self):
        if self._closed or any(common.is_dragging(h) for h in self.draggers.values()):
            return
        self._remove_draggers()
        if self.target is None or self.full_length.isChecked() or not self.faces:
            return
        if preview.failure(self.target):
            return
        try:
            c = self._first_cylinder()
            if c is None:
                return
            place = self.body.getGlobalPlacement()
            axis = place.Rotation.multVec(c.axis)
            from_end = bool(self.options.get("from_end"))
            start_z = (c.z1 - self.offset.value()) if from_end else (c.z0 + self.offset.value())
            along = axis * (-1.0 if from_end else 1.0)
            start = place.multVec(c.at(start_z))
            look = App.Vector(Gui.ActiveDocument.ActiveView.getViewDirection())
            radial = (look - axis * look.dot(axis)) * -1.0
            if radial.Length < 1e-9:
                radial = axis.cross(App.Vector(1, 0, 0))
                if radial.Length < 1e-9:
                    radial = axis.cross(App.Vector(0, 1, 0))
            radial.normalize()
            size = max(2.0, min(c.length * 0.25, 15.0))
            reach = c.radius + size * 0.3 if not c.internal else 0.0
            self.length_origin = start + radial * reach
            self.length_direction = along
            arrow = ArrowDragger(
                self.length_origin,
                along,
                self.length.value(),
                size,
                on_drag=self._length_dragged,
                on_release=self._length_dragged,
            )
            common.on_top(arrow.root)
            self.dragger = self.draggers["length"] = arrow
        except Exception as exc:
            warn("thread handle unavailable: %s" % exc)

    def _length_dragged(self, value):
        self._quiet = True
        try:
            self.length.set_value(max(round(value, 2), 0.1))
        finally:
            self._quiet = False
        self._changed()

    # -- undo / closing while open ----------------------------------------------------------
    def document_event(self, closing):
        if closing:
            self.target = self.base = self.body = self.source = None
            common.abandon(self)
        else:
            QtCore.QTimer.singleShot(0, lambda: common.end_after_undo(self))

    # -- OK / Cancel ------------------------------------------------------------------------
    def accept(self):
        if self._closed:
            return True
        if self.target is None:
            self.message.setText("⚠ Click a cylindrical face to thread first.")
            return False
        self._timer.stop()
        if self.dirty:
            self.dirty = False
            self._apply()
        if self.error:
            self.message.setText("⚠ " + self.error)
            return False
        preview.recompute(self.doc)
        text = plain(preview.failure(self.target))
        if text:
            self.message.setText("⚠ " + text)
            return False
        self._collect()
        ThreadPanel.remembered = {
            k: self.options[k] for k in ("standard", "modeled", "direction", "full_length")
        }
        self.cleanup()
        self.doc.commitTransaction()
        self._close()
        log("%s done" % self.title)
        CosmeticThreads.schedule()
        return True

    def reject(self):
        if self._closed:
            return True
        self._timer.stop()
        self.cleanup()
        self.doc.abortTransaction()
        preview.recompute(self.doc)
        self._close()
        CosmeticThreads.schedule()
        return True

    def cleanup(self):
        self._unwatch()
        self.escape.remove()
        self._remove_draggers()
        self.watch.remove()
        super().cleanup()


class ThreadCommand:
    def GetResources(self):
        return {
            "MenuText": "Thread",
            "ToolTip": "Thread a shaft or a hole: pick its cylindrical face; ISO metric or "
            "Unified sizes, cosmetic or modeled",
            "Pixmap": ui_icon_path("thread"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        try:
            CosmeticThreads.install()
            found = common.picks()  # a face picked before the command
            if not commands.finish_open_dialog():
                return
            Gui.Control.showDialog(ThreadPanel(App.ActiveDocument, selection=found))
            log("thread started")
        except Exception as exc:
            warn("Thread failed to start: %s" % exc)


def edit(feature):
    """Open the Thread dialog on an existing thread (timeline double-click)."""
    try:
        CosmeticThreads.install()
        if Gui.Control.activeDialog() and not commands.finish_open_dialog():
            return
        Gui.Control.showDialog(ThreadPanel(feature.Document, feature=feature))
    except Exception as exc:
        warn("could not edit %s: %s" % (feature.Label, exc))


# -- cosmetic threads ---------------------------------------------------------------------------
COLOR = (0.18, 0.18, 0.22)
PATTERN = 0xF0F0  # dashed


def _active_features(body):
    """Features of the body up to its history marker (rolled-back ones are not shown)."""
    group = list(body.Group)
    tip = body.Tip
    if tip is None or tip not in group:
        return []
    return group[: group.index(tip) + 1]


def _suppressed(obj):
    try:
        from . import timeline_ops

        return timeline_ops.is_suppressed(obj)
    except Exception:
        return bool(getattr(obj, "Suppressed", False))


def cosmetic_spots(doc):
    """Every cosmetic thread to draw in a document: [(placement, radius, pitch, z0, z1, left,
    circles)] with the placement taking the thread's frame (z = axis) to global coordinates
    and `circles` extra dashed circles [(radius, z)]."""
    from . import hole

    found = []
    for body in doc.findObjects("PartDesign::Body"):
        try:
            if body.ViewObject is None or not body.ViewObject.Visibility:
                continue
        except Exception:
            continue
        place = body.getGlobalPlacement()
        for obj in _active_features(body):
            if _suppressed(obj) or preview.failure(obj):
                continue
            if thread.is_thread(obj) and not obj.Modeled:
                record = thread.computed(obj)
                for t in record.get("threads", []):
                    axis = App.Vector(*t["axis"])
                    frame = App.Placement(
                        App.Vector(*t["base"]), App.Rotation(App.Vector(0, 0, 1), axis)
                    )
                    radius = t["radius"]
                    lift = max(0.01, radius * 0.004)
                    r = radius - lift if t["internal"] else radius + lift
                    found.append(
                        (
                            place.multiply(frame),
                            r,
                            record.get("pitch", 1.0),
                            t["z0"],
                            t["z1"],
                            record.get("left", False),
                            [],
                        )
                    )
            elif hole.is_hole(obj):
                for t in hole.cosmetic_threads(obj):
                    frame = App.Placement(
                        t["start"], App.Rotation(App.Vector(0, 0, 1), t["direction"])
                    )
                    lift = max(0.01, t["radius"] * 0.004)
                    found.append(
                        (
                            frame,
                            t["radius"] - lift,
                            t["pitch"],
                            0.0,
                            t["length"],
                            t["left"],
                            [(t["major"], -lift)],  # the major diameter at the hole's mouth
                        )
                    )
    return found


class _CosmeticThreads:
    """Draws every cosmetic thread as a dashed helix (and a tapped hole's major diameter as a
    dashed circle at its mouth). The drawing is SciForge's own Coin nodes, rebuilt shortly
    after any recompute, undo/redo or visibility change; nothing in the document changes."""

    def __init__(self):
        self.nodes = {}  # document name -> our SoSeparator
        self.counts = {}  # document name -> threads drawn
        self.installed = False
        self._timer = None

    def install(self):
        if self.installed:
            return
        try:
            self._watch = _AppWatch()
            App.addDocumentObserver(self._watch)
            self.installed = True
        except Exception as exc:
            log("cosmetic threads unavailable: %s" % exc)

    def schedule(self):
        try:
            if self._timer is None:
                self._timer = QtCore.QTimer()
                self._timer.setSingleShot(True)
                self._timer.setInterval(80)
                self._timer.timeout.connect(self.refresh_all)
            self._timer.start()
        except Exception:
            pass

    def forget(self, name):
        self.nodes.pop(name, None)  # the document's views are gone with it
        self.counts.pop(name, None)

    def count(self, doc_name=None):
        """How many threads are drawn (tests)."""
        return sum(n for name, n in self.counts.items() if doc_name in (None, name))

    def refresh_all(self):
        try:
            names = set(App.listDocuments())
            for name in list(self.nodes):
                if name not in names:
                    self.forget(name)
            for name in names:
                self.refresh(App.getDocument(name))
        except Exception as exc:
            log("cosmetic threads: %s" % exc)

    def _views(self, doc):
        gdoc = Gui.getDocument(doc.Name)
        if gdoc is None:
            return []
        try:
            return list(gdoc.mdiViewsOfType("Gui::View3DInventor"))
        except Exception:
            view = getattr(gdoc, "ActiveView", None)
            return [view] if view is not None else []

    def refresh(self, doc):
        if doc.Recomputing:
            self.schedule()
            return
        views = self._views(doc)
        old = self.nodes.pop(doc.Name, None)
        self.counts.pop(doc.Name, None)
        if old is not None:
            for view in views:
                try:
                    root = view.getSceneGraph()
                    if root.findChild(old) >= 0:
                        root.removeChild(old)
                except Exception:
                    pass
        spots = cosmetic_spots(doc)
        if not spots or not views:
            return
        node = _build(spots)
        for view in views:
            try:
                view.getSceneGraph().addChild(node)
            except Exception:
                pass
        self.nodes[doc.Name] = node
        self.counts[doc.Name] = len(spots)


def _build(spots):
    from pivy import coin

    root = coin.SoSeparator()
    pick = coin.SoPickStyle()
    pick.style = coin.SoPickStyle.UNPICKABLE  # clicks go to the part, not to the drawing
    root.addChild(pick)
    style = coin.SoDrawStyle()
    style.lineWidth = 1.5
    style.linePattern = PATTERN
    root.addChild(style)
    material = coin.SoMaterial()
    material.diffuseColor.setValue(*COLOR)
    material.emissiveColor.setValue(*COLOR)
    root.addChild(material)
    light = coin.SoLightModel()
    light.model = coin.SoLightModel.BASE_COLOR
    root.addChild(light)
    for placement, radius, pitch, z0, z1, left, circles in spots:
        sep = coin.SoSeparator()
        transform = coin.SoTransform()
        transform.translation.setValue(*placement.Base)
        transform.rotation.setValue(*placement.Rotation.Q)
        sep.addChild(transform)
        lines = [core.helix_points(radius, pitch, z0, z1, left_hand=left)]
        for circle_radius, z in circles:
            lines.append(
                [
                    (
                        circle_radius * math.cos(2 * math.pi * i / 48),
                        circle_radius * math.sin(2 * math.pi * i / 48),
                        z,
                    )
                    for i in range(49)
                ]
            )
        points, counts = [], []
        for line in lines:
            if len(line) >= 2:
                points += line
                counts.append(len(line))
        coords = coin.SoCoordinate3()
        coords.point.setValues(0, len(points), points)
        line_set = coin.SoLineSet()
        line_set.numVertices.setValues(0, len(counts), counts)
        sep.addChild(coords)
        sep.addChild(line_set)
        root.addChild(sep)
    return root


CosmeticThreads = _CosmeticThreads()


class _AppWatch:
    def slotRecomputedDocument(self, doc):
        CosmeticThreads.schedule()

    def slotUndoDocument(self, doc):
        CosmeticThreads.schedule()

    def slotRedoDocument(self, doc):
        CosmeticThreads.schedule()

    def slotDeletedDocument(self, doc):
        try:
            CosmeticThreads.forget(doc.Name)
        except Exception:
            pass

    def slotChangedObject(self, obj, prop):
        # App objects only: a Gui observer gets view providers, which crash FreeCAD when
        # read while they are being built. Visibility mirrors the view's eye.
        if prop in ("Tip", "Suppressed", "Visibility"):
            CosmeticThreads.schedule()

    def slotActivateDocument(self, doc):
        CosmeticThreads.schedule()


try:
    CosmeticThreads.install()
except Exception:
    pass

COMMANDS = {"SciForge_Thread": ThreadCommand}
EDITORS = {"SciForge::Thread": edit}
