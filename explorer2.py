"""Neons Style Explorer 2 — catalog, composer and user data.

Version 2 lives beside the original and shares nothing with it at run time:
its own style files (styles_v2/), its own user folder (user/v2/), its own
routes. A workflow that uses the original node is untouched.

A version 2 style is a LEAD ("Cross-hatched pen and ink drawing") followed by
PARTS, concrete descriptors ordered most-defining first. That order is what
makes strength work without emphasis syntax, which turbo models ignore: a
light touch keeps the lead and two parts, heavy keeps them all.

Everything is loaded lazily and cached, so starting ComfyUI costs nothing and
the node list carries no big dropdowns.
"""

import hashlib
import io
import json
import os
import random
import re
import shutil
import threading
import time

from .assets import derived_thumb, drop_derived, read_json, write_json

HERE = os.path.dirname(os.path.abspath(__file__))
SHIPPED = os.path.join(HERE, "styles_v2")
USER = os.path.join(HERE, "user", "v2")
STATE = os.path.join(USER, "state.json")
CUSTOM = os.path.join(USER, "custom.json")
PREVIEWS = os.path.join(USER, "previews")

STRENGTHS = {"light": 2, "standard": 4, "heavy": 7}       # parts kept from one style
MIX_BUDGET = {"light": 3, "standard": 6, "heavy": 10}      # parts shared by a blend
OUTPUTS = ["natural language", "tags", "natural language + tags"]
POSITIONS = ["before prompt", "after prompt"]
AUTO_PREVIEW = ["off", "if missing", "always"]
MOD_KINDS = ["lighting", "palette", "camera", "mood", "format", "finish"]
NONE = "None"
RANDOM = "Random"

MAX_PICKS = 3
MAX_RECENT = 40
MAX_COLLECTIONS = 60
MAX_COLLECTION = 2000
MAX_CUSTOM = 2000
MAX_NAME = 40
MAX_OWN_PARTS = 60      # a saved roller recipe can be this long; shipped styles have 5-7
PREVIEW_SIZE = 768
MAX_IMAGE_BYTES = 64 * 1024 * 1024
CUSTOM_CAT = "custom"

_lock = threading.RLock()
_cache = {"stamp": None, "data": None}
_state = {"stamp": None, "data": None}
_previews = {"stamp": None, "data": {}}
_claimed = set()                    # styles handed out by @next this session


# ------------------------------------------------------------------ text

def clean(text, limit=400):
    """One line of plain text: no control characters, no stray whitespace."""
    text = re.sub(r"[\x00-\x1f\x7f]", " ", str(text or ""))
    return re.sub(r"\s+", " ", text).strip()[:limit].strip()


def clean_name(text):
    # a name is also the key users type into the styles box, where , : @ | mean something
    return clean(re.sub(r"[,:@|\[\]\(\)<>\"\\]", " ", str(text or "")), MAX_NAME)


def slug(text):
    return re.sub(r"[^a-z0-9]+", "_", str(text or "").lower()).strip("_")[:80]


def _lower_first(text):
    if not text:
        return text
    if len(text) > 1 and (text[1].isupper() or text[1].isdigit()):   # CRT, 3D, VHS
        return text
    return text[0].lower() + text[1:]


def escape(text):
    """Brackets in a term would be read as prompt emphasis."""
    return str(text).replace("\\", "").replace("(", "\\(").replace(")", "\\)")


# --------------------------------------------------------------- catalog

def _stamp():
    marks = []
    try:
        names = sorted(name for name in os.listdir(SHIPPED) if name.endswith(".json"))
    except OSError:
        names = []
    for path in [os.path.join(SHIPPED, name) for name in names] + [CUSTOM]:
        try:
            info = os.stat(path)
            marks.append((os.path.basename(path), info.st_mtime_ns, info.st_size))
        except OSError:
            marks.append((os.path.basename(path), 0, 0))
    return tuple(marks)


