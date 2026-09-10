"""Catalog loading, merging, caching and lookup."""

import json
import os
import random
import re
import threading

from . import catalogs

ROOT = os.path.dirname(os.path.abspath(__file__))
STYLES_DIR = os.path.join(ROOT, "styles")
USER_DIR = os.path.join(ROOT, "user")
DATA_DIR = os.path.join(ROOT, "data")
OVERRIDES_PATH = os.path.join(USER_DIR, "overrides.json")
CUSTOM_PATH = os.path.join(USER_DIR, "custom.json")
HIDDEN_PATH = os.path.join(USER_DIR, "hidden.json")
# Favourites and recents belong to the active catalog, so they are resolved per
# call: "my Krea 2" keeps its own shortlist and history.


def favourites_path():
    return catalogs.paths()["favourites"]


def recents_path():
    return catalogs.paths()["recents"]
MAX_RECENTS = 24

AXES = ["style", "format", "finish"]
RANDOM_TOKEN = "\U0001F3B2 Random"

# families brought in from other projects; see THIRD-PARTY-NOTICES.md
IMPORTED_FAMILIES = {"Extra"}

FAMILY_ORDER = [
    "Anime & Manga",
    "Western Animation",
    "Comics & Print",
    "Traditional Painting",
    "Illustration",
    "Photography & Film",
    "3D & Games",
    "Design & Aesthetics",
    "Experimental & Material",
    # ships with the node, so it belongs in this list — it sits last, after the
    # written families and before anything the user has made
    "Extra",
    "Other",
]

FAMILY_TAG = {
    "Anime & Manga": "Anime",
    "Western Animation": "Cartoon",
    "Comics & Print": "Comic",
    "Traditional Painting": "Painting",
    "Illustration": "Illustration",
    "Photography & Film": "Photo",
    "3D & Games": "3D",
    "Design & Aesthetics": "Aesthetic",
    "Experimental & Material": "Material",
    "Extra": "Extra",
    "Other": "Custom",
}

FAMILY_MEDIUM = {
    "Anime & Manga": "anime style image",
    "Western Animation": "cartoon style image",
    "Comics & Print": "comic style image",
    "Traditional Painting": "painting style image",
    "Illustration": "illustration style image",
    "Photography & Film": "photograph style image",
    "3D & Games": "cgi style image",
    "Design & Aesthetics": "graphic style image",
    "Experimental & Material": "material style image",
    "Extra": "style image",
    "Other": "style image",
}

_LOCK = threading.Lock()
_CACHE = {"signature": None, "entries": []}


