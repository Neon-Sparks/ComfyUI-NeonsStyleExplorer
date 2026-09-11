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
# a rename is patched alongside the rest; see catalog.RENAME_FIELD
RENAMEABLE = FIELDS + ("name",)


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


def unique_id(candidate):
    """An id nothing else is using, suffixed if need be."""
    taken = {str(entry.get("id", "")).lower() for entry in entries()}
    taken |= {str(item.get("id", "")).lower() for item in load_custom()}
    if candidate.lower() not in taken:
        return candidate
    n = 2
    while f"{candidate}_{n}".lower() in taken:
        n += 1
    return f"{candidate}_{n}"


def custom_name(raw, family, axis="style"):
    raw = re.sub(r"^(\[[^\]]+\]\s*)+", "", clean_name(raw)).strip()
    if not raw:
        return ""
    tag = axis.capitalize() if axis in ("format", "finish") else family_tag(family)
    return f"[{tag}][Custom] {raw}"


def name_taken(wanted, keep_id=None):
    """Is this display name already in use by another entry?

    Checked against the effective catalog, not just the shipped files: a name
    can already be claimed by another entry's rename, which is exactly the
    collision a shipped-names-only check misses.
    """
    wanted = clean_name(wanted).lower()
    if not wanted:
        return False
    for entry in entries():
        if keep_id and entry.get("id") == keep_id:
            continue
        if entry["name"].lower() == wanted:
            return True
    return False


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

    # A rename is stored on the same patch, still keyed by the original name, so
    # the entry keeps its id — its gallery images stay attached — and the
    # original name lives on as an alias.
    wanted = clean_name(fields.get("rename") or "")
    if wanted and wanted.lower() != name.lower():
        mine = next((entry for entry in entries()
                     if entry["name"].lower() == name.lower()
                     or name.lower() in [alias.lower() for alias in entry.get("aliases") or []]), None)
        if name_taken(wanted, keep_id=(mine or {}).get("id")):
            return False, f"'{wanted}' is already taken"
        patch["name"] = wanted
    elif wanted:
        patch.pop("name", None)
    overrides[name] = patch
    write_json(OVERRIDES_PATH, overrides)
    entries(force=True)
    return True, patch.get("name") or name


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
    previous = name
    if not str(nl or "").strip():
        return False, "style clause is required"

    customs = load_custom()
    existing = next(
        (item for item in customs if clean_name(item.get("name", "")).lower() == name.lower()),
        None,
    )
    if existing is None and name.lower() in {e["name"].lower() for e in load_shipped()}:
        return False, "name collides with a shipped style"

    wanted = clean_name(_extra.get("rename") or "")
    if update and existing and wanted and wanted.lower() != name.lower():
        if name_taken(wanted, keep_id=existing.get("id")):
            return False, f"'{wanted}' is already taken"
        name = wanted

    if update and existing and clean_name(existing.get("family", "")) != family:
        # the bracket tag is derived from the family, so a family change has to
        # rebuild the name — the old one is kept as an alias so saved workflows
        # and gallery images still resolve
        renamed = custom_name(name, family, axis)
        if renamed and renamed.lower() != name.lower():
            name = renamed

    aliases = list((existing or {}).get("aliases", []))
    if previous.lower() != name.lower() and previous not in aliases:
        aliases.append(previous)

    record = {
        # An id is permanent: gallery images are filed under it, so it must not
        # change when an entry is renamed. That makes the name free again, and a
        # later style taking that name used to generate the same id — inheriting
        # the first one's previews. New ids are therefore made unique against
        # every id already in use.
        "id": (existing or {}).get("id") or unique_id(f"custom.{slug(name)}"),
        "name": name,
        "family": family,
        "axis": axis,
        "medium": str(medium or FAMILY_MEDIUM.get(family, "style image")).strip(),
        "nl": str(nl).strip(),
        "tags": as_tags(tags),
        "tags_negative": as_tags(tags_negative),
        "negative": str(negative or "").strip(),
        "aliases": aliases,
        "written": True,
    }
    if existing is None:
        customs.append(record)
    else:
        existing.update(record)
    write_json(CUSTOM_PATH, customs)
    entries(force=True)
    return True, name


LONELY = "Lonely"


def families_admin():
    """Every family in use, with counts and whether it is one of the shipped
    ones. Only user-made families can be renamed or removed."""
    from .catalog import FAMILY_ORDER, entries as all_entries

    rows = {}
    for entry in all_entries():
        family = entry.get("family") or LONELY
        row = rows.setdefault(family, {"name": family, "total": 0, "mine": 0,
                                       "shipped": family in FAMILY_ORDER})
        row["total"] += 1
        if entry.get("source") == "custom":
            row["mine"] += 1
    order = [name for name in FAMILY_ORDER if name in rows] + \
            sorted(name for name in rows if name not in FAMILY_ORDER)
    return [rows[name] for name in order]


def _move_family(old, new):
    """Move every custom entry from one family to another, rebuilding the
    bracket tag on each name and keeping the old name as an alias."""
    from .catalog import FAMILY_ORDER, entries

    old = clean_name(old)
    new = clean_name(new) or LONELY
    if not old or old in FAMILY_ORDER:
        return False, "only your own families can be changed", 0

    customs = load_custom()
    moved = 0
    for item in customs:
        if clean_name(item.get("family", "")) != old:
            continue
        item["family"] = new
        previous = clean_name(item.get("name", ""))
        renamed = custom_name(previous, new, item.get("axis", "style"))
        if renamed and renamed.lower() != previous.lower():
            item["name"] = renamed
            aliases = list(item.get("aliases") or [])
            if previous not in aliases:
                aliases.append(previous)
            item["aliases"] = aliases
        moved += 1
    if not moved:
        return False, "no styles in that family", 0
    write_json(CUSTOM_PATH, customs)
    entries(force=True)
    return True, new, moved


def rename_family(old, new):
    new = clean_name(new)
    if not new:
        return False, "give the family a name", 0
    return _move_family(old, new)


def delete_family(name):
    """Remove a user family. Its styles are not deleted — they move to Lonely,
    the holding family for styles with nowhere else to be."""
    return _move_family(name, LONELY)


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
