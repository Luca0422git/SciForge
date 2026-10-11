# SPDX-License-Identifier: LGPL-2.1-or-later
"""Dialog base for INSPECT commands that pick whole bodies (Center of Mass, Interference):
a click on any face, edge or corner of a body picks the body (it lights up whole), a click on
a picked body drops it again, like Fusion's body selection filter. Also draws things over the
part (on_top) for the analyses' view providers.
"""
import FreeCADGui as Gui

from . import analysis, construct, hole_common, pickpanel, warn


class _Gate:
    def __init__(self, panel):
        self.panel = panel

    def allow(self, doc, obj, sub):
        try:
            panel = self.panel
            if panel is None or panel._closed or obj is None:
                return True
            from .construct_ui import _resolve_gate

            leaf, _short = _resolve_gate(obj, sub)
            return bool(panel.allow(leaf, ""))
        except Exception:
            return False


HINT_STYLE = "color: #b8c4d0;"
ERROR_STYLE = "color: #ff8a80;"


class Tones:
    """Dialog messages in two tones: hint() for what to do next (plain), say() for a
    problem (red, like every SciForge dialog's errors)."""

    def hint(self, text):
        self.message.setStyleSheet(HINT_STYLE)
        self.message.setText(text)

    def say(self, text):
        self.message.setStyleSheet(ERROR_STYLE)
        self.message.setText(text)


class BodyPickPanel(Tones, pickpanel.PickPanel):
    """Subclasses call start_picking() and implement bodies_changed()."""

    def __init__(self, doc, transaction):
        super().__init__(doc, transaction)
        self.picked = []

    def start_picking(self):
        super().start_picking()
        try:
            if self.gate is not None:
                hole_common.remove_gate(self.gate)
            self.gate = _Gate(self)
            Gui.Selection.addSelectionGate(self.gate)
        except Exception as exc:
            warn("%s: selection filter unavailable: %s" % (self.title, exc))

    def allow(self, obj, short):
        if obj is None or construct.is_helper(obj):
            return False
        if getattr(obj, "SciForgeType", "").endswith("Analysis"):
            return False
        return analysis.body_of(obj) is not None

    def shown(self):
        return [(b, []) for b in self.picked if construct.alive(b)]

    def picks_changed(self, added, dropped):
        toggled = []
        for obj, _short, _point in list(dropped) + list(added):
            body = analysis.body_of(obj)
            if body is not None and body not in toggled:
                toggled.append(body)
        if not toggled:
            return False
        for body in toggled:
            if body in self.picked:
                self.picked.remove(body)
            else:
                self.picked.append(body)
        self.bodies_changed()
        return True

    def bodies_changed(self):
        pass

    def picked_text(self, empty="Select"):
        if not self.picked:
            return empty
        if len(self.picked) == 1:
            return self.picked[0].Label
        return "%d bodies" % len(self.picked)


def on_top(root):
    """Draw what follows in `root` over the part (seen through it, like Fusion's markers)."""
    try:
        from pivy import coin

        depth = coin.SoDepthBuffer()
        depth.test.setValue(False)
        root.insertChild(depth, 0)
    except Exception:
        pass