def _style(raw, cat, custom=False):
    """Normalise one record; return None for anything unusable."""
    if not isinstance(raw, dict):
        return None
    name = clean_name(raw.get("name"))
    lead = clean(raw.get("lead"), 120)
    if not name or not lead:
        return None
    limit = MAX_OWN_PARTS if custom else 9
    parts = [clean(part, 100) for part in (raw.get("parts") or []) if clean(part, 100)][:limit]
    tags = [clean(tag, 60) for tag in (raw.get("tags") or []) if clean(tag, 60)][:limit]
    traits = [clean(trait, 30) for trait in (raw.get("traits") or []) if clean(trait, 30)][:6]
    ident = clean(raw.get("id"), 120) or f"{cat}.{slug(name)}"
    return {"id": ident, "name": name, "cat": cat, "sub": clean(raw.get("sub"), 60),
            "lead": lead, "parts": parts, "tags": tags, "traits": traits,
            "custom": custom,
            # a recipe saved whole: strength does not shorten it
            "fixed": bool(custom and raw.get("fixed") is True)}


def _load():
    taxonomy = read_json(os.path.join(SHIPPED, "_taxonomy.json"), {})
    cats = [{"id": cat["id"], "name": cat["name"], "subs": list(cat.get("subs") or [])}
            for cat in taxonomy.get("categories") or [] if isinstance(cat, dict) and cat.get("id")]
    styles, seen, names = [], set(), set()

    def add(entry):
        key = entry["name"].lower()
        if entry["id"] in seen or key in names:
            return
        seen.add(entry["id"])
        names.add(key)
        styles.append(entry)

    for cat in cats:
        data = read_json(os.path.join(SHIPPED, f"{cat['id']}.json"), {})
        for raw in (data.get("styles") if isinstance(data, dict) else None) or []:
            entry = _style(raw, cat["id"])
            if entry:
                add(entry)
    custom = read_json(CUSTOM, [])
    for raw in (custom if isinstance(custom, list) else [])[:MAX_CUSTOM]:
        entry = _style(raw, CUSTOM_CAT, custom=True)
        if entry:
            entry["id"] = f"{CUSTOM_CAT}.{slug(entry['name'])}"
            add(entry)

    mods = {kind: [] for kind in MOD_KINDS}
    data = read_json(os.path.join(SHIPPED, "modifiers.json"), {})
    taken = {kind: set() for kind in MOD_KINDS}
    for raw in (data.get("modifiers") if isinstance(data, dict) else None) or []:
        if not isinstance(raw, dict) or raw.get("kind") not in mods:
            continue
        name, phrase = clean_name(raw.get("name")), clean(raw.get("nl"), 160)
        if not name or not phrase or name.lower() in taken[raw["kind"]]:
            continue
        taken[raw["kind"]].add(name.lower())
        mods[raw["kind"]].append({"name": name, "nl": phrase, "tags": [
            clean(tag, 60) for tag in (raw.get("tags") or []) if clean(tag, 60)][:4]})
    for kind in mods:
        mods[kind].sort(key=lambda entry: entry["name"].lower())

    if any(entry["custom"] for entry in styles):
        cats = cats + [{"id": CUSTOM_CAT, "name": "My Styles", "subs": sorted(
            {entry["sub"] for entry in styles if entry["custom"] and entry["sub"]})}]
    stamp = _stamp()
    return {
        "cats": cats,
        "traits": [clean(trait, 30) for trait in taxonomy.get("traits") or []],
        "styles": styles,
        "by_id": {entry["id"]: entry for entry in styles},
        "by_name": {entry["name"].lower(): entry for entry in styles},
        "mods": mods,
        "mod_index": {kind: {entry["name"].lower(): entry for entry in mods[kind]}
                      for kind in mods},
        "signature": hashlib.sha1(repr(stamp).encode("utf-8")).hexdigest()[:16],
    }