def read_json(path, default):
    if not os.path.isfile(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return default


# ComfyUI can execute several prompts at once, so every read-modify-write of a
# user file has to be serialised: two runs saving a preview or pushing a recent
# would otherwise each write the state they read and one update would vanish.
IO_LOCK = threading.RLock()


def write_json(path, data):
    """Atomically replace *path*. The temp name carries the thread id so two
    concurrent writers never share a scratch file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.{os.getpid()}.{threading.get_ident()}.tmp"
    with IO_LOCK:
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        os.replace(tmp, path)


def clean_name(name):
    name = re.sub(r"\s+", " ", str(name or "").strip())
    return name.replace("/", "-").replace("\\", "-").replace("\x00", "")[:160]


def slug(text, limit=52):
    text = re.sub(r"[^a-z0-9]+", "_", str(text or "").lower()).strip("_")
    return text[:limit] or "entry"


def base_name(name):
    return re.sub(r"^(\[[^\]]+\]\s*)+", "", str(name or "")).strip()


def normalise(raw, source="shipped"):
    name = clean_name(raw.get("name", ""))
    if not name:
        return None
    family = str(raw.get("family", "Other")).strip() or "Other"
    axis = str(raw.get("axis", "style")).strip()
    entry = {
        "id": str(raw.get("id") or f"{slug(family.split(' ')[0], 8)}.{slug(name)}"),
        "name": name,
        "family": family,
        "axis": axis if axis in AXES else "style",
        "medium": str(raw.get("medium") or FAMILY_MEDIUM.get(family, "style image")).strip(),
        "nl": str(raw.get("nl", "")).strip(),
        "tags": [str(t).strip() for t in (raw.get("tags") or []) if str(t).strip()],
        "tags_negative": [str(t).strip() for t in (raw.get("tags_negative") or []) if str(t).strip()],
        "negative": str(raw.get("negative", "")).strip(),
        "aliases": [str(a).strip() for a in (raw.get("aliases") or []) if str(a).strip()],
        "written": bool(raw.get("written", False)),
        "source": source,
    }
    return entry


def load_shipped():
    entries = []
    if not os.path.isdir(STYLES_DIR):
        return entries
    for filename in sorted(os.listdir(STYLES_DIR)):
        if not filename.endswith(".json"):
            continue
        data = read_json(os.path.join(STYLES_DIR, filename), {})
        rows = data.get("styles") if isinstance(data, dict) else data
        for raw in rows or []:
            if not isinstance(raw, dict):
                continue
            source = "v2" if "[v2]" in str(raw.get("name", "")) else "shipped"
            entry = normalise(raw, source)
            if entry:
                entries.append(entry)
    return entries


def load_overrides():
    data = read_json(OVERRIDES_PATH, {})
    return data if isinstance(data, dict) else {}


def load_custom():
    data = read_json(CUSTOM_PATH, [])
    return data if isinstance(data, list) else []


def load_hidden():
    """Hidden style names, as stored (original case), newest last."""
    data = read_json(HIDDEN_PATH, [])
    if isinstance(data, dict):
        data = data.get("names", [])
    if not isinstance(data, list):
        return []
    return [str(name).strip() for name in data if str(name).strip()]


def hidden_keys():
    """Lower-cased hidden names, for matching against the catalog."""
    return {name.lower() for name in load_hidden()}


def save_hidden(names):
    write_json(HIDDEN_PATH, list(names))


# ---------------------------------------------------------------- favourites

def load_favourites():
    data = read_json(favourites_path(), [])
    return [str(name).strip() for name in data if str(name).strip()] if isinstance(data, list) else []


def is_favourite(name):
    return clean_name(name).lower() in {item.lower() for item in load_favourites()}


def set_favourite(name, on=True):
    """Star or unstar a style. Returns the new state."""
    name = clean_name(name)
    if not name:
        return False
    with IO_LOCK:  # read-modify-write: parallel runs must not clobber each other
        favourites = load_favourites()
        lowered = {item.lower() for item in favourites}
        if on and name.lower() not in lowered:
            favourites.append(name)
        elif not on:
            favourites = [item for item in favourites if item.lower() != name.lower()]
        write_json(favourites_path(), favourites)
    return bool(on)


def toggle_favourite(name):
    return set_favourite(name, not is_favourite(name))


def load_recents():
    data = read_json(recents_path(), [])
    return [str(name).strip() for name in data if str(name).strip()] if isinstance(data, list) else []


def push_recent(name):
    """Record a style as just used; most recent first, capped."""
    name = clean_name(name)
    if not name or name == "None":
        return load_recents()
    with IO_LOCK:  # several prompts can finish at once; keep every one of them
        recents = [item for item in load_recents() if item.lower() != name.lower()]
        recents.insert(0, name)
        recents = recents[:MAX_RECENTS]
        write_json(recents_path(), recents)
    return recents


def clear_recents():
    write_json(recents_path(), [])
    return True


def _signature():
    parts = []
    if os.path.isdir(STYLES_DIR):
        for filename in sorted(os.listdir(STYLES_DIR)):
            if filename.endswith(".json"):
                parts.append((filename, os.path.getmtime(os.path.join(STYLES_DIR, filename))))
    for path in (OVERRIDES_PATH, CUSTOM_PATH, HIDDEN_PATH):
        parts.append((os.path.basename(path), os.path.getmtime(path) if os.path.isfile(path) else 0))
    return tuple(parts)


OVERRIDE_FIELDS = ("nl", "medium", "negative", "tags", "tags_negative", "family", "axis")
# A rename is stored as a "name" patch. The override stays keyed by the ORIGINAL
# name, so the entry keeps its id (previews stay attached) and the original name
# survives as an alias — saved workflows referring to it still resolve.
RENAME_FIELD = "name"


def entries(force=False):
    with _LOCK:
        signature = _signature()
        if not force and _CACHE["signature"] == signature and _CACHE["entries"]:
            return _CACHE["entries"]

        overrides = load_overrides()
        hidden = hidden_keys()
        merged, seen = [], set()

        for entry in load_shipped():
            key = entry["name"].lower()
            if key in hidden or key in seen:
                continue
            seen.add(key)
            patch = overrides.get(entry["name"]) or overrides.get(key)
            if isinstance(patch, dict):
                entry = dict(entry)
                for field in OVERRIDE_FIELDS:
                    if patch.get(field) is None:
                        continue
                    entry[field] = patch[field] if field in ("tags", "tags_negative") else str(patch[field]).strip()
                renamed = str(patch.get(RENAME_FIELD) or "").strip()
                if renamed and renamed.lower() != entry["name"].lower():
                    aliases = list(entry.get("aliases") or [])
                    if entry["name"] not in aliases:
                        aliases.append(entry["name"])
                    entry["aliases"] = aliases
                    entry["name"] = renamed
                entry["source"] = "override"
            merged.append(entry)

        for raw in load_custom():
            entry = normalise(raw, "custom") if isinstance(raw, dict) else None
            if not entry or entry["name"].lower() in hidden or entry["name"].lower() in seen:
                continue
            seen.add(entry["name"].lower())
            merged.append(entry)

        merged.sort(key=lambda item: (
            AXES.index(item["axis"]) if item["axis"] in AXES else 9,
            FAMILY_ORDER.index(item["family"]) if item["family"] in FAMILY_ORDER else 99,
            item["name"].lower(),
        ))
        _CACHE.update({"signature": signature, "entries": merged})
        return merged


def by_axis(axis, pool=None):
    return [entry for entry in (pool if pool is not None else entries()) if entry["axis"] == axis]


def names_for(axis, pool=None):
    return [entry["name"] for entry in by_axis(axis, pool)]


def resolve(name, pool=None):
    name = clean_name(name)
    if not name or name in ("None", RANDOM_TOKEN):
        return None
    pool = pool if pool is not None else entries()
    for entry in pool:
        if entry["name"] == name:
            return entry
    lowered = name.lower()
    for entry in pool:
        if entry["name"].lower() == lowered or entry["id"].lower() == lowered:
            return entry
        if any(alias.lower() == lowered for alias in entry["aliases"]):
            return entry
    # Base-name fallback: an imported family can legitimately carry the same
    # look as an entry written here ("Pixel Art" exists in both), so a bare name
    # resolves to this catalog's own entry first and only then to an import.
    stripped = base_name(name).lower()
    fallback = None
    for entry in pool:
        if base_name(entry["name"]).lower() != stripped:
            continue
        if entry.get("family") in IMPORTED_FAMILIES:
            fallback = fallback or entry
        else:
            return entry
    return fallback


def preview_key(text):
    """Normalise an id/name the same way the gallery names its files."""
    return re.sub(r"[^A-Za-z0-9]+", "_", str(text or "").strip()).strip("_")[:140]


def scope_pool(axis="style", scope="all", family=None, previews=None, exclude=()):
    """Entries a scope allows, in catalog order.

    scope: all | family | favourites | recent | has preview | missing preview.
    Shared by the dice and by crawl mode so both walk exactly the same set.
    """
    pool = by_axis(axis)
    if scope == "family" and family:
        pool = [entry for entry in pool if entry["family"] == family]
    if scope == "favourites":
        wanted = {name.lower() for name in load_favourites()}
        picked = [entry for entry in pool if entry["name"].lower() in wanted]
        pool = picked or pool
    if scope == "recent":
        wanted = {name.lower() for name in load_recents()}
        picked = [entry for entry in pool if entry["name"].lower() in wanted]
        pool = picked or pool
    if scope in ("has preview", "missing preview") and previews is not None:
        # the gallery keys on a slugged id, so compare like for like
        have = {preview_key(key) for key in previews}
        want = scope == "has preview"
        pool = [entry for entry in pool if (preview_key(entry["id"]) in have) is want]
    return [entry for entry in pool if entry["name"] not in exclude]


def roll(axis="style", scope="all", family=None, seed=None, previews=None, exclude=()):
    """Pick a random entry from the scope's pool."""
    pool = scope_pool(axis, scope, family, previews, exclude)
    if not pool:
        return None
    rng = random.Random(seed) if seed not in (None, 0) else random
    return rng.choice(pool)


def written_names(axis="style"):
    """Names on an axis excluding imported packs and the user's own entries.

    This is what the main style dropdowns carry: keeping three thousand options
    in each of them made every menu heavy to open.
    """
    return [entry["name"] for entry in by_axis(axis)
            if entry["family"] not in IMPORTED_FAMILIES and entry.get("source") != "custom"]


def imported_style_names():
    """Names belonging to an imported pack, for the dedicated slot."""
    return [entry["name"] for entry in by_axis("style") if entry["family"] in IMPORTED_FAMILIES]


def custom_names(axis="style"):
    """Names of the user's own entries on an axis.

    Feeds the node's custom_style slot, so your own styles are one dropdown
    away instead of buried among a thousand shipped ones.
    """
    return [entry["name"] for entry in by_axis(axis) if entry.get("source") == "custom"]


SOURCES = ("main", "extra", "custom")


def source_pool(source):
    """The style names one dropdown carries."""
    if source == "extra":
        return imported_style_names()
    if source == "custom":
        return custom_names("style")
    return written_names("style")


def crawl_names(scope="all", family=None, previews=None, missing_only=False, source="main"):
    """The ordered style names crawl mode steps through for a scope.

    With *missing_only*, entries that already have a preview are dropped — the
    same filter the UI applies, so the node's fallback agrees with the walk.
    """
    allowed = set(source_pool(source))
    pool = [entry for entry in scope_pool("style", scope, family, previews)
            if entry["name"] in allowed]
    if missing_only and previews is not None:
        have = {preview_key(key) for key in previews}
        pool = [entry for entry in pool if preview_key(entry["id"]) not in have]
    return [entry["name"] for entry in pool]


def coverage():
    pool = entries()
    total = len(pool)
    written = sum(1 for entry in pool if entry["written"])
    per_family = {}
    for entry in pool:
        stats = per_family.setdefault(entry["family"], {"total": 0, "written": 0})
        stats["total"] += 1
        stats["written"] += 1 if entry["written"] else 0
    return {"total": total, "written": written, "families": per_family}


def tag_vocabulary():
    path = os.path.join(DATA_DIR, "tags.txt")
    tags = []
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line and not line.startswith("#"):
                    tags.append(line)
    return tags


LIGHT_FIELDS = ("name", "id", "family", "axis", "medium", "source", "written",
                "aliases", "tags", "tags_negative")


def payload():
    pool = entries()
    families = {}
    by_name = {}
    for entry in pool:
        families.setdefault(entry["family"], []).append(entry["name"])
        # a light copy: the clause ('nl') and 'negative' account for most of the
        # catalog's weight and are only ever wanted for one entry at a time, so
        # they come from /neons_style/entry instead of every catalog load
        by_name[entry["name"]] = {field: entry[field] for field in LIGHT_FIELDS}
    return {
        "schema": 1,
        "favourites": load_favourites(),
        "recents": load_recents(),
        "styles": names_for("style", pool),
        "formats": names_for("format", pool),
        "finishes": names_for("finish", pool),
        "families": families,
        # which families ship with the node: everything else is user-made, and
        # the browser groups those together under one filter
        "shipped_families": list(FAMILY_ORDER),
        "imported_families": sorted(IMPORTED_FAMILIES),
        "family_order": [f for f in FAMILY_ORDER if f in families]
        + [f for f in families if f not in FAMILY_ORDER],
        "axes": AXES,
        "random_token": RANDOM_TOKEN,
        "by_name": by_name,
        "coverage": coverage(),
        "count": len(by_name),
    }
