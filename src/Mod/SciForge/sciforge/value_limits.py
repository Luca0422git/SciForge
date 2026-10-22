# SPDX-License-Identifier: LGPL-2.1-or-later
"""A value that goes past what fits stops at the largest value that works (Luca, 2026-10-21).

Fusion refuses a fillet radius, chamfer distance, draft angle, shell thickness... that does not
fit and the dialog waits until a smaller value is typed. Luca: "limit edits to stop at that
limit, so if I want to chamfer something to the max I can quickly drag it". So in SciForge:
  * an arrow dragged past the limit stops there, like the end of a slider; the preview shows
    that result and the dialog says "Largest that fits here: 3.47 mm"; OK works at once;
  * a plain number typed past it is set to the limit, and the dialog says so ("5 mm does not
    fit: limited to 3.47 mm"), so nobody is surprised;
  * a value that comes from a formula ("width / 2") is never rewritten (that would break the
    formula): the dialog keeps its explanation, with the limit in it.
This deliberately differs from Fusion (it shows an error); it is Luca's decision.

The limit is found once, by bisection between a value that works and one that does not (time
budgeted), rounded toward the safe side to a tidy value at the box's precision (3.47 mm,
12.3 deg) and that value is built once more to be sure it works (the bisection can stop right on
the failing edge). It is kept for the inputs it was found for (the part before the step, the
picks, the other options: LimitCache) and every later drag step reuses it, so dragging never
stutters; other inputs find their own limit.

Pure Python (no FreeCAD, no Qt at module level): unit tested in SciForgeTests/unit.
"""

import math
import time
from collections import OrderedDict

BUDGET = 1.5  # seconds the bisection may take (it runs once per set of inputs)
MIN_TRIALS = 3  # ... but at least this many builds, even on a slow part
VERIFY_TRIES = 6  # tidy candidates tried toward the safe side before giving up on tidiness
NOTE_STYLE = "color: #8cc4ff;"  # the note is information, not an error (theme.py swaps it)

# Words of the "this value is too big here" refusals (fillet, chamfer, shell, draft, press pull,
# thicken...). Other refusals (a face that cannot be drafted at any angle, a missing pick) are
# not limits: a smaller value would not help, so they stay errors.
LIMIT_WORDS = (
    "too big",
    "too thick",
    "too steep",
    "too small for this angle",
    "too far",
    "does not fit",
    "smaller",
    "thinner",
    "shorter",
    "never reaches",
    "into pieces",
    "separate pieces",
    "remove the whole",
    "cannot be made",
    "cannot be thickened",
    "cannot be tilted",
    "not a valid solid",
    "leaves no solid",
    "run into each other",
    "could not build",
    "command not done",  # OpenCASCADE's own words when a fillet / chamfer does not fit
    "fold over",
    "too thin",  # the limits on the other side: a value that must not get smaller
    "must be larger",
    "at least",
    "at most",
    "touch each other",
    "close up",
    "shorter than",
    "narrows",
)


def is_limit_error(text):
    """True if a refusal is of the kind a smaller (or less negative) value can cure."""
    low = (text or "").lower()
    return any(word in low for word in LIMIT_WORDS)


# -- precision ------------------------------------------------------------------------------------
def decimals(default=2):
    """The number of decimals FreeCAD's value boxes show (Preferences > General > Units)."""
    try:
        import FreeCAD as App

        value = App.ParamGet("User parameter:BaseApp/Preferences/Units").GetInt("Decimals", default)
        return max(0, min(6, int(value)))
    except Exception:
        return default


def step_for(unit="mm"):
    """The precision a limit is rounded to: the box's shown decimals in mm, 0.1 of a degree
    (the angle handles turn in steps of 0.1 deg)."""
    if unit == "deg":
        return 0.1
    return 10.0 ** -decimals()


def _digits(step):
    return max(0, int(round(-math.log10(step)))) if 0 < step < 1 else 0


def tidy(value, step, toward):
    """`value` rounded to a multiple of `step` on the side of `toward` (the safe side): 3.4789
    toward 0 -> 3.47; -3.4789 toward 0 -> -3.47; 3.4711 toward 9 -> 3.48."""
    if step <= 0:
        return value
    n = value / step
    k = math.floor(n + 1e-7) if toward < value else math.ceil(n - 1e-7)
    return round(k * step, _digits(step) + 2)


