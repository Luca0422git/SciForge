# SPDX-License-Identifier: LGPL-2.1-or-later
"""Builds a golden model's steps in a real FreeCAD document (needs FreeCAD).

The steps are built by SciForge's own design-step code, sciforge/ai/ops/ (core.py and the
*_ops.py files beside it): the same code the AI tools run, so the golden models prove what
the AI builds. This file only adds what a test needs on top: the checks (checks.py) and
two test setups, reopen and age.
"""

import FreeCAD as App

from sciforge.ai.ops import core
from sciforge.ai.ops.core import BuildError


class Builder(core.Builder):
    """SciForge's design-step builder plus the golden models' checks."""

    def op_reopen(self, step):
        """Save the design, close it and open the file again (what was only in memory is
        gone; what the steps keep in the file must do)."""
        import os
        import tempfile

        names = {key: obj.Name for key, obj in self.objects.items()}
        body = self.body.Name
        folder = tempfile.mkdtemp(prefix="sciforge_golden_")
        path = os.path.join(folder, self.doc.Name + ".FCStd")
        self.doc.saveAs(path)
        App.closeDocument(self.doc.Name)
        self.doc = App.openDocument(path)
        self.doc.recompute()
        self.body = self.doc.getObject(body)
        self.objects = {key: self.doc.getObject(name) for key, name in names.items()}
        from sciforge import upgrade

        # What the GUI does once a file is open: steps of an older SciForge are rebuilt.
        for new in upgrade.after_open(self.doc):
            for key, name in names.items():
                if self.doc.getObject(name) is None and new.Label == key:
                    self.objects[key] = new  # rebuilt as another object (same label)
        try:
            os.remove(path)
            os.rmdir(folder)
        except OSError:
            pass

    def op_age(self, step):
        """Test setup: make a coil or pipe look as saved by SciForge before the primitives QA
        fixes of 2026-10-11 (its old shape, its section without what the fixes added)."""
        from sciforge import coil, pipe, primitives

        feature = self.objects[step["target"]]
        if coil.is_coil(feature):
            _ref, options = coil.read(feature)
            meta = primitives.load_meta(feature, coil.META)
            section = self.doc.getObject(meta["helpers"][-1])
            section.Taper = 0.0  # no narrowing at the far end: the old section
            _turns, height, _pitch = coil.resolved(options)
            feature.Angle = float(options["angle"])  # the old helix: a negative angle as is
            feature.Reversed = height < 0
            section.touch()
            self.doc.recompute()
            section.removeProperty("Taper")  # what the fixes added
        elif pipe.is_pipe(feature):
            meta = primitives.load_meta(feature, pipe.META)
            helpers = [self.doc.getObject(n) for n in meta["helpers"]]
            spine = [h for h in helpers if h is not None and h.Name.startswith("PipePath")][0]
            section = [h for h in helpers if h is not None and h is not spine][0]
            section.Path = spine  # the old link to the path object, no edges of its own
            section.Edges = []
            self.doc.recompute()
        else:
            raise BuildError("age %r: only a coil or a pipe" % step["target"])


from . import checks  # noqa: E402,F401  (registers the *_expect checks on Builder)
