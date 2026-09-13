"""Preview gallery: several shots per style, one cover, keyed on style id."""

import functools
import json
import os
import re
import threading
import uuid
import time
from io import BytesIO

from . import catalogs

ROOT = os.path.dirname(os.path.abspath(__file__))


# Previews belong to a catalog, so the location is resolved per call rather than
# fixed at import: switching catalogs must take effect immediately.
def previews_dir(cid=None):
    return catalogs.paths(cid)["previews"]


def manifest_path(cid=None):
    return catalogs.paths(cid)["manifest"]


LOG_PATH = os.path.join(ROOT, "user", "gallery_log.txt")

THUMB = 512
MAX_SHOTS = 8
EXTS = (".jpg", ".jpeg", ".png", ".webp")
_ADOPTED = set()  # catalogs whose loose files have been folded in



def shot_filename(directory, key):
    """A filename nothing else in this folder is using.

    The stamp alone was not enough: two images saved inside the same
    millisecond — a batch with auto-gallery on, or two nodes finishing together
    — produced the SAME name, so the second overwrote the first and the
    manifest ended up with two entries pointing at one file. Deleting it then
    emptied the record.
    """
    for _ in range(100):
        candidate = f"{key}--{int(time.time() * 1000)}-{uuid.uuid4().hex[:6]}.jpg"
        if not os.path.exists(os.path.join(directory, candidate)):
            return candidate
    return f"{key}--{uuid.uuid4().hex}.jpg"

def safe(text):
    return re.sub(r"[^A-Za-z0-9]+", "_", str(text or "").strip()).strip("_")[:140]


def key_for(style):
    """Storage key for a style entry, its name, or an id."""
    if isinstance(style, dict):
        return safe(style.get("id") or style.get("name"))
    name = str(style or "").strip()
    if not name or name == "None":
        return ""
    try:
        from .catalog import resolve
        entry = resolve(name)
    except Exception:
        entry = None
    return safe(entry["id"] if entry else name)


# One prompt per lock holder: load-mutate-save has to be atomic, otherwise two
# previews saved at the same moment each write the manifest they read and one
# of them disappears.
_MANIFEST_LOCK = threading.RLock()