def fmt(value, unit="mm", step=None):
    """A value as the dialog shows it in a note: '3.47 mm', '12.3°', '9.99' (unit "": a
    count, the turns of a coil)."""
    step = step or step_for(unit)
    text = "%.*f" % (_digits(step), value)
    if text.startswith("-") and float(text) == 0.0:
        text = text[1:]
    return text + ("°" if unit == "deg" else " mm" if unit == "mm" else "")


def fmt_typed(value, unit="mm"):
    """A typed value as typed: '5 mm', '0.25 mm', '30°'."""
    return "%g" % value + ("°" if unit == "deg" else " mm" if unit == "mm" else "")


def note_reached(limit, side, unit="mm", step=None):
    """The note shown while a dragged value sits at its limit."""
    if side == "hi":
        word = "Largest"
    elif limit > 0:
        word = "Smallest"  # a value that must not get smaller (a pipe's section size)
    else:
        word = "Furthest"  # a push into the part, -30 deg...
    return "%s that fits here: %s" % (word, fmt(limit, unit, step))


def note_typed(typed, limit, unit="mm", step=None):
    """The note shown when a typed value was set to the limit."""
    return "%s does not fit: limited to %s" % (fmt_typed(typed, unit), fmt(limit, unit, step))


def hint(limit, side, unit="mm", step=None):
    """The line added to the error of a formula that does not fit (it is not rewritten)."""
    return note_reached(limit, side, unit, step) + "."


# -- the search -----------------------------------------------------------------------------------
def _safe(works):
    def run(value):
        try:
            return bool(works(value))
        except Exception:
            return False

    return run


def _middle(lo, hi):
    """The next value to try between `lo` (works) and `hi` (does not). Far apart on the same
    side of zero (0.01 and 50): their geometric mean (0.71), so the first builds stay near the
    value that worked and home in on the scale of the limit: a slow part's few trials then
    give a useful limit, and values far past it (a 25 mm shell wall where 3 fits, which
    crashed OpenCASCADE) are rarely built. Close together: the middle."""
    if lo * hi > 0:
        a, b = abs(lo), abs(hi)
        if max(a, b) > 4.0 * min(a, b):
            return math.copysign(math.sqrt(a * b), lo)
    return (lo + hi) / 2.0


def search(
    works, good, bad, step, budget=BUDGET, good_known=False, clock=time.perf_counter, seen=None
):
    """The value nearest `bad` that still works, between `good` (a value that works) and `bad`
    (one that does not): a tidy multiple of `step` on the side of `good`, built once more to be
    sure. Returns (limit, exact) or (None, False) when nothing between them works (then the
    refusal is not a limit). `exact` is False when the time budget stopped the bisection before
    it reached `step` (the limit is then on the safe side of the real one, maybe far from it).
    `seen` (a dict, optional) gets "fails": the value nearest `good` that was built and did
    not work (values between the limit and it were never tried).
    `works(value)` builds the result with that value and says if it is sound; an exception
    counts as "does not work"."""
    works = _safe(works)
    good, bad = float(good), float(bad)
    if seen is not None:
        seen["fails"] = bad
    if good == bad:
        return None, False
    if not good_known and not works(good):
        return None, False
    start = clock()
    lo, hi = good, bad  # lo works, hi does not (lo may be above hi for a lower limit)
    trials = 0
    while abs(hi - lo) > step * 0.5:
        if trials >= MIN_TRIALS and clock() - start > budget:
            break
        if trials > 60:
            break
        mid = _middle(lo, hi)
        trials += 1
        if works(mid):
            lo = mid
        else:
            hi = mid
    if seen is not None:
        seen["fails"] = hi
    exact = abs(hi - lo) <= step * 0.5
    toward = 1.0 if good > bad else -1.0
    digits = _digits(step) + 2
    # The tidy value just short of the refused one, when it lies beyond the last value that
    # worked (the bisection stopped between them): it may work too (2.50 rather than 2.49).
    above = tidy(hi, step, good)
    if abs(above - hi) < 1e-12:
        above = round(above + toward * step, digits)
    if exact and (above - lo) * toward < -1e-12 and works(above):
        return above, exact
    candidate = tidy(lo, step, good)
    for _ in range(VERIFY_TRIES):
        if (candidate - good) * toward > 1e-12:
            break  # walked past `good`: `good` itself is the answer
        if abs(candidate - lo) < 1e-12:
            return candidate, exact  # built already (by the bisection, or `good` itself)
        if works(candidate):
            return candidate, exact
        candidate = round(candidate + toward * step, digits)
    # no tidy value works near the edge (a jumpy kernel): the last value that worked
    return lo, False


