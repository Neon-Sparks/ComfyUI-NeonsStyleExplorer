"""Named catalogs — one preview set per model, or per project.

A catalog owns everything that is about *your* images rather than about the
styles themselves: the preview gallery, the favourites and the recently-used
list. The style texts, your edits and your custom entries are shared by every
catalog, because a hand-written style prefix is worth the same whichever model
rendered it.

The catalog you started with keeps its files exactly where they were, so
switching to a named catalog and back never moves or rewrites existing
previews. New catalogs live under ``user/catalogs/<id>/``.

This module deliberately imports nothing from the rest of the package: both
``catalog.py`` and ``gallery.py`` depend on it.
"""

import json
import os
import re
import threading
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
USER_DIR = os.path.join(ROOT, "user")
CATALOGS_DIR = os.path.join(USER_DIR, "catalogs")
INDEX_PATH = os.path.join(USER_DIR, "catalogs.json")

MAX_PROMPT = 800
MAX_PROMPTS = 12

DEFAULT_ID = "default"
DEFAULT_NAME = "Default"
MAX_NAME = 60

_LOCK = threading.RLock()


# ---------------------------------------------------------------- index io


def _read():
    if os.path.isfile(INDEX_PATH):
        try:
            with open(INDEX_PATH, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, dict) and isinstance(data.get("items"), list):
                return data
        except (OSError, json.JSONDecodeError):
            pass
    return {"active": DEFAULT_ID, "items": [{"id": DEFAULT_ID, "name": DEFAULT_NAME, "created": 0}]}


def _write(data):
    os.makedirs(USER_DIR, exist_ok=True)
    tmp = f"{INDEX_PATH}.{os.getpid()}.{threading.get_ident()}.tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    os.replace(tmp, INDEX_PATH)


def _slug(name, taken):
    base = re.sub(r"[^a-z0-9]+", "-", str(name or "").strip().lower()).strip("-")[:40]
    base = base or "catalog"
    if base == DEFAULT_ID and DEFAULT_ID in taken:
        base = "catalog"
    candidate, n = base, 2
    while candidate in taken:
        candidate = f"{base}-{n}"
        n += 1
    return candidate


def clean_prompt(text):
    text = re.sub(r"[ \t]+", " ", str(text or "").strip())
    return text[:MAX_PROMPT]


def clean_prompts(value):
    if not isinstance(value, list):
        return []
    out = []
    for item in value:
        text = clean_prompt(item)
        if text and text not in out:
            out.append(text)
    return out[:MAX_PROMPTS]


def clean_name(name):
    name = re.sub(r"\s+", " ", str(name or "").strip())
    return name[:MAX_NAME]


# ---------------------------------------------------------------- queries


def items():
    """Every catalog, default first, in creation order."""
    data = _read()
    seen, out = set(), []
    for item in data["items"]:
        cid = str(item.get("id") or "")
        if not cid or cid in seen:
            continue
        seen.add(cid)
        out.append({
            "id": cid,
            "name": clean_name(item.get("name")) or cid,
            "created": item.get("created", 0),
            # the prompt(s) these previews were generated with, so a catalog
            # says how it was made and not just what is in it
            "prompts": clean_prompts(item.get("prompts")),
        })
    if not any(item["id"] == DEFAULT_ID for item in out):
        out.insert(0, {"id": DEFAULT_ID, "name": DEFAULT_NAME, "created": 0})
    return out


def active():
    """The catalog in use. Falls back to the default if it went missing."""
    data = _read()
    current = str(data.get("active") or DEFAULT_ID)
    return current if any(item["id"] == current for item in items()) else DEFAULT_ID


def name_of(cid=None):
    cid = cid or active()
    for item in items():
        if item["id"] == cid:
            return item["name"]
    return DEFAULT_NAME


def paths(cid=None):
    """Where one catalog keeps its files.

    The default catalog keeps the original locations so an existing install is
    untouched by this feature.
    """
    cid = cid or active()
    if cid == DEFAULT_ID:
        previews = os.path.join(ROOT, "previews")
        return {
            "previews": previews,
            "manifest": os.path.join(previews, "manifest.json"),
            "favourites": os.path.join(USER_DIR, "favourites.json"),
            "recents": os.path.join(USER_DIR, "recents.json"),
        }
    base = os.path.join(CATALOGS_DIR, cid)
    return {
        "previews": os.path.join(base, "previews"),
        "manifest": os.path.join(base, "previews", "manifest.json"),
        "favourites": os.path.join(base, "favourites.json"),
        "recents": os.path.join(base, "recents.json"),
    }


