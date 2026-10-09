"""Resolve logical command slots to commands that really exist."""

# Slots that could not be resolved this session (shown in Diagnostics).
MISSING = []


def available_commands():
    import FreeCADGui as Gui

    try:
        return set(Gui.listCommands())
    except Exception:
        return set()


def alternatives(entry):
    return (entry,) if isinstance(entry, str) else tuple(entry)


def resolve(entry, available):
    for name in alternatives(entry):
        if name in available:
            return name
    return None


def resolve_many(entries, available):
    """Return (found_names, missing_labels) for a list of slots."""
    found, missing = [], []
    for entry in entries:
        name = resolve(entry, available)
        if name:
            found.append(name)
        else:
            missing.append("/".join(alternatives(entry)))
    return found, missing