# -- the cache ------------------------------------------------------------------------------------
def frozen(value):
    """`value` as something a dict key can hold: lists, dicts, vectors and floats made
    hashable (floats rounded so 1.0000000001 and 1.0 are the same input)."""
    if isinstance(value, float):
        return round(value, 9)
    if isinstance(value, (str, int, bool, type(None))):
        return value
    if isinstance(value, dict):
        return tuple(sorted((str(k), frozen(v)) for k, v in value.items()))
    if isinstance(value, (list, tuple, set, frozenset)):
        items = [frozen(v) for v in value]
        return (
            tuple(sorted(items, key=repr)) if isinstance(value, (set, frozenset)) else tuple(items)
        )
    if all(hasattr(value, a) for a in ("x", "y", "z")):
        try:
            return ("vec", round(value.x, 9), round(value.y, 9), round(value.z, 9))
        except Exception:
            pass
    if hasattr(value, "hashCode") and hasattr(value, "ShapeType"):
        try:
            return ("shape", value.hashCode(), value.ShapeType)
        except Exception:
            pass
    if hasattr(value, "Name") and hasattr(value, "Document"):
        try:
            return ("object", value.Document.Name, value.Name)
        except Exception:
            pass
    return ("id", type(value).__name__, id(value))


def make_key(*parts):
    """The cache key of a set of inputs (any mix of shapes, names, option dicts, numbers)."""
    return tuple(frozen(p) for p in parts)


def side_of(value, good):
    """'hi' for a limit above (the value grew past it), 'lo' for one below."""
    return "hi" if value > good else "lo"


def slot_of(side, value):
    """Where a limit is kept: its side and the side of zero it lies on ("hi+", "lo-"...). A
    limit found for positive values says nothing about negative ones: a coil's height may
    not get too small going down, yet dragged through zero it is a coil the other way."""
    if side[-1:] in "+-" and len(side) == 3:
        return side
    return side + ("+" if value > 0 else "-")


SLOTS = ("hi+", "hi-", "lo+", "lo-")


class LimitCache:
    """The limits found, per set of inputs (make_key). Each entry has an upper ('hi') and a
    lower ('lo') limit on each side of zero: (limit, bad, wall) when found, or (None, bad,
    None) when a search found that no smaller value helps (then it is not searched again for
    these inputs). A value past `wall` is held at `limit` without being built: `wall` is the
    limit itself when the search was exact, else the nearest value that was built and did not
    work (a search cut short by its time budget: the values between the limit and the wall
    were never tried, so they are tried, not refused). A limit holds only values on its own
    side of zero. `keep` holds objects the key names by identity (the base shape), so their
    identity cannot be reused meanwhile."""

    def __init__(self, size=48):
        self.size = size
        self.entries = OrderedDict()

    def clear(self):
        self.entries.clear()

    def get(self, key, slot):
        entry = self.entries.get(key)
        if entry is None:
            return None
        self.entries.move_to_end(key)
        if slot in ("hi", "lo"):  # either side of zero (tests, simple callers)
            return entry.get(slot + "+") or entry.get(slot + "-")
        return entry.get(slot)

    def searched(self, key, slot):
        return self.get(key, slot) is not None

    def store(self, key, side, limit, bad, keep=None, wall=None):
        """Keep `limit` (None: no limit) found when `bad` was refused; `side` is "hi" / "lo"
        (the side of zero is the refused value's) or a slot ("hi+"...); `wall`: values past
        it are held at `limit` (default: the limit itself, an exact limit)."""
        entry = self.entries.setdefault(key, {})
        if limit is not None and wall is None:
            wall = limit
        entry[slot_of(side, bad)] = (limit, bad, wall)
        if keep is not None:
            entry["keep"] = keep
        self.entries.move_to_end(key)
        while len(self.entries) > self.size:
            self.entries.popitem(last=False)

    def limit(self, key, slot):
        found = self.get(key, slot)
        return found[0] if found else None

    def clamp(self, key, value):
        """(value, limit, side): `value` held at a known limit it went past on its own side
        of zero, else unchanged (limit None)."""
        entry = self.entries.get(key)
        if not entry:
            return value, None, None
        for slot in SLOTS:
            found = entry.get(slot)
            if not found or found[0] is None:
                continue
            if (slot[2] == "+" and value <= 0) or (slot[2] == "-" and value >= 0):
                continue  # the other side of zero: this limit says nothing about it
            limit, side, wall = found[0], slot[:2], found[2]
            if (side == "hi" and value > wall + 1e-12) or (side == "lo" and value < wall - 1e-12):
                return limit, limit, side
        return value, None, None

    def on_limit(self, key, value):
        """(limit, side) when `value` sits right on a known limit, else None."""
        entry = self.entries.get(key) or {}
        for slot in SLOTS:
            found = entry.get(slot)
            if found and found[0] is not None and abs(value - found[0]) < 1e-9:
                return found[0], slot[:2]
        return None


