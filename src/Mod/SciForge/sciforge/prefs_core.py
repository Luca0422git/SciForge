# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's Preferences window as data: its pages, the options SciForge honours, where each one
is kept (FreeCAD's own parameters or SciForge's), and the defaults Restore Defaults puts back.
No FreeCAD, no Qt: unit tested (SciForgeTests/unit/test_misc_cores.py). preferences_ui.py is
the window and applies the values.

Options SciForge cannot honour yet are listed too, greyed with the reason (like the greyed
ribbon entries): Fusion's window shows them, and a person looking for one learns why it does
nothing here. Sources: docs/sciforge/parity/misc.md.
"""

PREFS = "User parameter:BaseApp/Preferences/Mod/SciForge/Preferences"
SCIFORGE = "User parameter:BaseApp/Preferences/Mod/SciForge"
FILES = "User parameter:BaseApp/Preferences/Mod/SciForge/Files"
VIEW = "User parameter:BaseApp/Preferences/View"
UNITS = "User parameter:BaseApp/Preferences/Units"
GENERAL = "User parameter:BaseApp/Preferences/General"
MACRO = "User parameter:BaseApp/Preferences/Macro"
ADDONS = "User parameter:BaseApp/Preferences/Addons"
INFERENCE = "User parameter:BaseApp/Preferences/Mod/SciForge/SketchInference"

# (id, title, parent page id or None), in the order of Fusion's list on the left.
PAGES = [
    ("general", "General", None),
    ("design", "Design", "general"),
    ("api", "API", "general"),
    ("material", "Material", None),
    ("graphics", "Graphics", None),
    ("units", "Unit and Value Display", None),
    ("default_units", "Default Units", None),
    ("default_units_design", "Design", "default_units"),
    ("network", "Network", None),
    # SciForge's own: every command's keyboard shortcut in one list (Fusion only changes them
    # one at a time from a command's three-dot menu; its users keep asking for a list)
    ("keyboard", "Keyboard Shortcuts", None),
    # SciForge's own: AI apps (Claude Desktop, Gemini CLI...) building in SciForge (brief
    # home-cloud-ai.md M3); off unless switched on
    ("ai", "AI", None),
]

# Fusion's Pan, Zoom, Orbit Shortcuts presets: (value, label, FreeCAD navigation style or None
# when SciForge cannot give it, why not).
MOUSE_PRESETS = [
    ("fusion", "Fusion", "Gui::RevitNavigationStyle", ""),
    ("solidworks", "SolidWorks", "Gui::SolidWorksNavigationStyle", ""),
    (
        "inventor",
        "Inventor",
        None,
        "Inventor's F2 / F3 / F4 with the left button are not built in SciForge yet.",
    ),
    (
        "tinkercad",
        "Tinkercad",
        None,
        "Tinkercad orbits with the right button, which opens SciForge's marking menu.",
    ),
    ("alias", "Alias", None, "Alias's Shift + Alt + mouse buttons are not built yet."),
    ("powermill", "PowerMill", None, "PowerMill's orbit is not built yet."),
]
DEFAULT_MOUSE = "fusion"

# Fusion's design units -> FreeCAD's unit schema (browser_core.UNITS has the same numbers).
UNIT_SCHEMAS = [
    ("mm", "Millimeter", 0),
    ("cm", "Centimeter", 4),
    ("m", "Meter", 9),
    ("in", "Inch", 3),
    ("ft", "Foot", 7),
]

ANTI_ALIASING = [
    (0, "None"),
    (2, "2x"),
    (3, "4x"),
    (5, "6x"),
    (4, "8x"),
]


def _option(
    key,
    page,
    label,
    kind,
    default,
    store,
    group="",
    choices=None,
    tip="",
    available=True,
    why="",
    restart=False,
    minimum=None,
    maximum=None,
    suffix="",
    apply="",
):
    """One row of a page. kind: "choice" | "bool" | "int" | "text" | "folder" | "file".
    store: (parameter group, "Bool" | "Int" | "String", name) or None for a greyed row.
    choices: [(value, label, available, why)]. default None: Restore Defaults removes the
    parameter (FreeCAD's own default applies). apply: what preferences_ui runs after a
    change (mouse, zoom, orbit, recovery, ...)."""
    return {
        "key": key,
        "page": page,
        "label": label,
        "kind": kind,
        "default": default,
        "store": store,
        "group": group,
        "choices": [tuple(c) + ("",) * (4 - len(c)) for c in (choices or [])],
        "tip": tip,
        "available": bool(available),
        "why": why,
        "restart": bool(restart),
        "minimum": minimum,
        "maximum": maximum,
        "suffix": suffix,
        "apply": apply,
    }


OPTIONS = [
    # -- General ----------------------------------------------------------------------------
    _option(
        "language",
        "general",
        "User Language",
        "choice",
        None,
        (GENERAL, "String", "Language"),
        group="Language",
        tip="The language of FreeCAD's own windows; SciForge's own words stay English.",
        restart=True,
    ),
    _option(
        "start_in_sciforge",
        "general",
        "Start in SciForge",
        "bool",
        True,
        (SCIFORGE, "Bool", "StartInSciForge"),
        group="Startup",
        tip="On: the program opens straight in SciForge, without FreeCAD's Start page, from "
        "the next start. Off: FreeCAD's own start workbench and Start page as before.",
        apply="startup",
    ),
    _option(
        "show_home",
        "general",
        "Show Home at start",
        "bool",
        True,
        (SCIFORGE, "Bool", "ShowHomeAtStart"),
        group="Startup",
        tip="On: SciForge opens on its Home tab (your recent designs, New design, Open), and "
        "closing the last design comes back to it. Off: an empty window, as before.",
    ),
    _option(
        "theme",
        "general",
        "Look",
        "choice",
        "dark",
        (SCIFORGE, "String", "Theme"),
        group="Appearance",
        choices=[
            ("dark", "Dark (SciForge's own)", True, ""),
            ("light", "Light (white, like Fusion's default)", True, ""),
        ],
        tip="SciForge's colours. Dark: SciForge's own look. Light: the white look of Fusion's "
        "default. The window changes at once; a few icons of FreeCAD's own menus change at "
        "the next start.",
        apply="theme",
    ),
    _option(
        "mouse_preset",
        "general",
        "Pan, Zoom, Orbit Shortcuts",
        "choice",
        DEFAULT_MOUSE,
        (PREFS, "String", "MousePreset"),
        group="Navigation",
        choices=[(v, label, style is not None, why) for v, label, style, why in MOUSE_PRESETS],
        tip="Fusion: middle button pans, Shift + middle orbits, the wheel zooms. SolidWorks: "
        "middle button orbits, Ctrl + middle pans.",
        apply="mouse",
    ),
    _option(
        "reverse_zoom",
        "general",
        "Reverse zoom direction",
        "bool",
        False,
        (PREFS, "Bool", "ReverseZoom"),
        group="Navigation",
        tip="Off: rolling the wheel away from you zooms in. On: it zooms out.",
        apply="zoom",
    ),
    _option(
        "orbit_type",
        "general",
        "Default Orbit type",
        "choice",
        "constrained",
        (SCIFORGE, "String", "OrbitMode"),
        group="Navigation",
        choices=[
            ("constrained", "Constrained Orbit", True, ""),
            ("free", "Free Orbit", True, ""),
        ],
        tip="Constrained turns about the up axis and never rolls; Free tumbles.",
        apply="orbit",
    ),
    _option(
        "recovery_minutes",
        "general",
        "Recovery save time interval",
        "int",
        5,
        (FILES, "Int", "AutosaveMinutes"),
        group="Saving and Recovery",
        minimum=1,
        maximum=120,
        suffix=" min",
        tip="How often a recovery copy of every changed design is written.",
        apply="recovery",
    ),
    _option(
        "version_on_close",
        "general",
        "Automatic version on close",
        "bool",
        True,
        (FILES, "Bool", "VersionOnClose"),
        group="Saving and Recovery",
        tip="On (Fusion's default): closing a saved design with changes saves them as a new "
        "version. Off: closing it asks whether to save a version first.",
    ),
    _option(
        "ask_description",
        "general",
        "Ask for a version description on every save",
        "bool",
        True,
        (FILES, "Bool", "AskDescription"),
        group="Saving and Recovery",
        tip="Fusion always asks; Enter saves without a description.",
    ),
    _option(
        "project_folder",
        "general",
        "Project folder",
        "folder",
        None,
        (FILES, "String", "ProjectFolder"),
        group="Saving and Recovery",
        tip="The folder the Data Panel shows (Fusion's project; your NAS folder).",
        apply="project",
    ),
    _option(
        "use_git",
        "general",
        "Keep versions with git in the project folder",
        "bool",
        True,
        (FILES, "Bool", "UseGit"),
        group="Saving and Recovery",
    ),
    # -- General > Design -------------------------------------------------------------------
    _option(
        "capture_history",
        "design",
        "Capture design history",
        "bool",
        True,
        (PREFS, "Bool", "CaptureHistory"),
        group="Design History",
        tip="New designs record a timeline (parametric). Off: new designs start without "
        "history (direct modeling); a design's own setting is in its browser menu.",
    ),
    _option(
        "orientation",
        "design",
        "Default modeling orientation",
        "choice",
        "z",
        (PREFS, "String", "ModelingOrientation"),
        group="General",
        choices=[
            ("z", "Z up", True, ""),
            ("y", "Y up", False, "SciForge's views, ViewCube and sketches are made for Z up."),
        ],
    ),
    _option(
        "active_component_visibility",
        "design",
        "Active component visibility",
        "bool",
        True,
        (PREFS, "Bool", "ActiveComponentVisibility"),
        group="General",
        tip="While a component is active, everything outside it is drawn see-through (it can "
        "still be picked). Off: everything stays as it is.",
        apply="components",
    ),
    _option(
        "sketch_guides",
        "design",
        "Show inference guides while sketching",
        "bool",
        True,
        (INFERENCE, "Bool", "Enabled"),
        group="Sketch",
        tip="Dashed guides from the points you hover, level / upright / perpendicular snaps.",
    ),
    _option(
        "sketch_guide_constraints",
        "design",
        "Add a constraint when a point is placed on a guide",
        "bool",
        True,
        (INFERENCE, "Bool", "GuideConstraint"),
        group="Sketch",
    ),
    _option(
        "sketch_auto_project",
        "design",
        "Auto project the face's edges when sketching on a face",
        "bool",
        True,
        (INFERENCE, "Bool", "AutoProject"),
        group="Sketch",
        tip="A new sketch on a flat face of the part gets the face's edges as projected "
        "(purple) curves, so the shapes you draw against them make profiles.",
    ),
    # -- General > API ----------------------------------------------------------------------
    _option(
        "scripts_folder",
        "api",
        "Scripts folder",
        "folder",
        None,
        (MACRO, "String", "MacroPath"),
        group="Scripts and Add-Ins",
        tip="Where Scripts and Add-Ins finds and creates your scripts (FreeCAD's macros).",
    ),
    _option(
        "addins_folder",
        "api",
        "Add-ins folder",
        "folder",
        None,
        (PREFS, "String", "AddInsFolder"),
        group="Scripts and Add-Ins",
        tip="Where Scripts and Add-Ins finds and creates add-ins (one folder each).",
    ),
    _option(
        "script_editor",
        "api",
        "Editor for Edit",
        "file",
        None,
        (PREFS, "String", "ScriptEditor"),
        group="Scripts and Add-Ins",
        tip="A program (VS Code, Notepad++...) that Edit opens scripts with; empty: FreeCAD's "
        "own editor.",
    ),
    # -- Material ---------------------------------------------------------------------------
    _option(
        "default_material",
        "material",
        "Default physical material",
        "choice",
        "steel",
        (PREFS, "String", "DefaultMaterial"),
        group="Design",
        tip="What a body counts as (its mass) until it is given a Physical Material.",
    ),
    _option(
        "default_appearance",
        "material",
        "Default appearance",
        "choice",
        "",
        None,
        group="Design",
        available=False,
        why="A body shows its material's look; a default look of its own is not built yet.",
    ),
    # -- Graphics ---------------------------------------------------------------------------
    _option(
        "graphics_driver",
        "graphics",
        "Graphics driver",
        "choice",
        "opengl",
        None,
        group="Display",
        choices=[("opengl", "OpenGL", True, "")],
        available=False,
        why="SciForge always draws with OpenGL.",
    ),
    _option(
        "anti_aliasing",
        "graphics",
        "Anti-aliasing",
        "choice",
        None,
        (VIEW, "Int", "AntiAliasing"),
        group="Display",
        choices=[(v, label, True, "") for v, label in ANTI_ALIASING],
        tip="Smoother edges; used by 3D views opened after the change.",
        restart=True,
    ),
    _option(
        "transparency",
        "graphics",
        "Transparency effects",
        "choice",
        None,
        (VIEW, "Int", "TransparentObjectRenderType"),
        group="Display",
        choices=[(0, "Better performance", True, ""), (1, "Better display", True, "")],
    ),
    _option(
        "show_fps",
        "graphics",
        "Show frame rate",
        "bool",
        None,
        (VIEW, "Bool", "ShowFPS"),
        group="Diagnostics",
    ),
    # -- Unit and Value Display -------------------------------------------------------------
    _option(
        "decimals",
        "units",
        "General precision",
        "int",
        None,
        (UNITS, "Int", "Decimals"),
        group="Precision",
        minimum=0,
        maximum=8,
        suffix=" decimals",
        tip="Decimal places shown in value boxes and measurements.",
        restart=True,
    ),
    _option(
        "angular_precision",
        "units",
        "Angular precision",
        "int",
        2,
        None,
        group="Precision",
        available=False,
        why="Angles are shown with the general precision.",
    ),
    # -- Default Units > Design -------------------------------------------------------------
    _option(
        "default_units",
        "default_units_design",
        "Default units for new designs",
        "choice",
        None,
        (UNITS, "Int", "UserSchema"),
        group="Design",
        choices=[(schema, label, True, "") for _short, label, schema in UNIT_SCHEMAS],
        tip="A design's own units: Document Settings > Units in its browser.",
    ),
    # -- Network ----------------------------------------------------------------------------
    _option(
        "proxy",
        "network",
        "Proxy",
        "choice",
        "system",
        (ADDONS, "String", "proxy_type"),
        group="Proxy settings",
        choices=[
            ("system", "Use the system's proxy settings", True, ""),
            ("none", "No proxy", True, ""),
            ("custom", "Use this proxy", True, ""),
        ],
        tip="SciForge itself never goes online; only the Add-on Manager (Scripts and Add-Ins "
        "> Get Add-Ons) does.",
        apply="proxy",
    ),
    _option(
        "proxy_host",
        "network",
        "Proxy host",
        "text",
        "",
        (ADDONS, "String", "proxy_host"),
        group="Proxy settings",
        apply="proxy",
    ),
    _option(
        "proxy_port",
        "network",
        "Proxy port",
        "int",
        8080,
        (ADDONS, "Int", "proxy_port"),
        group="Proxy settings",
        minimum=1,
        maximum=65535,
        apply="proxy",
    ),
    # -- AI (M3) -------------------------------------------------------------------------------
    _option(
        "allow_ai",
        "ai",
        "Allow AI apps to control SciForge",
        "bool",
        False,
        ("User parameter:BaseApp/Preferences/Mod/SciForge/AI", "Bool", "AllowControl"),
        group="AI apps",
        tip="On: an AI app set up with File > Add an AI App can build, change and save "
        "designs; SciForge asks you the first time in each session, and every step is one "
        "Undo. Off: nothing reaches SciForge.",
        apply="ai",
    ),
]

# Fusion options that are not listed at all (out of SciForge's scope), with why: the parity
# doc lists them too.
LEFT_OUT = [
    ("General > Default workspace", "SciForge has the Design workspace only."),
    ("Data Collection and Use", "SciForge collects nothing (no telemetry, no account)."),
    ("Preview Features", "No preview features to switch on."),
    ("Render, Manufacture, Simulation, Electronics pages", "Out of scope (outline section 8)."),
    ("Offline cache, account, cloud data", "Everything is local (outline 0.6)."),
]


class PrefError(ValueError):
    pass


def pages():
    return list(PAGES)


def page_title(page_id):
    for pid, title, parent in PAGES:
        if pid == page_id:
            return title
    raise PrefError("Unknown page %r" % page_id)


def options(page=None):
    return [o for o in OPTIONS if page is None or o["page"] == page]


def option(key):
    for opt in OPTIONS:
        if opt["key"] == key:
            return opt
    raise PrefError("Unknown option %r" % key)


def groups(page):
    """[(group title, [options])] of a page, in order."""
    found = []
    for opt in options(page):
        if found and found[-1][0] == opt["group"]:
            found[-1][1].append(opt)
        else:
            found.append((opt["group"], [opt]))
    return found


def choice_values(opt, available_only=False):
    return [c[0] for c in opt["choices"] if c[2] or not available_only]


def normalise(opt, value):
    """A value the option can hold: ints clamped, choices checked; PrefError otherwise."""
    if isinstance(opt, str):
        opt = option(opt)
    kind = opt["kind"]
    if value is None:
        return None
    if kind == "bool":
        return bool(value)
    if kind == "int":
        try:
            number = int(round(float(value)))
        except (TypeError, ValueError):
            raise PrefError("%s needs a whole number." % opt["label"]) from None
        if opt["minimum"] is not None:
            number = max(opt["minimum"], number)
        if opt["maximum"] is not None:
            number = min(opt["maximum"], number)
        return number
    if kind == "choice":
        if opt["choices"]:
            allowed = [c for c in opt["choices"] if c[0] == value]
            if not allowed:
                raise PrefError("%s: %r is not one of its choices." % (opt["label"], value))
            if not allowed[0][2]:
                raise PrefError(allowed[0][3] or "%s is not available." % allowed[0][1])
        return value
    return str(value).strip()


def mouse_style(preset):
    """FreeCAD's navigation style for a Pan, Zoom, Orbit preset (Fusion's when unknown)."""
    for value, _label, style, _why in MOUSE_PRESETS:
        if value == preset and style:
            return style
    return MOUSE_PRESETS[0][2]


def invert_zoom(reverse):
    """FreeCAD's InvertZoom for Fusion's Reverse zoom direction (FreeCAD's default, True,
    zooms in when the wheel rolls away from you, as SciForge does by default)."""
    return not bool(reverse)


def unit_label(schema):
    for short, label, number in UNIT_SCHEMAS:
        if number == schema:
            return label
    return None


def writes(opt, value):
    """[(group path, kind, name, value or None = remove)] that store `value` for `opt`."""
    if isinstance(opt, str):
        opt = option(opt)
    store = opt["store"]
    if store is None:
        return []
    path, kind, name = store
    out = [(path, kind, name, normalise(opt, value))]
    if opt["key"] == "proxy":
        # FreeCAD's Add-on Manager moves its old proxy settings over once; marked done so it
        # never overwrites the choice made here.
        out.append((ADDONS, "Bool", "proxy_settings_migrated_2025", True))
    return out


def restore_plan():
    """[(key, default)] Restore Defaults sets, for every option that SciForge keeps."""
    return [(o["key"], o["default"]) for o in OPTIONS if o["store"] is not None]


def changed(before, after):
    """Keys whose value differs between two {key: value} snapshots."""
    return [k for k in after if before.get(k) != after.get(k)]
