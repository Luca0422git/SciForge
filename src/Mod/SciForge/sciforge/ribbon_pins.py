# SPDX-License-Identifier: LGPL-2.1-or-later
"""Commands pinned to the ribbon (Fusion's "Pin to Toolbar"): a pinned command gets a big
icon in its group's always-visible row, after the group's own icons.

Fusion (Autodesk forum, "Can't Pin to Toolbar"; "losing tools on tool bar", Autodesk staff):
hover a command in a panel's drop-down, its three-dot menu has Pin to Toolbar (and Unpin);
right-click the toolbar: Reset All Toolbar Customization (Fusion asks nothing; its users
asked for a confirmation, SciForge asks).

Stored per tab and group ("solid/modify": ["Coil", ...]) as JSON in the parameter
Mod/SciForge/Ribbon/Pinned. The pure functions below take and return that dict (unit
tested); load() / save() talk to FreeCAD.
"""

import json

PARAMS = "User parameter:BaseApp/Preferences/Mod/SciForge/Ribbon"
KEY = "Pinned"


def slot(tab_id, group_id):
    return "%s/%s" % (tab_id, group_id)


def pinned(store, tab_id, group_id):
    return list((store or {}).get(slot(tab_id, group_id), []))


def is_pinned(store, tab_id, group_id, label):
    return label in pinned(store, tab_id, group_id)


def pin(store, tab_id, group_id, label, built_in=()):
    """New store with `label` pinned at the end of the group's row (nothing changes for a
    command that is already a big icon of the group, or already pinned)."""
    result = {k: list(v) for k, v in (store or {}).items()}
    if label in built_in:
        return result
    row = result.setdefault(slot(tab_id, group_id), [])
    if label not in row:
        row.append(label)
    return result


def unpin(store, tab_id, group_id, label):
    result = {k: list(v) for k, v in (store or {}).items()}
    key = slot(tab_id, group_id)
    row = [x for x in result.get(key, []) if x != label]
    if row:
        result[key] = row
    else:
        result.pop(key, None)
    return result


def load():
    try:
        import FreeCAD as App

        text = App.ParamGet(PARAMS).GetString(KEY, "")
        data = json.loads(text) if text else {}
        return {str(k): [str(x) for x in v] for k, v in data.items() if isinstance(v, list)}
    except Exception:
        return {}


def save(store):
    import FreeCAD as App

    App.ParamGet(PARAMS).SetString(KEY, json.dumps(store or {}, sort_keys=True))