class Limiter:
    """What a dialog keeps for its limited values: the cache, the note it shows, and the
    search with the dialog's own build check. One per dialog.

        value, note = limiter.clamp(key, value, typed)      every drag step / typed number
        limit = limiter.find(key, works, value, good)        once, after a value was refused
    """

    def __init__(self, unit="mm", budget=BUDGET):
        self.unit = unit
        self.budget = budget
        self.cache = LimitCache()
        self._note = ""  # what the dialog shows under its boxes (not an error): .note
        self.note_key = None  # the inputs the note was made for (None: any)
        self.key_now = None  # the dialog's inputs now, for the value edited (a function)
        self.searches = 0  # bisections run (tests: never on every drag step)
        self.search_clock = time.perf_counter  # tests give a fake clock

    def step(self, unit=None):
        return step_for(self.unit if unit is None else unit)

    @property
    def note(self):
        """The note, as long as the inputs it was made for have not changed: "80° does not
        fit: limited to 71.5°" is not true any more once Flip is clicked (review finding L5)."""
        if self._note and self.note_key is not None and self.key_now is not None:
            try:
                now = self.key_now()
            except Exception:
                now = None
            if now is not None and now != self.note_key:
                self._note = ""
                self.note_key = None
        return self._note

    @note.setter
    def note(self, text):
        self._note = text or ""
        self.note_key = None

    def _say(self, text, key):
        self._note = text or ""
        self.note_key = key if text else None

    def clamp(self, key, value, typed=False, unit=None):
        """The value to use: held at the cached limit it went past (the note says so), else
        unchanged (and the note is cleared). Never builds anything."""
        unit = self.unit if unit is None else unit
        held, limit, side = self.cache.clamp(key, value)
        if limit is None:
            self.note = ""
            on = self.cache.on_limit(key, value)  # sitting right on it (the arrow let go there)
            if on is not None:
                self._say(note_reached(on[0], on[1], unit, self.step(unit)), key)
            return value
        self._say(
            note_typed(value, limit, unit, self.step(unit))
            if typed
            else note_reached(limit, side, unit, self.step(unit)),
            key,
        )
        return held

    def known(self, key, value):
        """The cached limit `value` went past, or None (nothing is built)."""
        return self.cache.clamp(key, value)[1]

    def find(self, key, works, value, good, good_known=False, unit=None, keep=None):
        """The limit on the side of `value` (refused) for these inputs: from the cache, or
        searched once between `good` and `value`. None when nothing between works (not a
        limit: the refusal stays) - remembered too, so it is not searched again."""
        side = side_of(value, good)
        slot = slot_of(side, value)
        sign = 1 if side == "hi" else -1
        found = self.cache.get(key, slot)
        wall = None
        if found is not None:
            limit, wall = found[0], found[2]
            if limit is None:
                return None
            if (value - wall) * sign > 1e-12:
                return limit
            # a value between the known limit and its wall (never tried, or the first refused
            # value): search that gap
            good, good_known = limit, True
        self.searches += 1
        seen = {}
        limit, exact = search(
            works,
            good,
            value,
            self.step(unit),
            self.budget,
            good_known=good_known,
            clock=self.search_clock,
            seen=seen,
        )
        if limit is not None and (limit - value) * sign >= 0:
            limit = None  # a "limit" beyond the refused value: the value works after all
        if limit is None and found is not None:
            # the gap held nothing better: the known limit stays, `value` is a wall now
            limit, exact, seen["fails"] = found[0], False, value
        new_wall = None
        if limit is not None and not exact:
            # cut short by the time budget: only values past the nearest refused one are held
            # without a build (Limiter.clamp); the ones before it are tried when they come
            new_wall = seen.get("fails", value)
            if wall is not None and (wall - new_wall) * sign < 0:
                new_wall = wall
        self.cache.store(key, slot, limit, value, keep, wall=new_wall)
        return limit

    def limited(self, key, value, limit, typed, unit=None):
        """Set the note for `value` held at `limit` (found just now)."""
        unit = self.unit if unit is None else unit
        side = side_of(value, limit) if value != limit else "hi"
        self._say(
            note_typed(value, limit, unit, self.step(unit))
            if typed
            else note_reached(limit, side, unit, self.step(unit)),
            key,
        )


