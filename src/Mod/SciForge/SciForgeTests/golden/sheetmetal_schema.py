# SPDX-License-Identifier: LGPL-2.1-or-later
"""Golden-model checks for the SHEET METAL forming steps (rules, Flange, Hem, Bend) (pure Python).
Imported at the end of schema.py; it adds its step keys and wraps schema.validate, as
gear_schema does. (Empty until that area's builder fills it.)"""

from . import schema  # noqa: F401