def catalog():
    stamp = _stamp()
    with _lock:
        if _cache["stamp"] != stamp:
            _cache.update(stamp=stamp, data=_load())
        return _cache["data"]


def signature():
    return catalog()["signature"]


def resolve(text):
    """A style by id or by name; None when there is no such style."""
    data = catalog()
    text = clean(text, 160)
    if not text:
        return None
    return data["by_id"].get(text) or data["by_name"].get(text.lower())


def modifier(kind, name):
    if name in (None, "", NONE, RANDOM):
        return None
    return catalog()["mod_index"].get(kind, {}).get(str(name).lower())


def modifier_names(kind):
    return [entry["name"] for entry in catalog()["mods"].get(kind, [])]


def payload():
    """The catalog as the browser reads it: arrays, so 3,000 styles stay small."""
    data = catalog()
    cat_index = {cat["id"]: index for index, cat in enumerate(data["cats"])}
    trait_index = {trait: index for index, trait in enumerate(data["traits"])}
    rows = []
    for entry in data["styles"]:
        cat = data["cats"][cat_index[entry["cat"]]] if entry["cat"] in cat_index else None
        sub = cat["subs"].index(entry["sub"]) if cat and entry["sub"] in cat["subs"] else -1
        rows.append([entry["id"], entry["name"], cat_index.get(entry["cat"], -1), sub,
                     entry["lead"], entry["parts"], entry["tags"],
                     [trait_index[trait] for trait in entry["traits"] if trait in trait_index]])
    return {"signature": data["signature"], "cats": data["cats"], "traits": data["traits"],
            "styles": rows,
            "mods": {kind: [[entry["name"], entry["nl"]] for entry in data["mods"][kind]]
                     for kind in MOD_KINDS}}


# ------------------------------------------------------------ user state

def _blank():
    return {"favourites": [], "recents": [], "collections": {}}


def state():
    try:
        info = os.stat(STATE)
        stamp = (info.st_mtime_ns, info.st_size)
    except OSError:
        stamp = None
    with _lock:
        if _state["stamp"] != stamp or _state["data"] is None:
            raw = read_json(STATE, {})
            raw = raw if isinstance(raw, dict) else {}
            data = _blank()
            # a hand-edited or half-written file must read as empty, never raise

            def strings(value):
                return [item for item in value if isinstance(item, str)] if isinstance(
                    value, list) else []

            data["favourites"] = strings(raw.get("favourites"))[:20000]
            data["recents"] = strings(raw.get("recents"))[:MAX_RECENT]
            for name, ids in (raw.get("collections") or {}).items() if isinstance(
                    raw.get("collections"), dict) else []:
                name = clean_name(name)
                if name and isinstance(ids, list) and len(data["collections"]) < MAX_COLLECTIONS:
                    data["collections"][name] = [str(item) for item in ids
                                                 if isinstance(item, str)][:MAX_COLLECTION]
            _state.update(stamp=stamp, data=data)
        return _state["data"]


def _save_state(data):
    with _lock:
        write_json(STATE, data)
        _state.update(stamp=None, data=None)


def set_favourite(ident, on=None):
    entry = resolve(ident)
    if not entry:
        return None
    with _lock:
        data = json.loads(json.dumps(state()))
        has = entry["id"] in data["favourites"]
        want = (not has) if on is None else bool(on)
        if want and not has:
            data["favourites"].append(entry["id"])
        elif not want and has:
            data["favourites"].remove(entry["id"])
        _save_state(data)
    return want


def push_recent(ident):
    with _lock:
        data = state()
        if data["recents"][:1] == [ident]:
            return
        data = json.loads(json.dumps(data))
        data["recents"] = ([ident] + [item for item in data["recents"] if item != ident])[:MAX_RECENT]
        _save_state(data)


def clear_recents():
    with _lock:
        data = json.loads(json.dumps(state()))
        data["recents"] = []
        _save_state(data)


