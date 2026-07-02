# -*- coding: utf-8 -*-
"""
Revit selection-context detection and item filtering.

This module inspects the current Revit selection to determine which
*context* (e.g. ``"pipes"``, ``"walls"``) is active, and provides a
generic filter that checks ``context_rules`` dictionaries attached to
menu items.

Revit API imports are wrapped in ``try/except`` so the module can be
imported safely outside of a Revit host (useful for testing).
"""

import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional Revit imports
# ---------------------------------------------------------------------------
_REVIT_AVAILABLE = False
_BuiltInCategory = None

try:
    from Autodesk.Revit.DB import BuiltInCategory as _BIC
    _BuiltInCategory = _BIC
    _REVIT_AVAILABLE = True
except (ImportError, Exception):
    pass


# ---------------------------------------------------------------------------
# Category map
# ---------------------------------------------------------------------------

CATEGORY_MAP = {
    -2008065: "pipes",       # OST_PipeCurves
    -2008130: "ducts",       # OST_DuctCurves
    -2000011: "walls",       # OST_Walls
    -2000021: "dimensions",  # OST_Dimensions
}
"""dict[int, str]: Mapping of Revit ``BuiltInCategory`` integer IDs to
human-readable context strings.

Add entries here to extend context detection to new element categories.
"""


# ---------------------------------------------------------------------------
# Context detection
# ---------------------------------------------------------------------------

def get_current_context(uiapp):
    """Determine the current Revit selection context.

    Inspects the first selected element in the active document and maps
    its category to a context string via :data:`CATEGORY_MAP`.  Falls
    back to the ``BuiltInCategory`` enum if the integer ID look-up
    misses.

    Args:
        uiapp: A Revit ``UIApplication`` instance.  May be ``None``, in
            which case ``"default"`` is returned.

    Returns:
        str: One of the context strings defined in :data:`CATEGORY_MAP`
        (e.g. ``"pipes"``), or ``"default"`` if no matching selection is
        found.
    """
    context = "default"
    try:
        if uiapp is None:
            return context
        uidoc = uiapp.ActiveUIDocument
        if uidoc is None:
            return context

        doc = uidoc.Document
        sel_ids = uidoc.Selection.GetElementIds()
        if not sel_ids or sel_ids.Count == 0:
            return context

        first_el = doc.GetElement(sel_ids[0])
        if first_el is None:
            return context

        category = first_el.Category
        if category is None:
            return context

        if hasattr(category.Id, "Value"):
            cat_id = int(category.Id.Value)
        else:
            cat_id = category.Id.IntegerValue

        # Fast integer look-up
        if cat_id in CATEGORY_MAP:
            context = CATEGORY_MAP[cat_id]
        else:
            # Fallback: enum comparison (requires Revit API)
            if _BuiltInCategory is not None:
                try:
                    cat_enum = category.BuiltInCategory
                    _enum_map = {
                        _BuiltInCategory.OST_PipeCurves: "pipes",
                        _BuiltInCategory.OST_DuctCurves: "ducts",
                        _BuiltInCategory.OST_Walls: "walls",
                        _BuiltInCategory.OST_Dimensions: "dimensions",
                    }
                    context = _enum_map.get(cat_enum, context)
                except Exception:
                    pass

        logger.debug("Resolved Revit selection context: %s", context)
    except Exception as ex:
        logger.debug("Error detecting selection context: %s", ex)
    return context


# ---------------------------------------------------------------------------
# Context-rule schema
# ---------------------------------------------------------------------------

class ContextRule(object):
    """Documentation-only class describing the ``context_rules`` schema.

    Each menu item may carry a ``context_rules`` dictionary with the
    following optional keys:

    Attributes:
        allowed_views (list[str]): View-type filter.  Recognised tokens:
            ``"3D"``, ``"Plan"``, ``"Sheet"``.  An empty list means
            *all views*.
        allowed_classes (list[str]): Element-class filter (reserved for
            future use).  When specified the item is shown only when
            selected elements match one of the listed classes.

    Example ``context_rules`` dict::

        {
            "allowed_views": ["3D", "Plan"],
            "allowed_classes": ["Wall", "Pipe"]
        }
    """
    pass


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------

def filter_by_context(items, context_string, view_type=None):
    """Filter a list of items by their ``context_rules``.

    Items without ``context_rules`` (or with an empty dict) are always
    included.

    Args:
        items (list[dict]): Menu items, each optionally containing a
            ``"context_rules"`` key.
        context_string (str): The active context string as returned by
            :func:`get_current_context`.  Used for view-type matching.
        view_type (str or None): Additional view-type hint.  If given it
            is checked against ``allowed_views`` instead of
            *context_string*.

    Returns:
        list[dict]: The subset of *items* that pass the context filter.
    """
    check_str = (view_type or context_string or "").lower()
    filtered = []
    try:
        for item in items:
            rules = item.get("context_rules", {})
            if not rules:
                # No rules = always visible
                filtered.append(item)
                continue

            # -- allowed_views check -----------------------------------------
            allowed_views = rules.get("allowed_views", [])
            if allowed_views:
                view_match = False
                if "3D" in allowed_views and "3d" in check_str:
                    view_match = True
                elif "Plan" in allowed_views and (
                    "plan" in check_str or "section" in check_str
                ):
                    view_match = True
                elif "Sheet" in allowed_views and "sheet" in check_str:
                    view_match = True
                elif not allowed_views:
                    view_match = True

                if not view_match:
                    continue

            # -- allowed_classes check (reserved for future use) -------------
            # allowed_classes = rules.get("allowed_classes", [])
            # Full class matching will be implemented when Revit selection
            # context provides element class information.

            filtered.append(item)
    except Exception as ex:
        logger.debug("Error filtering items by context: %s", ex)
        return list(items)
    return filtered
