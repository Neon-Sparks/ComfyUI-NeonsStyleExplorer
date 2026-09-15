"""LoRAs, grouped by the folders they are filed in.

The list comes from ComfyUI itself, so whatever is in your `loras` folder is
what appears. The folders carry the meaning:

    loras/krea 2/portrait_v3.safetensors            gallery "krea 2"
    loras/krea 2/portraits/soft_light.safetensors   gallery "krea 2", family "portraits"
    loras/loose_one.safetensors                     gallery "Unsorted"

Each gallery keeps its own previews, so the same LoRA filed under two model
folders has two separate sets of images — which is the point: a LoRA behaves
differently on different checkpoints and you want to see both.

Nothing here writes to the loras folder. Previews and favourites live under
`user/loras/`, alongside everything else the node stores.
"""

import hashlib
import json
import os
import re
import threading
import uuid
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
USER_DIR = os.path.join(ROOT, "user")
LORA_DIR = os.path.join(USER_DIR, "loras")
FAVOURITES_PATH = os.path.join(LORA_DIR, "favourites.json")
TRIGGERS_PATH = os.path.join(LORA_DIR, "triggers.json")
FINGERPRINTS_PATH = os.path.join(LORA_DIR, "fingerprints.json")
# how much of a file is read to identify it: enough to be unique in practice,
# little enough that scanning hundreds of LoRAs costs nothing noticeable
FINGERPRINT_BYTES = 1 << 20
MAX_TRIGGER = 400

UNSORTED = "Unsorted"
MAX_SHOTS = 8
THUMB = 512

_LOCK = threading.RLock()
_CACHE = {"names": None, "at": 0.0}
CACHE_SECONDS = 20


# ----------------------------------------------------------------- helpers



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

def slug(text):
    return re.sub(r"[^A-Za-z0-9]+", "_", str(text or "").strip()).strip("_")[:140]


def read_json(path, default):
    if not os.path.isfile(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return default


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.{os.getpid()}.{threading.get_ident()}.tmp"
    with _LOCK:
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        os.replace(tmp, path)


# ------------------------------------------------------------------- list


def names(refresh=False):
    """Every LoRA ComfyUI can see, as forward-slashed relative paths."""
    now = time.time()
    if not refresh and _CACHE["names"] is not None and now - _CACHE["at"] < CACHE_SECONDS:
        return _CACHE["names"]
    found = []
    try:
        import folder_paths

        found = list(folder_paths.get_filename_list("loras"))
    except Exception:
        found = []
    found = sorted({str(name).replace("\\", "/") for name in found if name})
    _CACHE["names"], _CACHE["at"] = found, now
    return found


def _full_path(name):
    try:
        import folder_paths

        return folder_paths.get_full_path("loras", name)
    except Exception:
        return None


def fingerprint(name):
    """A stable identity for a LoRA file: its size plus its first and last MiB.

    Previews used to be filed under the LoRA's PATH, which made a move look like
    a deletion and made a new file dropped into the old path inherit the old
    previews. A fingerprint follows the file instead: rename it, move it between
    folders, and its gallery follows; replace it with a different file and the
    previews stay with the original.
    """
    path = _full_path(name)
    if not path or not os.path.isfile(path):
        return ""
    try:
        size = os.path.getsize(path)
        stamp = int(os.path.getmtime(path))
    except OSError:
        return ""

    cached = read_json(FINGERPRINTS_PATH, {})
    cached = cached if isinstance(cached, dict) else {}
    record = cached.get(str(name))
    if isinstance(record, dict) and record.get("size") == size and record.get("mtime") == stamp:
        return str(record.get("fingerprint") or "")

    digest = hashlib.sha1()
    digest.update(str(size).encode("ascii"))
    try:
        with open(path, "rb") as handle:
            digest.update(handle.read(FINGERPRINT_BYTES))
            if size > FINGERPRINT_BYTES * 2:
                handle.seek(-FINGERPRINT_BYTES, os.SEEK_END)
                digest.update(handle.read(FINGERPRINT_BYTES))
    except OSError:
        return ""
    value = digest.hexdigest()
    with _LOCK:
        cached = read_json(FINGERPRINTS_PATH, {})
        cached = cached if isinstance(cached, dict) else {}
        cached[str(name)] = {"size": size, "mtime": stamp, "fingerprint": value}
        # forget files that are no longer there, so the file cannot grow forever
        live = set(names())
        cached = {k: v for k, v in cached.items() if k in live}
        write_json(FINGERPRINTS_PATH, cached)
    return value


def split(name):
    """(gallery, family, label) for a LoRA path."""
    parts = [part for part in str(name or "").replace("\\", "/").split("/") if part]
    if not parts:
        return UNSORTED, "", ""
    filename = parts[-1]
    label = re.sub(r"\.(safetensors|ckpt|pt|bin|lora)$", "", filename, flags=re.I)
    if len(parts) == 1:
        return UNSORTED, "", label
    if len(parts) == 2:
        return parts[0], "", label
    return parts[0], parts[1], label


def entry(name):
    gallery, family, label = split(name)
    return {
        "name": name,
        "label": label,
        "gallery": gallery,
        "family": family,
        "key": slug(name),
        "favourite": is_favourite(name),
        "triggers": triggers_for(name),
    }


def load_triggers():
    """The words each LoRA wants in the prompt, keyed by its path."""
    data = read_json(TRIGGERS_PATH, {})
    return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}