def collection_edit(name, ident=None, on=True, delete=False, rename=None):
    """Create, fill, rename or delete a collection. Returns an error string or ''."""
    name = clean_name(name)
    if not name:
        return "Give the collection a name."
    with _lock:
        data = json.loads(json.dumps(state()))
        cols = data["collections"]
        match = next((key for key in cols if key.lower() == name.lower()), None)
        if delete:
            if match:
                del cols[match]
                _save_state(data)
            return ""
        if rename is not None:
            new = clean_name(rename)
            if not match or not new:
                return "No such collection, or no new name."
            if any(key.lower() == new.lower() and key != match for key in cols):
                return "A collection already has that name."
            cols[new] = cols.pop(match)
            _save_state(data)
            return ""
        if not match:
            if len(cols) >= MAX_COLLECTIONS:
                return f"At most {MAX_COLLECTIONS} collections."
            match = name
            cols[match] = []
        if ident is not None:
            entry = resolve(ident)
            if not entry:
                return "No such style."
            if on and entry["id"] not in cols[match]:
                if len(cols[match]) >= MAX_COLLECTION:
                    return "That collection is full."
                cols[match].append(entry["id"])
            elif not on and entry["id"] in cols[match]:
                cols[match].remove(entry["id"])
        _save_state(data)
    return ""


# -------------------------------------------------------------- previews

def preview_file(ident):
    """Where a style's preview lives. Built from a slug, so no input can
    name a path: the result is always directly inside the previews folder."""
    name = slug(ident)
    return os.path.join(PREVIEWS, f"{name}.jpg") if name else None


def previews():
    """{style id: stamp} for every style that has a preview."""
    try:
        info = os.stat(PREVIEWS)
        stamp = info.st_mtime_ns
    except OSError:
        return {}
    with _lock:
        if _previews["stamp"] != stamp:
            found = {}
            try:
                with os.scandir(PREVIEWS) as listing:
                    for item in listing:
                        if item.is_file() and item.name.endswith(".jpg"):
                            found[item.name[:-4]] = int(item.stat().st_mtime)
            except OSError:
                found = {}
            _previews.update(stamp=stamp, data=found)
        slugs = _previews["data"]
    return {entry["id"]: slugs[slug(entry["id"])] for entry in catalog()["styles"]
            if slug(entry["id"]) in slugs}


def has_preview(ident):
    path = preview_file(ident)
    return bool(path and os.path.isfile(path))


def save_preview(ident, raw):
    """Store *raw* image bytes as the style's preview. Returns the stamp or None."""
    entry = resolve(ident)
    if not entry or not isinstance(raw, (bytes, bytearray)) or len(raw) > MAX_IMAGE_BYTES:
        return None
    try:
        from PIL import Image

        image = Image.open(io.BytesIO(bytes(raw)))
        image = image.convert("RGB")
        image.thumbnail((PREVIEW_SIZE, PREVIEW_SIZE), Image.LANCZOS)
        buffer = io.BytesIO()
        image.save(buffer, "JPEG", quality=88, optimize=True, progressive=True)
    except Exception:
        return None
    path = preview_file(entry["id"])
    with _lock:
        os.makedirs(PREVIEWS, exist_ok=True)
        temporary = f"{path}.{os.getpid()}.{threading.get_ident()}.tmp"
        with open(temporary, "wb") as handle:
            handle.write(buffer.getvalue())
        os.replace(temporary, path)
        drop_derived(path)
        _previews["stamp"] = None
        _claimed.discard(entry["id"])
    return int(time.time())


def delete_preview(ident):
    entry = resolve(ident)
    path = preview_file(entry["id"]) if entry else None
    if not path or not os.path.isfile(path):
        return False
    with _lock:
        try:
            os.remove(path)
        except OSError:
            return False
        drop_derived(path)
        _previews["stamp"] = None
    return True