def payload():
    """What the UI needs to draw the catalog picker."""
    current = active()
    return {
        "active": current,
        "name": name_of(current),
        "items": [dict(item, shots=count_shots(item["id"])) for item in items()],
    }


def count_shots(cid):
    """How many styles have a preview in this catalog."""
    path = paths(cid)["manifest"]
    if not os.path.isfile(path):
        return 0
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return len(data) if isinstance(data, dict) else 0
    except (OSError, json.JSONDecodeError):
        return 0


# ---------------------------------------------------------------- mutations


def create(name):
    """Add a catalog and switch to it. Returns its record."""
    label = clean_name(name) or "Catalog"
    with _LOCK:
        data = _read()
        taken = {str(item.get("id")) for item in data["items"]} | {DEFAULT_ID}
        record = {"id": _slug(label, taken), "name": label, "created": int(time.time()), "prompts": []}
        data["items"].append(record)
        data["active"] = record["id"]
        _write(data)
    os.makedirs(paths(record["id"])["previews"], exist_ok=True)
    return record


def select(cid):
    """Switch catalogs. Unknown ids fall back to the default."""
    cid = str(cid or DEFAULT_ID)
    with _LOCK:
        data = _read()
        known = {str(item.get("id")) for item in data["items"]} | {DEFAULT_ID}
        data["active"] = cid if cid in known else DEFAULT_ID
        _write(data)
    os.makedirs(paths(data["active"])["previews"], exist_ok=True)
    return data["active"]


def rename(cid, name):
    label = clean_name(name)
    if not label:
        return False
    with _LOCK:
        data = _read()
        for item in data["items"]:
            if str(item.get("id")) == str(cid):
                item["name"] = label
                _write(data)
                return True
        if str(cid) == DEFAULT_ID:  # default may be missing from an old index
            data["items"].insert(0, {"id": DEFAULT_ID, "name": label, "created": 0})
            _write(data)
            return True
    return False


def prompts_of(cid=None):
    cid = cid or active()
    for item in items():
        if item["id"] == cid:
            return item["prompts"]
    return []


def add_prompt(cid, text):
    """Record a generation prompt against a catalog. Duplicates are ignored."""
    text = clean_prompt(text)
    if not text:
        return False
    cid = str(cid or active())
    with _LOCK:
        data = _read()
        for item in data["items"]:
            if str(item.get("id")) == cid:
                current = clean_prompts(item.get("prompts"))
                if text in current:
                    return True
                item["prompts"] = (current + [text])[:MAX_PROMPTS]
                _write(data)
                return True
        if cid == DEFAULT_ID:  # default may be missing from an old index
            data["items"].insert(0, {"id": DEFAULT_ID, "name": DEFAULT_NAME, "created": 0, "prompts": [text]})
            _write(data)
            return True
    return False


def delete_prompt(cid, text=None, index=None):
    """Drop one recorded prompt, by exact text or by position."""
    cid = str(cid or active())
    with _LOCK:
        data = _read()
        for item in data["items"]:
            if str(item.get("id")) != cid:
                continue
            current = clean_prompts(item.get("prompts"))
            if text is not None:
                kept = [entry for entry in current if entry != clean_prompt(text)]
            elif index is not None and 0 <= int(index) < len(current):
                kept = [entry for n, entry in enumerate(current) if n != int(index)]
            else:
                return False
            if len(kept) == len(current):
                return False
            item["prompts"] = kept
            _write(data)
            return True
    return False


def remove(cid, delete_files=False):
    """Drop a catalog. The default one cannot be removed.

    Its previews are left on disk unless *delete_files*, so a mis-click is
    recoverable by recreating a catalog with the same name.
    """
    cid = str(cid or "")
    if cid == DEFAULT_ID or not cid:
        return False
    with _LOCK:
        data = _read()
        kept = [item for item in data["items"] if str(item.get("id")) != cid]
        if len(kept) == len(data["items"]):
            return False
        data["items"] = kept
        if str(data.get("active")) == cid:
            data["active"] = DEFAULT_ID
        _write(data)
    if delete_files:
        import shutil

        shutil.rmtree(os.path.join(CATALOGS_DIR, cid), ignore_errors=True)
    return True