def triggers_for(name):
    return load_triggers().get(str(name or "").replace("\\", "/"), "")


def set_triggers(name, text):
    """Record (or clear) a LoRA's trigger words."""
    name = str(name or "").replace("\\", "/")
    if not name:
        return ""
    text = re.sub(r"\s+", " ", str(text or "")).strip()[:MAX_TRIGGER]
    with _LOCK:
        current = load_triggers()
        if text:
            current[name] = text
        else:
            current.pop(name, None)
        write_json(TRIGGERS_PATH, current)
    return text


def reconcile(live=None):
    """Follow LoRAs that moved, and detach previews from files that were replaced.

    Records carry the fingerprint of the file they were saved against. Three
    cases matter, and all three used to be wrong:

    * the LoRA moved or was renamed — its record is re-keyed to the new path,
      and moved into the new top folder's gallery if that changed;
    * a different file now sits at a path we have previews for — the record is
      parked under its fingerprint instead of handed to the new file;
    * the LoRA is simply gone — its record is left alone, so putting the file
      back restores its gallery.
    """
    live = list(live if live is not None else names(True))
    by_print = {}
    for name in live:
        value = fingerprint(name)
        if value:
            by_print.setdefault(value, name)

    moved, detached = [], []
    with _LOCK:
        for gallery in _galleries_on_disk():
            data = read_json(manifest_path(gallery), {})
            if not isinstance(data, dict) or not data:
                continue
            changed = False
            for key, record in list(data.items()):
                if not isinstance(record, dict):
                    continue
                stored = str(record.get("fingerprint") or "")
                # 'lora' is the path; 'name' is only the label shown on a card
                path = str(record.get("lora") or "")
                if not stored:
                    continue                       # saved before fingerprints; leave it
                now_here = fingerprint(path) if path in live else ""
                if now_here == stored:
                    continue                       # still the same file: nothing to do
                target = by_print.get(stored)
                if target and target != path:
                    # the file moved: take the record with it
                    record["lora"] = target
                    record["name"] = split(target)[2]
                    data.pop(key)
                    _place(record, target, gallery)
                    moved.append((path, target))
                    changed = True
                elif now_here and now_here != stored:
                    # a different file is at that path now
                    record["detached"] = True
                    data.pop(key)
                    data[f"{key}--was-{stored[:8]}"] = record
                    detached.append(path)
                    changed = True
            if changed:
                write_json(manifest_path(gallery), data)

    # triggers follow the file too
    if moved:
        with _LOCK:
            triggers = load_triggers()
            for old, new in moved:
                if old in triggers and new not in triggers:
                    triggers[new] = triggers.pop(old)
            write_json(TRIGGERS_PATH, triggers)
            favourites = load_favourites()
            for old, new in moved:
                if old in favourites:
                    favourites = [new if item == old else item for item in favourites]
            write_json(FAVOURITES_PATH, favourites)
    return {"moved": moved, "detached": detached}


