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

import json
import os
import re
import threading
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
USER_DIR = os.path.join(ROOT, "user")
LORA_DIR = os.path.join(USER_DIR, "loras")
FAVOURITES_PATH = os.path.join(LORA_DIR, "favourites.json")
TRIGGERS_PATH = os.path.join(LORA_DIR, "triggers.json")
MAX_TRIGGER = 400

UNSORTED = "Unsorted"
MAX_SHOTS = 8
THUMB = 512

_LOCK = threading.RLock()
_CACHE = {"names": None, "at": 0.0}
CACHE_SECONDS = 20


# ----------------------------------------------------------------- helpers


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


def catalog(refresh=False):
    """Everything the browser needs: the LoRAs, their galleries and families."""
    rows = [entry(name) for name in names(refresh)]
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
    filename = f"{key}--{int(time.time() * 1000)}.jpg"
    with open(os.path.join(previews_dir(gallery), filename), "wb") as handle:
        handle.write(_to_jpeg(source))

    with _LOCK:
        data = read_json(manifest_path(gallery), {})
        data = data if isinstance(data, dict) else {}
        record = data.get(key) if isinstance(data.get(key), dict) else {}
        shots = [shot for shot in record.get("shots", []) if isinstance(shot, dict) and shot.get("file")]
        shots.append({"file": filename, "prompt": str(prompt or "")[:600], "ts": int(time.time())})
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