def note_label():
    """The line under a dialog's message that says a value was held at its limit (blue: it is
    information, not an error; theme.py gives it the light look's blue)."""
    from .compat import QtWidgets

    label = QtWidgets.QLabel("")
    label.setObjectName("SciForgeLimitNote")
    label.setWordWrap(True)
    label.setStyleSheet(NOTE_STYLE)
    label.setVisible(False)
    return label


def show_note(label, text):
    """Show `text` in a note_label() (hidden when there is nothing to say)."""
    try:
        if label is None:
            return
        label.setText(text or "")
        label.setVisible(bool(text))
    except RuntimeError:
        pass  # the dialog went away


class ShowWhenLeft:
    """A number typed in a box and held at a limit while it is being typed: the box keeps
    what is typed (rewriting it under the cursor would be rude) and shows the limit once it
    is left (Enter, Tab, a click elsewhere), unless something else was typed meanwhile.
    For taskui.DistanceField boxes (FreeCAD's number box)."""

    def __init__(self):
        self.pending = {}  # value name -> (the number typed, the limit it was held at)
        self.watched = set()

    def hold(self, key, field, typed, held):
        """Show `held` in `field` once it is left (if it then still holds `typed`)."""
        self.pending[key] = (float(typed), float(held))
        if key in self.watched:
            return
        try:
            field.widget.editingFinished.connect(lambda k=key, f=field: self._left(k, f))
            self.watched.add(key)
        except Exception:
            pass

    def _left(self, key, field):
        try:
            item = self.pending.pop(key, None)
            if item is None or getattr(field, "_typed", None) is not None:
                return
            if abs(float(field.value()) - item[0]) < 1e-9:
                field.set_value(item[1])
        except Exception:
            pass  # the box went with its dialog


def show_held(shower, key, field, typed, held):
    """`held` in `field` now when nothing is being typed in it, else once it is left."""
    if field is None:
        return
    if getattr(field, "_typed", None) is None:
        field.set_value(held)
    elif shower is not None:
        shower.hold(key, field, typed, held)