def _galleries_on_disk():
    if not os.path.isdir(LORA_DIR):
        return []
    return [name for name in os.listdir(LORA_DIR)
            if os.path.isdir(os.path.join(LORA_DIR, name))]


def _place(record, name, from_gallery):
    """Write a record into the gallery its LoRA now belongs to."""
    gallery, _family, _label = split(name)
    key = slug(name)
    target = read_json(manifest_path(gallery), {})
    target = target if isinstance(target, dict) else {}
    target[key] = record
    os.makedirs(previews_dir(gallery), exist_ok=True)
    # the images live in the old gallery folder; carry them across
    if gallery != from_gallery:
        for shot in record.get("shots", []):
            source = os.path.join(previews_dir(from_gallery), shot.get("file", ""))
            if shot.get("file") and os.path.isfile(source):
                try:
                    os.replace(source, os.path.join(previews_dir(gallery), shot["file"]))
                except OSError:
                    pass
    write_json(manifest_path(gallery), target)


def catalog(refresh=False):
    """Everything the browser needs: the LoRAs, their galleries and families."""
    live = names(refresh)
    fixed = reconcile(live) if refresh else {"moved": [], "detached": []}
    rows = [entry(name) for name in live]
    galleries = {}
    for row in rows:
        bucket = galleries.setdefault(row["gallery"], {"name": row["gallery"], "count": 0, "families": []})
        bucket["count"] += 1
        if row["family"] and row["family"] not in bucket["families"]:
            bucket["families"].append(row["family"])
    for bucket in galleries.values():
        bucket["families"].sort()
    order = sorted(galleries, key=lambda name: (name == UNSORTED, name.lower()))
    return {
        "loras": rows,
        "galleries": [galleries[name] for name in order],
        "favourites": load_favourites(),
        "triggers": load_triggers(),
        "count": len(rows),
        "moved": [{"from": old, "to": new} for old, new in fixed["moved"]],
        "detached": fixed["detached"],
    }


# -------------------------------------------------------------- favourites


def load_favourites():
    data = read_json(FAVOURITES_PATH, [])
    return [str(item) for item in data if str(item).strip()] if isinstance(data, list) else []


def is_favourite(name):
    return str(name) in set(load_favourites())


def set_favourite(name, on=True):
    name = str(name or "").replace("\\", "/")
    if not name:
        return False
    with _LOCK:
        current = load_favourites()
        if on and name not in current:
            current.append(name)
        elif not on:
            current = [item for item in current if item != name]
        write_json(FAVOURITES_PATH, current)
    return bool(on)


def toggle_favourite(name):
    return set_favourite(name, not is_favourite(name))


# ----------------------------------------------------------------- gallery


def gallery_dir(gallery):
    """Where one gallery's previews live. Named for the folder, kept as a slug
    because a folder name is not a safe path component."""
    return os.path.join(LORA_DIR, slug(gallery) or "unsorted")


def manifest_path(gallery):
    return os.path.join(gallery_dir(gallery), "manifest.json")


def previews_dir(gallery):
    return os.path.join(gallery_dir(gallery), "previews")


def manifest(gallery):
    data = read_json(manifest_path(gallery), {})
    if not isinstance(data, dict):
        return {}
    out = {}
    for key, record in data.items():
        if not isinstance(record, dict):
            continue
        shots = [shot for shot in record.get("shots", [])
                 if isinstance(shot, dict) and shot.get("file")
                 and os.path.isfile(os.path.join(previews_dir(gallery), shot["file"]))]
        if not shots:
            continue
        cover = record.get("cover") if record.get("cover") in {s["file"] for s in shots} else shots[-1]["file"]
        out[key] = {"shots": shots, "cover": cover, "count": len(shots),
                    "lora": record.get("lora", ""), "name": record.get("name", "")}
    return out


def all_manifests():
    """Every gallery's manifest, keyed by gallery name."""
    return {bucket["name"]: manifest(bucket["name"]) for bucket in catalog()["galleries"]}


def shot_path(gallery, key, filename=None):
    record = manifest(gallery).get(slug(key))
    if not record:
        return None
    target = filename or record["cover"]
    if target not in {shot["file"] for shot in record["shots"]}:
        return None
    return os.path.join(previews_dir(gallery), target)


