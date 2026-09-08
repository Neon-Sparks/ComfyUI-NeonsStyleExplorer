"""User edits: overrides on shipped styles, custom styles, hidden styles."""

import re

from .catalog import (
    AXES,
    HIDDEN_PATH,
    clear_recents,
    is_favourite,
    load_favourites,
    load_recents,
    push_recent,
    set_favourite,
    toggle_favourite,
    CUSTOM_PATH,
    FAMILY_MEDIUM,
    FAMILY_TAG,
    OVERRIDES_PATH,
    clean_name,
    entries,
    load_custom,
    load_hidden,
    load_overrides,
    load_shipped,
    save_hidden,
    slug,
    write_json,
)

FIELDS = ("nl", "medium", "negative", "tags", "tags_negative", "family", "axis")


def as_tags(value):
    if isinstance(value, str):
        value = re.split(r"[,\n]", value)
    return [str(tag).strip().replace(" ", "_") for tag in (value or []) if str(tag).strip()]


def family_tag(family):
    family = clean_name(family) or "Other"
    if family in FAMILY_TAG:
        return FAMILY_TAG[family]
    token = re.sub(r"[^A-Za-z0-9]+", "", family.split("&")[0].strip().split(" ")[0] or "Custom")
    return token[:12] or "Custom"


def custom_name(raw, family, axis="style"):
    raw = re.sub(r"^(\[[^\]]+\]\s*)+", "", clean_name(raw)).strip()
    if not raw:
        return ""
    tag = axis.capitalize() if axis in ("format", "finish") else family_tag(family)
    return f"[{tag}][Custom] {raw}"


def save_override(name, **fields):
    name = clean_name(name)
    if not name:
        return False, "bad name"
    shipped = {entry["name"] for entry in load_shipped()}
    customs = {clean_name(item.get("name", "")) for item in load_custom()}
    if name in customs:
        return save_custom(name, update=True, **fields)
    if name not in shipped:
        return False, "unknown style"
    overrides = load_overrides()
    patch = overrides.get(name) if isinstance(overrides.get(name), dict) else {}
    for field in FIELDS:
        if fields.get(field) is None:
            continue
        patch[field] = as_tags(fields[field]) if field in ("tags", "tags_negative") else str(fields[field]).strip()
    if patch.get("axis") and patch["axis"] not in AXES:
        patch.pop("axis")
    overrides[name] = patch
    write_json(OVERRIDES_PATH, overrides)
    entries(force=True)
    return True, name


def delete_override(name):
    name = clean_name(name).lower()
    overrides = load_overrides()
    for key in list(overrides):
        if key.lower() == name:
            overrides.pop(key)
            write_json(OVERRIDES_PATH, overrides)
            entries(force=True)
            return True
    return False


def save_custom(name, family="Other", axis="style", nl="", medium="", negative="",
                tags=None, tags_negative=None, update=False, **_extra):
    family = clean_name(family) or "Other"
    axis = axis if axis in AXES else "style"
    name = clean_name(name) if update else custom_name(name, family, axis)
    if not name:
        return False, "bad name"
    if not str(nl or "").strip():
        return False, "style clause is required"

    customs = load_custom()
    existing = next(
        (item for item in customs if clean_name(item.get("name", "")).lower() == name.lower()),
        None,
    )
    if existing is None and name.lower() in {e["name"].lower() for e in load_shipped()}:
        return False, "name collides with a shipped style"

    record = {
        "id": (existing or {}).get("id") or f"custom.{slug(name)}",
        "name": name,
        "family": family,
        "axis": axis,
        "medium": str(medium or FAMILY_MEDIUM.get(family, "style image")).strip(),
        "nl": str(nl).strip(),
        "tags": as_tags(tags),
        "tags_negative": as_tags(tags_negative),
        "negative": str(negative or "").strip(),
        "aliases": (existing or {}).get("aliases", []),
        "written": True,
    }
    if existing is None:
        customs.append(record)
    else:
        existing.update(record)
    write_json(CUSTOM_PATH, customs)
    entries(force=True)
    return True, name


def delete_custom(name):
    name = clean_name(name).lower()
    customs = load_custom()
    kept = [item for item in customs if clean_name(item.get("name", "")).lower() != name]
    if len(kept) == len(customs):
        return False
    write_json(CUSTOM_PATH, kept)
    entries(force=True)
    return True


def hide_style(name):
    name = clean_name(name)
    if not name:
        return False
    if name.lower() in {clean_name(i.get("name", "")).lower() for i in load_custom()}:
        return delete_custom(name)
    hidden = load_hidden()
    if name.lower() not in {item.lower() for item in hidden}:
        hidden.append(name)
    save_hidden(hidden)
    entries(force=True)
    return True


def restore_style(name):
    """Un-hide one shipped style."""
    name = clean_name(name).lower()
    hidden = load_hidden()
    kept = [item for item in hidden if item.lower() != name]
    if len(kept) == len(hidden):
        return False
    save_hidden(kept)
    entries(force=True)
    return True


def restore_all():
    """Un-hide every shipped style that was deleted from the catalog."""
    hidden = load_hidden()
    if not hidden:
        return 0
    save_hidden([])
    entries(force=True)
    return len(hidden)


def hidden_styles():
    """The shipped styles currently hidden, newest last."""
    return list(load_hidden())