def preview_path(ident, size=None):
    entry = resolve(ident)
    path = preview_file(entry["id"]) if entry else None
    if not path or not os.path.isfile(path):
        return None
    return derived_thumb(path, size) if size else path


def adopt_v1_previews():
    """Once: give version 2 styles the previews their originals already have.

    Most version 2 styles are reworked from the original catalog, and
    styles_v2/_aliases.json records which. A gallery someone spent hours
    filling should not start empty here, so the first time the browser asks
    for its state each original's cover image is copied across. Copies only:
    the original gallery is never changed, and a style that already has a
    version 2 preview keeps it.
    """
    marker = os.path.join(USER, ".adopted")
    if os.path.isfile(marker):
        return 0
    copied = 0
    with _lock:
        try:
            from . import gallery

            aliases = read_json(os.path.join(SHIPPED, "_aliases.json"), {})
            records = gallery.manifest()
            folder = gallery.previews_dir()
            known = catalog()["by_id"]
            os.makedirs(PREVIEWS, exist_ok=True)
            for old, new in (aliases.items() if isinstance(aliases, dict) else []):
                record = records.get(gallery.safe(old))
                target = preview_file(new) if new in known else None
                if not record or not target or os.path.isfile(target):
                    continue
                source = os.path.join(folder, os.path.basename(str(record.get("cover") or "")))
                if os.path.isfile(source):
                    shutil.copyfile(source, target)
                    copied += 1
        except Exception:
            pass                  # a convenience; never a reason to fail a page
        try:
            os.makedirs(USER, exist_ok=True)
            with open(marker, "w", encoding="utf-8") as handle:
                handle.write(str(copied))
        except OSError:
            pass
        _previews["stamp"] = None
    return copied


def user_state():
    data = state()
    return {"favourites": data["favourites"], "recents": data["recents"],
            "collections": data["collections"], "previews": previews()}


# ---------------------------------------------------------- custom styles

def save_custom(raw, replace=None):
    """Add or update one of the user's own styles. Returns (entry, error)."""
    if not isinstance(raw, dict):
        return None, "Nothing to save."
    name = clean_name(raw.get("name"))
    lead = clean(raw.get("lead"), 120)
    parts = raw.get("parts")
    if isinstance(parts, str):
        parts = re.split(r"[,\n]", parts)
    parts = [clean(part, 100) for part in (parts or []) if clean(part, 100)][:MAX_OWN_PARTS]
    tags = raw.get("tags")
    if isinstance(tags, str):
        tags = re.split(r"[,\n]", tags)
    tags = [clean(tag, 60).replace(" ", "_") for tag in (tags or [])
            if clean(tag, 60)][:MAX_OWN_PARTS]
    if not name:
        return None, "Give the style a name."
    if not lead:
        return None, "Write the lead: the phrase that names the look."
    with _lock:
        current = read_json(CUSTOM, [])
        current = [item for item in current if isinstance(item, dict)] if isinstance(
            current, list) else []
        old = clean_name(replace).lower() if replace else None
        kept = [item for item in current if clean_name(item.get("name")).lower() != old]
        clash = resolve(name)
        if clash and not (clash["custom"] and old == clash["name"].lower()):
            return None, f"There is already a style called {clash['name']}."
        if len(kept) >= MAX_CUSTOM:
            return None, f"At most {MAX_CUSTOM} styles of your own."
        record = {"name": name, "sub": clean(raw.get("sub"), 60), "lead": lead, "parts": parts,
                  "fixed": raw.get("fixed") is True,
                  "tags": tags, "traits": [clean(t, 30) for t in (raw.get("traits") or [])
                                           if isinstance(t, str) and clean(t, 30)][:6]}
        kept.append(record)
        write_json(CUSTOM, kept)
        _cache["stamp"] = None
    return resolve(name), ""