def _locked(fn):
    """Serialise a function that reads and then rewrites the manifest."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        with _MANIFEST_LOCK:
            return fn(*args, **kwargs)

    return wrapper


def _load():
    data = {}
    if os.path.isfile(manifest_path()):
        try:
            with open(manifest_path(), "r", encoding="utf-8") as handle:
                loaded = json.load(handle)
            if isinstance(loaded, dict):
                data = loaded
        except (OSError, json.JSONDecodeError):
            data = {}
    return data


def _save(data):
    """Atomic manifest write. The scratch name is per-thread so two prompts
    finishing together cannot write the same temp file."""
    os.makedirs(previews_dir(), exist_ok=True)
    tmp = f"{manifest_path()}.{os.getpid()}.{threading.get_ident()}.tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    os.replace(tmp, manifest_path())


def _record(manifest, key):
    record = manifest.get(key)
    if not isinstance(record, dict):
        record = {}
    record.setdefault("name", "")
    record.setdefault("cover", "")
    record.setdefault("shots", [])
    return record


@_locked
def adopt_existing():
    """Fold loose preview files into the manifest once, matching on name."""
    current = catalogs.active()
    if current in _ADOPTED:
        return
    _ADOPTED.add(current)
    if not os.path.isdir(previews_dir()):
        return

    try:
        from .catalog import base_name, entries
        pool = entries()
        by_stem = {safe(entry["name"]): entry for entry in pool}
        by_base = {}
        for entry in pool:
            for variant in (base_name(entry["name"]), entry["name"].replace("[v2]", "").strip()):
                by_base.setdefault(safe(variant), entry)
    except Exception:
        by_stem, by_base = {}, {}

    def match(stem):
        if stem in by_stem:
            return by_stem[stem]
        if stem in by_base:
            return by_base[stem]
        parts = stem.split("_", 1)
        if len(parts) == 2 and parts[1] in by_base:
            return by_base[parts[1]]
        return None

    manifest = _load()
    known = {
        shot.get("file")
        for record in manifest.values()
        if isinstance(record, dict)
        for shot in record.get("shots", [])
    }
    changed = False
    for filename in sorted(os.listdir(previews_dir())):
        if not filename.lower().endswith(EXTS) or filename in known:
            continue
        stem = filename.split("--", 1)[0] if "--" in filename else os.path.splitext(filename)[0]
        entry = match(stem)
        key = safe(entry["id"]) if entry else stem
        record = _record(manifest, key)
        record["name"] = record["name"] or (entry["name"] if entry else stem.replace("_", " "))
        record["shots"].append({
            "file": filename,
            "prompt": "",
            "ts": int(os.path.getmtime(os.path.join(previews_dir(), filename))),
        })
        record["cover"] = record["cover"] or filename
        manifest[key] = record
        changed = True
    if changed:
        _save(manifest)


def signature(cid=None):
    """A cheap fingerprint of a catalog's gallery.

    Stat of the manifest file rather than a walk of it: the point is to let a
    poller ask "has anything changed?" without moving the whole manifest or
    touching every image on disk.
    """
    path = manifest_path(cid)
    try:
        stat = os.stat(path)
        return f"{int(stat.st_mtime_ns)}:{stat.st_size}"
    except OSError:
        return "0:0"


def manifest():
    adopt_existing()
    raw = _load()
    out = {}
    for key, record in raw.items():
        if not isinstance(record, dict):
            continue
        shots = [
            shot for shot in record.get("shots", [])
            if isinstance(shot, dict) and shot.get("file")
            and os.path.isfile(os.path.join(previews_dir(), shot["file"]))
        ]
        if not shots:
            continue
        files = {shot["file"] for shot in shots}
        cover = record.get("cover") if record.get("cover") in files else shots[-1]["file"]
        out[key] = {
            "name": record.get("name", ""),
            "cover": cover,
            "shots": shots,
            "count": len(shots),
            "mtime": max(int(shot.get("ts", 0)) for shot in shots),
        }
    return out


def has_shots(style):
    key = key_for(style)
    return bool(key) and key in manifest()


def shot_path(key, filename=None):
    key = safe(key)
    record = manifest().get(key)
    if not record:
        return None
    target = filename or record["cover"]
    if target not in {shot["file"] for shot in record["shots"]}:
        return None
    return os.path.join(previews_dir(), target)


def _to_pil(source):
    from PIL import Image

    if isinstance(source, (bytes, bytearray)):
        return Image.open(BytesIO(source)).convert("RGB")
    import numpy as np

    tensor = source.cpu() if hasattr(source, "cpu") else source
    array = np.asarray(tensor.numpy() if hasattr(tensor, "numpy") else tensor)
    if array.ndim == 4:
        array = array[0]
    if array.ndim == 3 and array.shape[0] in (1, 3, 4) and array.shape[-1] not in (1, 3, 4):
        array = array.transpose(1, 2, 0)
    if array.dtype != np.uint8:
        array = (array.clip(0, 1) * 255).astype("uint8")
    if array.ndim == 2:
        return Image.fromarray(array, "L").convert("RGB")
    if array.shape[-1] == 4:
        return Image.fromarray(array, "RGBA").convert("RGB")
    return Image.fromarray(array[:, :, :3], "RGB")


@_locked
def add_shot(style, source, prompt="", make_cover=True, max_shots=MAX_SHOTS):
    from PIL import Image

    key = key_for(style)
    if not key:
        return None
    name = style.get("name") if isinstance(style, dict) else str(style)

    image = _to_pil(source)
    image.thumbnail((THUMB, THUMB), Image.LANCZOS)
    canvas = Image.new("RGB", (THUMB, THUMB), (14, 15, 19))
    canvas.paste(image, ((THUMB - image.width) // 2, (THUMB - image.height) // 2))

    adopt_existing()
    os.makedirs(previews_dir(), exist_ok=True)
    filename = shot_filename(previews_dir(), key)
    canvas.save(os.path.join(previews_dir(), filename), "JPEG", quality=90, optimize=True)

    data = _load()
    record = _record(data, key)
    record["name"] = name or record["name"]
    record["shots"].append({"file": filename, "prompt": str(prompt or "")[:600], "ts": int(time.time())})
    while len(record["shots"]) > max(1, int(max_shots)):
        dropped = record["shots"].pop(0)
        if dropped.get("file") == record.get("cover"):
            record["cover"] = ""
        path = os.path.join(previews_dir(), dropped.get("file", ""))
        if dropped.get("file") and os.path.isfile(path):
            try:
                os.remove(path)
            except OSError:
                pass
    if make_cover or not record["cover"]:
        record["cover"] = filename
    data[key] = record
    _save(data)
    log(name or key, filename)
    return {"key": key, "file": filename, "record": record}


@_locked
def set_cover(key, filename):
    key = safe(key)
    data = _load()
    record = data.get(key)
    if not isinstance(record, dict) or filename not in {s.get("file") for s in record.get("shots", [])}:
        return False
    record["cover"] = filename
    data[key] = record
    _save(data)
    return True


@_locked
def delete_shot(key, filename):
    key = safe(key)
    data = _load()
    record = data.get(key)
    if not isinstance(record, dict):
        return False
    shots = [shot for shot in record.get("shots", []) if shot.get("file") != filename]
    if len(shots) == len(record.get("shots", [])):
        return False
    path = os.path.join(previews_dir(), filename)
    if os.path.isfile(path):
        try:
            os.remove(path)
        except OSError:
            pass
    record["shots"] = shots
    if record.get("cover") == filename:
        record["cover"] = shots[-1]["file"] if shots else ""
    if shots:
        data[key] = record
    else:
        data.pop(key, None)
    _save(data)
    return True


@_locked
def delete_style(style):
    key = key_for(style) or safe(style)
    data = _load()
    record = data.pop(key, None)
    removed = False
    if isinstance(record, dict):
        for shot in record.get("shots", []):
            path = os.path.join(previews_dir(), shot.get("file", ""))
            if shot.get("file") and os.path.isfile(path):
                try:
                    os.remove(path)
                    removed = True
                except OSError:
                    pass
        _save(data)
    return removed


def delete_many(names):
    return sum(1 for name in names or [] if delete_style(name))


def log(style, filename):
    from datetime import datetime

    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    line = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  {style}  ->  {filename}"
    with open(LOG_PATH, "a", encoding="utf-8") as handle:
        handle.write(line + "\n")
    return line


