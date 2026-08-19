"""Pure layout helpers for the configurable cockpit (v2.2.41).

The Qt widgets delegate ordering decisions to this module so migrations and
automatic/fixed layouts can be regression-tested without a GUI runtime.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

LAYOUT_AUTO = "auto"
LAYOUT_FIXED = "fixed"
VALID_LAYOUT_MODES = (LAYOUT_AUTO, LAYOUT_FIXED)


def normalize_mode(value: object) -> str:
    """Return a supported layout mode; unknown values fall back to automatic."""
    mode = str(value or LAYOUT_AUTO).strip().lower()
    return mode if mode in VALID_LAYOUT_MODES else LAYOUT_AUTO


def normalize_order(
    panel_keys: Iterable[str],
    raw_order: object,
    *,
    legacy_map: Mapping[str, str] | None = None,
) -> list[str]:
    """Clean, de-duplicate and complete a persisted panel order.

    Old panel identifiers can be mapped to their replacement. This is needed
    for the v2.2.40 merge of three warning panels into ``action_needed``.
    """
    keys = list(dict.fromkeys(str(key) for key in panel_keys))
    valid = set(keys)
    aliases = dict(legacy_map or {})
    raw = raw_order if isinstance(raw_order, list) else []
    result: list[str] = []
    for value in raw:
        key = aliases.get(str(value), str(value))
        if key in valid and key not in result:
            result.append(key)
    for key in keys:
        if key not in result:
            result.append(key)
    return result


def normalize_columns(
    panel_keys: Iterable[str],
    raw_columns: object,
    *,
    default_left: Iterable[str] = (),
) -> dict[str, str]:
    """Return a complete ``panel -> left/right`` mapping."""
    keys = list(dict.fromkeys(str(key) for key in panel_keys))
    left = set(str(key) for key in default_left)
    raw = raw_columns if isinstance(raw_columns, dict) else {}
    result: dict[str, str] = {}
    for key in keys:
        value = str(raw.get(key, "") or "").lower()
        result[key] = (
            value
            if value in ("left", "right")
            else ("left" if key in left else "right")
        )
    return result


def arrange_columns(
    panel_keys: Iterable[str],
    order: object,
    columns: object,
    *,
    default_left: Iterable[str] = (),
    empty_keys: Iterable[str] = (),
    automatic: bool,
    legacy_map: Mapping[str, str] | None = None,
) -> tuple[list[str], list[str]]:
    """Build ordered left/right panel lists.

    Automatic mode always uses the product's stable default columns and moves
    empty sections below populated sections *inside the same column*. Fixed
    mode keeps the user's stored column assignment and exact order.
    """
    keys = list(dict.fromkeys(str(key) for key in panel_keys))
    clean_order = normalize_order(keys, order, legacy_map=legacy_map)
    mapping = normalize_columns(
        keys,
        {} if automatic else columns,
        default_left=default_left,
    )
    left = [key for key in clean_order if mapping[key] == "left"]
    right = [key for key in clean_order if mapping[key] == "right"]
    if automatic:
        empty = set(str(key) for key in empty_keys)
        left = [key for key in left if key not in empty] + [
            key for key in left if key in empty
        ]
        right = [key for key in right if key not in empty] + [
            key for key in right if key in empty
        ]
    return left, right


def columns_from_lists(
    panel_keys: Iterable[str], left: Iterable[str], right: Iterable[str]
) -> dict[str, str]:
    """Create a complete persisted mapping from a drag/drop result."""
    keys = list(dict.fromkeys(str(key) for key in panel_keys))
    left_set = set(str(key) for key in left)
    right_set = set(str(key) for key in right)
    return {
        key: "left" if key in left_set else "right"
        for key in keys
        if key in left_set or key in right_set
    }