def delete_custom(name):
    entry = resolve(name)
    if not entry or not entry["custom"]:
        return False
    with _lock:
        current = read_json(CUSTOM, [])
        kept = [item for item in current if isinstance(item, dict)
                and clean_name(item.get("name")).lower() != entry["name"].lower()]
        write_json(CUSTOM, kept)
        _cache["stamp"] = None
    delete_preview(entry["id"])
    return True


# ------------------------------------------------------------- selection

def parse(text):
    """The styles box: ``Name``, ``Name:0.6`` or a dice ``@scope``, comma-separated.

    Returns a list of (token, weight). Nothing here is resolved yet.
    """
    picks = []
    for chunk in re.split(r"[,\n|]", str(text or "")[:2000]):
        chunk = clean(chunk, 200)
        if not chunk:
            continue
        weight = 1.0
        found = re.match(r"^(.*?)\s*:\s*([0-9]*\.?[0-9]+)$", chunk)
        if found:
            chunk = found.group(1).strip()
            try:
                weight = max(0.1, min(2.0, float(found.group(2))))
            except ValueError:
                weight = 1.0
        if chunk:
            picks.append((chunk, weight))
        if len(picks) >= MAX_PICKS:
            break
    return picks


def scope_pool(scope):
    """The styles a dice may land on, and a note when the scope was empty."""
    data = catalog()
    styles = data["styles"]
    key = clean(scope, 80).lower()
    if key in ("", "all", "any", "random"):
        return styles, ""
    user = state()
    if key in ("favourites", "favorites", "fav"):
        wanted = set(user["favourites"])
        pool = [entry for entry in styles if entry["id"] in wanted]
        return (pool, "") if pool else (styles, "no favourites yet, rolled from everything")
    if key in ("recent", "recents"):
        wanted = set(user["recents"])
        pool = [entry for entry in styles if entry["id"] in wanted]
        return (pool, "") if pool else (styles, "nothing recent yet, rolled from everything")
    if key in ("preview", "with preview", "missing", "missing preview", "next"):
        have = previews()
        if key in ("preview", "with preview"):
            pool = [entry for entry in styles if entry["id"] in have]
            return (pool, "") if pool else (styles, "no previews yet, rolled from everything")
        pool = [entry for entry in styles if entry["id"] not in have]
        return (pool, "") if pool else (styles, "every style has a preview, rolled from everything")
    cat, _, sub = key.partition("/")
    by_cat = [entry for entry in styles if entry["cat"] == cat.strip()
              or next((c["name"].lower() for c in data["cats"] if c["id"] == entry["cat"]),
                      "") == cat.strip()]
    if by_cat:
        if sub.strip():
            narrowed = [entry for entry in by_cat if entry["sub"].lower() == sub.strip()]
            return (narrowed, "") if narrowed else (by_cat, f"no sub '{sub.strip()}', rolled the category")
        return by_cat, ""
    for name, ids in user["collections"].items():
        if name.lower() == key:
            wanted = set(ids)
            pool = [entry for entry in styles if entry["id"] in wanted]
            return (pool, "") if pool else (styles, f"collection '{name}' is empty, rolled from everything")
    return styles, f"no category or collection called '{clean(scope, 40)}', rolled from everything"


def pick(text, seed=0, claim=False):
    """Resolve the styles box. Returns (picks, notes): picks are (entry, weight)."""
    picks, notes, used = [], [], set()
    for index, (token, weight) in enumerate(parse(text)):
        if token.startswith("@"):
            scope = token[1:].strip()
            pool, note = scope_pool(scope)
            pool = [entry for entry in pool if entry["id"] not in used]
            if not pool:
                continue
            if scope.lower() == "next":
                # walk the catalog in order: the first style with no preview
                # that this session has not already handed out
                with _lock:
                    entry = next((item for item in pool if item["id"] not in _claimed), pool[0])
                    if claim:
                        _claimed.add(entry["id"])
            else:
                rng = random.Random(f"{int(seed)}:{index}") if seed else random.Random()
                entry = rng.choice(pool)
            if note:
                notes.append(note)
        else:
            entry = resolve(token)
            if not entry:
                notes.append(f"no style called '{clean(token, 60)}'")
                continue
        if entry["id"] in used:
            continue
        used.add(entry["id"])
        picks.append((entry, weight))
    return picks, notes