def _to_jpeg(source):
    """Accept a torch/numpy image batch or raw bytes; return JPEG bytes."""
    from io import BytesIO

    from PIL import Image

    if isinstance(source, (bytes, bytearray)):
        image = Image.open(BytesIO(bytes(source))).convert("RGB")
    else:
        import numpy as np

        tensor = source[0] if hasattr(source, "__len__") and len(source) and hasattr(source[0], "shape") else source
        array = np.asarray(tensor.numpy() if hasattr(tensor, "numpy") else tensor)
        if array.ndim == 4:
            array = array[0]
        image = Image.fromarray((array.clip(0, 1) * 255).astype("uint8"))
    image.thumbnail((THUMB, THUMB))
    buffer = BytesIO()
    image.save(buffer, "JPEG", quality=90, optimize=True)
    return buffer.getvalue()


def add_shot(name, source, prompt="", make_cover=True):
    """Save an image against a LoRA, in that LoRA's own gallery."""
    gallery, _family, _label = split(name)
    key = slug(name)
    if not key:
        return None
    os.makedirs(previews_dir(gallery), exist_ok=True)
    filename = shot_filename(previews_dir(gallery), key)
    with open(os.path.join(previews_dir(gallery), filename), "wb") as handle:
        handle.write(_to_jpeg(source))

    with _LOCK:
        data = read_json(manifest_path(gallery), {})
        data = data if isinstance(data, dict) else {}
        record = data.get(key) if isinstance(data.get(key), dict) else {}
        shots = [shot for shot in record.get("shots", []) if isinstance(shot, dict) and shot.get("file")]
        shots.append({"file": filename, "prompt": str(prompt or "")[:600], "ts": int(time.time())})
        record["fingerprint"] = fingerprint(name)
        while len(shots) > MAX_SHOTS:
            dropped = shots.pop(0)
            stale = os.path.join(previews_dir(gallery), dropped.get("file", ""))
            if os.path.isfile(stale):
                os.remove(stale)
            if record.get("cover") == dropped.get("file"):
                record["cover"] = ""
        record.update({"shots": shots, "lora": name, "name": split(name)[2]})
        if make_cover or not record.get("cover"):
            record["cover"] = filename
        data[key] = record
        write_json(manifest_path(gallery), data)
    return {"gallery": gallery, "key": key, "file": filename,
            "record": {"shots": shots, "cover": record["cover"], "count": len(shots),
                       "lora": name, "name": split(name)[2]}}


def set_cover(gallery, key, filename):
    with _LOCK:
        data = read_json(manifest_path(gallery), {})
        record = data.get(slug(key)) if isinstance(data, dict) else None
        if not isinstance(record, dict):
            return False
        if filename not in {shot.get("file") for shot in record.get("shots", [])}:
            return False
        record["cover"] = filename
        write_json(manifest_path(gallery), data)
    return True


def delete_shot(gallery, key, filename):
    with _LOCK:
        data = read_json(manifest_path(gallery), {})
        record = data.get(slug(key)) if isinstance(data, dict) else None
        if not isinstance(record, dict):
            return False
        kept = [shot for shot in record.get("shots", []) if shot.get("file") != filename]
        if len(kept) == len(record.get("shots", [])):
            return False
        stale = os.path.join(previews_dir(gallery), filename)
        if os.path.isfile(stale):
            os.remove(stale)
        if kept:
            record["shots"] = kept
            if record.get("cover") == filename:
                record["cover"] = kept[-1]["file"]
        else:
            data.pop(slug(key), None)
        write_json(manifest_path(gallery), data)
    return True


def delete_lora_shots(name):
    """Every image for one LoRA in its own gallery."""
    gallery, _family, _label = split(name)
    key = slug(name)
    with _LOCK:
        data = read_json(manifest_path(gallery), {})
        record = data.pop(key, None) if isinstance(data, dict) else None
        if not isinstance(record, dict):
            return 0
        gone = 0
        for shot in record.get("shots", []):
            stale = os.path.join(previews_dir(gallery), shot.get("file", ""))
            if os.path.isfile(stale):
                os.remove(stale)
                gone += 1
        write_json(manifest_path(gallery), data)
    return gone
