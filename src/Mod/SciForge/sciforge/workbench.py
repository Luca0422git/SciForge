"""Builds the SciForge workbench: toolbars, menus, and activation behaviour."""

from . import commands, config, log, registry, warn


def _import_sibling_workbench_commands():
    # Commands of other workbenches only exist after their GUI module loads.
    for module in ("PartGui", "PartDesignGui", "SketcherGui"):
        try:
            __import__(module)
        except Exception as exc:
            warn("could not load %s: %s" % (module, exc))


def build(wb):
    _import_sibling_workbench_commands()
    commands.register_all()

    available = registry.available_commands()
    groups = commands.resolve_groups(available)
    if config.USE_DROPDOWNS:
        commands.register_groups(groups)
        available = registry.available_commands()

    for title, items in config.TOOLBARS:
        names = []
        for item in items:
            if isinstance(item, str) and item in config.GROUPS:
                if config.USE_DROPDOWNS:
                    if groups.get(item):
                        names.append(item)
                else:
                    names.extend(groups.get(item, []))
                continue
            resolved = registry.resolve(item, available)
            if resolved:
                names.append(resolved)
            else:
                registry.MISSING.extend(registry.alternatives(item)[:1])
        if names:
            wb.appendToolbar(title, names)

    forge_menu, _ = registry.resolve_many(config.FORGE_MENU, available)
    wb.appendMenu("SciForge", forge_menu)
    for group_id, found in groups.items():
        if found:
            wb.appendMenu(["SciForge", config.GROUPS[group_id]["title"]], found)

    log(
        "workbench built (%d missing commands, see SciForge > Diagnostics)"
        % len(set(registry.MISSING))
    )


def activated():
    from . import shortcuts, timeline_ui

    shortcuts.apply()
    timeline_ui.show()


def deactivated():
    from . import shortcuts, timeline_ui

    shortcuts.restore()
    timeline_ui.hide()