def has_dice(text):
    return any(token.startswith("@") for token, _weight in parse(text))


# --------------------------------------------------------------- compose

def _join(parts):
    out = ""
    for part in parts:
        part = clean(part, 20000).strip(",").strip()
        if not part:
            continue
        if not out:
            out = part
        elif re.search(r"[.!?;:,]$", out):
            out = f"{out} {part}"
        else:
            out = f"{out}, {part}"
    return out


def style_text(picks, strength="standard"):
    """The natural-language clause for one style or a blend of up to three."""
    picks = [(entry, weight) for entry, weight in picks if entry]
    if not picks:
        return ""
    if len(picks) == 1:
        entry, weight = picks[0]
        keep = max(1, min(len(entry["parts"]), round(STRENGTHS.get(strength, 4) * weight)))
        if entry.get("fixed"):
            keep = len(entry["parts"])
        return ", ".join([entry["lead"]] + entry["parts"][:keep])
    leads = [picks[0][0]["lead"]] + [_lower_first(entry["lead"]) for entry, _w in picks[1:]]
    head = f"{leads[0]} blended with {' and '.join(leads[1:])}"
    budget = MIX_BUDGET.get(strength, 6)
    total = sum(weight for _entry, weight in picks) or 1.0
    shares = [len(entry["parts"]) if entry.get("fixed")
              else max(1, min(len(entry["parts"]), round(budget * weight / total)))
              for entry, weight in picks]
    body, seen = [], set()
    for row in range(max(shares)):
        for (entry, _weight), share in zip(picks, shares):
            if row < share and row < len(entry["parts"]):
                part = entry["parts"][row]
                if part.lower() not in seen:
                    seen.add(part.lower())
                    body.append(part)
    return ", ".join([head] + body)


def style_tags(picks, strength="standard"):
    keep = {"light": 2, "standard": 4, "heavy": 8}.get(strength, 4)
    out, seen = [], set()
    for entry, weight in picks:
        for tag in entry["tags"][:len(entry["tags"]) if entry.get("fixed") else keep]:
            if tag in seen:
                continue
            seen.add(tag)
            text = escape(tag)
            out.append(f"({text}:{weight:.2f})" if abs(weight - 1.0) > 0.001 else text)
    return out


def compose(prompt="", picks=(), mods=(), strength="standard", output_as="natural language",
            position="before prompt", triggers=(), prefix=""):
    """Return ``(positive, style_text)``.

    *mods* is a list of modifier entries, already resolved, in display order.
    """
    picks = list(picks)
    mods = [entry for entry in mods if entry]
    natural = _join([style_text(picks, strength)] + [entry["nl"] for entry in mods])
    tags = style_tags(picks, strength)
    seen = set(tags)
    for entry in mods:
        for tag in entry["tags"]:
            if escape(tag) not in seen:
                seen.add(escape(tag))
                tags.append(escape(tag))
    tag_text = ", ".join(tags)
    if output_as == "tags":
        style = tag_text
    elif output_as == "natural language + tags":
        style = _join([natural, tag_text])
    else:
        style = natural
    prompt = clean(prompt, 20000) if "\n" not in str(prompt or "") else str(prompt).strip()
    order = [prompt, style] if position == "after prompt" else [style, prompt]
    # LoRA triggers lead whatever the style position: a trigger the model does
    # not meet early may as well not be there
    # written exactly as the LoRA node gives them: a trigger may carry its own
    # brackets or weight on purpose
    lead = ", ".join(str(term) for term in triggers or () if term)
    return _join([lead, clean(prefix, 4000)] + order), style
