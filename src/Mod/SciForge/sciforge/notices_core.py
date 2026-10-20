# SPDX-License-Identifier: LGPL-2.1-or-later
"""The rules of the slim lines at the top of Home, without FreeCAD and without Qt (unit
tested: SciForgeTests/unit/test_notices_core.py). home_notices_ui.py draws them.

  * "SciForge closed unexpectedly last time. [Report it] [Dismiss]" (crashlog.py knows
    whether the last session ended without a clean exit);
  * the welcome line, the first time SciForge starts only: "Welcome to SciForge 0.1.0-beta. It
    works like Fusion: the ribbon, the timeline, S for search. This is a beta: save often.
    [Cheat sheet] [Open an example] [Report a problem] [x]". No tour, no popup (Luca: "the
    whole point of sciforge is that its supposed to feel like fusion ... dont overdo it").
"""

import os

CRASH_TEXT = "SciForge closed unexpectedly last time."
WELCOME_FLAG = "WelcomeShown"  # the preference (SciForge's parameter group)

CHEAT_SHEET_URL = (
    "https://github.com/Luca0422git/SciForge/blob/develop/docs/sciforge/cheat-sheet.md"
)

# Where the module keeps its copies (src/Mod/SciForge/docs and /examples: the docs/ folder of
# the repository is not part of an installed SciForge)
CHEAT_SHEET_FILE = os.path.join("docs", "cheat-sheet.md")
EXAMPLE_FILE = os.path.join("examples", "pi5-case", "pi5_case.FCStd")
EXAMPLE_NAME = "Raspberry Pi 5 case (example).FCStd"


def welcome_text(version):
    return (
        "Welcome to SciForge %s. It works like Fusion: the ribbon, the timeline, S for "
        "search. This is a beta: save often." % version
    )


def module_file(module_root, relative):
    """The path of a file the module ships, or "" when it is not there."""
    path = os.path.join(module_root, relative)
    return path if os.path.isfile(path) else ""


class Welcome:
    """Whether the welcome line is shown. The first time it is looked at on a computer that
    has never shown it, it is shown (and the flag is set at once, so the next start does not
    show it again, whatever happens in between); the x hides it for good. Within that first
    session it stays up (Home can be closed and opened again) until the x."""

    def __init__(self, get_flag, set_flag):
        self._get, self._set = get_flag, set_flag
        self._showing = None  # None: not asked yet in this session
        self.closed = False

    def visible(self):
        if self.closed:
            return False
        if self._showing is None:
            try:
                self._showing = not self._get()
            except Exception:
                self._showing = False  # when in doubt, no line
            if self._showing:
                try:
                    self._set(True)
                except Exception:
                    pass
        return bool(self._showing)

    def close(self):
        """The x."""
        self.closed = True
        try:
            self._set(True)
        except Exception:
            pass

    def reset(self):
        """A new session (tests: "the next start")."""
        self._showing = None
        self.closed = False


def example_copy_target(user_data):
    """Where the example is copied to before it is opened: the installed copy may sit in a
    folder that cannot be written (Program Files), and a design is saved with Ctrl+S."""
    return os.path.join(user_data, "SciForge", "examples", EXAMPLE_NAME)