class LimitedValues:
    """The part of a dialog that holds its values at their limits (a mixin: Shell, Draft,
    Press Pull, Thicken...). The dialog gives:

        limit_key(what)          the inputs the limit of value `what` depends on (make_key)
        limit_works(what)        works(value): that value builds (nothing in the document)
        limit_value(what)        the value now
        limit_set(what, value)   use `value` (options, the box unless a number is being typed
                                 in it, the arrow)
        limit_start(what, value) a value near zero on the side of `value` that should work
        limit_keep()             what the key names by identity (the part before the step)
        limit_unit(what)         "mm" or "deg"

    and calls limit_edit() for every new value (it returns the value to use), limit_good()
    when a preview worked, limit_refused(reason) when it was refused (True: the value was
    held at its limit, preview again) and limit_hint(error) for the error of a formula."""

    def limit_init(self):
        self.limits = Limiter()
        self.limits.key_now = self._limit_key_now  # a note goes when its inputs change
        self.limit_shower = ShowWhenLeft()  # a typed number held: the box shows the limit
        self._limit_edit = None  # (value name, "typed" / "dragged" / "formula")
        self._limit_pending = False
        self._limit_busy = False
        self._limit_good = {}  # value name -> (key, value whose preview worked)

    def limit_unit(self, what):
        return "mm"

    def _limit_key_now(self):
        """The inputs now for the value edited last (None: nothing edited)."""
        if self._limit_edit is None:
            return None
        return self.limit_key(self._limit_edit[0])

    def limit_forget(self):
        """A value that has no limit was edited (a count of teeth): nothing is held, and a
        refusal now is not about the value edited before."""
        self._limit_edit = None
        self._limit_pending = False
        self.limits.note = ""

    def limit_keep(self):
        return None

    def limit_start(self, what, value):
        step = step_for(self.limit_unit(what))
        return step if value > 0 else -step

    def limit_edit(self, what, value, source):
        """A new value (`source`: "typed", "dragged" or "formula"): held at a limit known for
        these inputs (never a formula's). Builds nothing."""
        self._limit_edit = (what, source)
        self._limit_pending = True
        if source == "formula":
            self.limits.note = ""
            return value
        try:
            return self.limits.clamp(
                self.limit_key(what), value, source == "typed", self.limit_unit(what)
            )
        except Exception:
            return value

    def limit_held(self, what, value):
        """`value` held at the limit known for these inputs (no note, nothing built): what a
        number being typed in a box stands for until the box is left."""
        try:
            return self.limits.cache.clamp(self.limit_key(what), value)[0]
        except Exception:
            return value

    def limit_good(self):
        """The preview worked: its value is a known good one for these inputs."""
        self._limit_pending = False
        if self._limit_edit is None:
            return
        what = self._limit_edit[0]
        try:
            self._limit_good[what] = (self.limit_key(what), float(self.limit_value(what)))
        except Exception:
            pass

    def _limit_from(self, what, key, value):
        """(good, known): the value whose preview worked last with these inputs when it is
        on the same side of zero (a search across zero would stop at 0, which many tools
        refuse), else limit_start()'s value (to be built first)."""
        found = self._limit_good.get(what)
        if found is not None and found[0] == key:
            good = found[1]
            if good * value > 0 and abs(good - value) > 1e-12:
                return good, True
        return self.limit_start(what, value), False

    def limit_search(self, what, value):
        """The limit on the side of `value` for the inputs now (cached; searched once)."""
        key = self.limit_key(what)
        good, known = self._limit_from(what, key, value)
        if good is None or abs(good - value) <= 1e-12:
            return None
        return self.limits.find(
            key,
            self.limit_works(what),
            value,
            good,
            good_known=known,
            unit=self.limit_unit(what),
            keep=self.limit_keep(),
        )

    def limit_refused(self, reason):
        """The value just dragged or typed was refused as too big: find the limit (once for
        these inputs) and use it. True when the dialog should preview again."""
        if self._limit_busy or not self._limit_pending or self._limit_edit is None:
            return False
        what, source = self._limit_edit
        if source == "formula" or not is_limit_error(reason):
            return False
        self._limit_busy = True
        try:
            value = float(self.limit_value(what))
            limit = self.limit_search(what, value)
            if limit is None:
                return False
            self._limit_pending = False
            self.limits.limited(
                self.limit_key(what), value, limit, source == "typed", self.limit_unit(what)
            )
            self.limit_set(what, limit)
            return True
        except Exception:
            return False
        finally:
            self._limit_busy = False

    def limit_hint(self, error):
        """`error` with the limit added, for a value that is not held at it (a formula, or a
        value that stopped fitting because the picks changed)."""
        if self._limit_busy or self._limit_edit is None or not is_limit_error(error):
            return error
        what = self._limit_edit[0]
        self._limit_busy = True
        try:
            value = float(self.limit_value(what))
            limit = self.limit_search(what, value)
            if limit is None:
                return error
            side = "hi" if value > limit else "lo"
            return "%s\n%s" % (error, hint(limit, side, self.limit_unit(what)))
        except Exception:
            return error
        finally:
            self._limit_busy = False
