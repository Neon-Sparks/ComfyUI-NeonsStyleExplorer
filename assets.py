"""One gallery engine, used by the LoRA and checkpoint explorers.

Both nodes want the same thing: a picker grouped by the folders the files
already live in, a preview gallery per top-level folder, favourites, a short
piece of text per file, and previews that follow a file when it moves. Writing
that twice is how two copies drift apart, so it lives here once and each module
supplies only what differs — which folder list to read, where to keep its data,
and what its text field is called.
"""

import hashlib
import io
import json
import os
import re
import threading
import time
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
USER_DIR = os.path.join(HERE, "user")

UNSORTED = "Unsorted"
MAX_SHOTS = 8
MAX_TEXT = 400
THUMB = 512
# how much of a file is read to identify it: enough to be unique in practice,
# little enough that scanning hundreds of files costs nothing noticeable
FINGERPRINT_BYTES = 1 << 20
CACHE_SECONDS = 20


# Cards render at about 190px and the stored preview is 512px, so serving the
# master to a grid ships roughly seven times the pixels a card can show. These
# are derived on first request and cached beside the original; the master is
# still served to the node's panel and to a zoomed-in card.
THUMB_SIZES = (256, 384)
THUMB_QUALITY = 85


def derived_thumb(path, size):
    """A cached, card-sized copy of a preview. Falls back to the original."""
    try:
        size = int(size)
    except (TypeError, ValueError):
        return path
    if size not in THUMB_SIZES or not path or not os.path.isfile(path):
        return path
    folder = os.path.join(os.path.dirname(path), "thumbs")
    stem = os.path.splitext(os.path.basename(path))[0]
    target = os.path.join(folder, f"{stem}.{size}.jpg")
    try:
        if os.path.isfile(target) and os.path.getmtime(target) >= os.path.getmtime(path):
            return target
        from PIL import Image

        os.makedirs(folder, exist_ok=True)
        with Image.open(path) as image:
            image = image.convert("RGB")
            image.thumbnail((size, size), Image.LANCZOS)
            temporary = f"{target}.tmp"
            image.save(temporary, "JPEG", quality=THUMB_QUALITY, optimize=True,
                       progressive=True)
        os.replace(temporary, target)
        return target
    except Exception:
        # a thumbnail is an optimisation; never fail a page over one
        return path


def build_derived(paths):
    """Make every cached size for a list of previews, reporting what it did.

    Only useful after updating from a version that had no cached sizes: from
    then on they are made as images are first shown. Running it is safe at any
    time — anything already built is skipped.
    """
    built = skipped = 0
    for path in paths:
        for size in THUMB_SIZES:
            before = os.path.isfile(os.path.join(
                os.path.dirname(path), "thumbs",
                f"{os.path.splitext(os.path.basename(path))[0]}.{size}.jpg"))
            derived_thumb(path, size)
            if before:
                skipped += 1
            else:
                built += 1
    return {"built": built, "skipped": skipped, "previews": len(paths)}


def drop_derived(path):
    """Remove the cached sizes of a preview that has been deleted."""
    folder = os.path.join(os.path.dirname(path), "thumbs")
    stem = os.path.splitext(os.path.basename(path))[0]
    for size in THUMB_SIZES:
        stale = os.path.join(folder, f"{stem}.{size}.jpg")
        if os.path.isfile(stale):
            try:
                os.remove(stale)
            except OSError:
                pass


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
    temporary = f"{path}.tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=1, ensure_ascii=False)
    os.replace(temporary, path)


class Gallery:
    """The preview gallery for one kind of asset."""

    def __init__(self, kind, folder_key, storage, text_field):
        """folder_key is one ComfyUI folder name, or several.

        With several — checkpoints and diffusion_models, say — every name is
        prefixed with the folder it came from, so `diffusion_models/flux/x.sft`
        and `checkpoints/flux/x.sft` are different assets with different
        previews, and the browser's gallery dropdown becomes the switch between
        the two sources.
        """
        self.kind = kind                 # "lora" / "model", for messages
        self.folder_keys = ((folder_key,) if isinstance(folder_key, str)
                            else tuple(folder_key))
        self.multi = len(self.folder_keys) > 1
        self.folder_key = self.folder_keys[0]
        self.root = os.path.join(USER_DIR, storage)
        self.text_field = text_field     # "triggers" / "notes"
        self.favourites_path = os.path.join(self.root, "favourites.json")
        self.text_path = os.path.join(self.root, f"{text_field}.json")
        self.fingerprints_path = os.path.join(self.root, "fingerprints.json")
        self._lock = threading.RLock()
        self._cache = {"names": None, "at": 0.0}
        self._built = {}          # manifest path -> (file signature, built)

    # ------------------------------------------------------------- listing

    def names(self, refresh=False):
        """Every file ComfyUI can see, as forward-slashed relative paths."""
        now = time.time()
        if not refresh and self._cache["names"] is not None \
                and now - self._cache["at"] < CACHE_SECONDS:
            return self._cache["names"]
        found = []
        try:
            import folder_paths

            for key in self.folder_keys:
                try:
                    listed = list(folder_paths.get_filename_list(key))
                except Exception:
                    listed = []
                for name in listed:
                    if not name:
                        continue
                    name = str(name).replace("\\", "/")
                    found.append(f"{key}/{name}" if self.multi else name)
        except Exception:
            found = []
        found = sorted(set(found))
        self._cache["names"], self._cache["at"] = found, now
        return found

    def source_of(self, name):
        """(folder key, path within it) for an asset name."""
        name = str(name or "").replace("\\", "/")
        if not self.multi:
            return self.folder_key, name
        for key in self.folder_keys:
            if name.startswith(f"{key}/"):
                return key, name[len(key) + 1:]
        return self.folder_key, name

    def full_path(self, name):
        key, relative = self.source_of(name)
        try:
            import folder_paths

            return folder_paths.get_full_path(key, relative)
        except Exception:
            return None

    @staticmethod
    def split(name):
        """(gallery, family, label) for a path."""
        parts = [part for part in str(name or "").replace("\\", "/").split("/") if part]
        if not parts:
            return UNSORTED, "", ""
        filename = parts[-1]
        label = re.sub(r"\.(safetensors|ckpt|pt|bin|lora|sft)$", "", filename, flags=re.I)
        if len(parts) == 1:
            return UNSORTED, "", label
        if len(parts) == 2:
            return parts[0], "", label
        return parts[0], parts[1], label

    # --------------------------------------------------------- identity

    def fingerprint(self, name):
        """A stable identity for a file: its size plus its first and last MiB.

        Previews used to be filed under the PATH, which made a move look like a
        deletion and let a new file dropped into the old path inherit the old
        previews. A fingerprint follows the file instead.
        """
        path = self.full_path(name)
        if not path or not os.path.isfile(path):
            return ""
        try:
            size = os.path.getsize(path)
            stamp = int(os.path.getmtime(path))
        except OSError:
            return ""

        cached = read_json(self.fingerprints_path, {})
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
        with self._lock:
            cached = read_json(self.fingerprints_path, {})
            cached = cached if isinstance(cached, dict) else {}
            cached[str(name)] = {"size": size, "mtime": stamp, "fingerprint": value}
            live = set(self.names())
            cached = {k: v for k, v in cached.items() if k in live}
            write_json(self.fingerprints_path, cached)
        return value

    def reconcile(self, live=None):
        """Follow files that moved; detach previews from files that were replaced."""
        live = list(live if live is not None else self.names(True))
        by_print = {}
        for name in live:
            value = self.fingerprint(name)
            if value:
                by_print.setdefault(value, name)

        moved, detached = [], []
        with self._lock:
            for gallery in self._galleries_on_disk():
                data = read_json(self.manifest_path(gallery), {})
                if not isinstance(data, dict) or not data:
                    continue
                changed = False
                for key, record in list(data.items()):
                    if not isinstance(record, dict):
                        continue
                    stored = str(record.get("fingerprint") or "")
                    path = str(record.get("asset") or record.get("lora") or "")
                    if not stored:
                        continue                  # saved before fingerprints
                    now_here = self.fingerprint(path) if path in live else ""
                    if now_here == stored:
                        continue
                    target = by_print.get(stored)
                    if target and target != path:
                        record["asset"] = target
                        record["lora"] = target   # older readers
                        record["name"] = self.split(target)[2]
                        data.pop(key)
                        self._place(record, target, gallery)
                        moved.append((path, target))
                        changed = True
                    elif now_here and now_here != stored:
                        record["detached"] = True
                        data.pop(key)
                        data[f"{key}--was-{stored[:8]}"] = record
                        detached.append(path)
                        changed = True
                if changed:
                    write_json(self.manifest_path(gallery), data)

        if moved:
            with self._lock:
                texts = self.load_text()
                for old, new in moved:
                    if old in texts and new not in texts:
                        texts[new] = texts.pop(old)
                write_json(self.text_path, texts)
                favourites = self.load_favourites()
                for old, new in moved:
                    favourites = [new if item == old else item for item in favourites]
                write_json(self.favourites_path, favourites)
        return {"moved": moved, "detached": detached}

    def _galleries_on_disk(self):
        if not os.path.isdir(self.root):
            return []
        return [name for name in os.listdir(self.root)
                if os.path.isdir(os.path.join(self.root, name))]

    def _place(self, record, name, from_gallery):
        gallery, _family, _label = self.split(name)
        target = read_json(self.manifest_path(gallery), {})
        target = target if isinstance(target, dict) else {}
        target[slug(name)] = record
        target[self.GALLERY_KEY] = gallery
        os.makedirs(self.previews_dir(gallery), exist_ok=True)
        if gallery != from_gallery:
            for shot in record.get("shots", []):
                source = os.path.join(self.previews_dir(from_gallery), shot.get("file", ""))
                if shot.get("file") and os.path.isfile(source):
                    try:
                        os.replace(source, os.path.join(self.previews_dir(gallery), shot["file"]))
                    except OSError:
                        pass
        write_json(self.manifest_path(gallery), target)

    # ------------------------------------------------------------- text

    def load_text(self):
        data = read_json(self.text_path, {})
        return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}

    def text_for(self, name):
        return self.load_text().get(str(name or "").replace("\\", "/"), "")

    def set_text(self, name, text):
        name = str(name or "").replace("\\", "/")
        if not name:
            return ""
        text = re.sub(r"\s+", " ", str(text or "")).strip()[:MAX_TEXT]
        with self._lock:
            current = self.load_text()
            if text:
                current[name] = text
            else:
                current.pop(name, None)
            write_json(self.text_path, current)
        return text

    # ------------------------------------------------------- favourites

    def load_favourites(self):
        data = read_json(self.favourites_path, [])
        return [str(item) for item in data if str(item).strip()] if isinstance(data, list) else []

    def is_favourite(self, name):
        return str(name) in set(self.load_favourites())

    def set_favourite(self, name, on=True):
        name = str(name or "")
        if not name:
            return False
        with self._lock:
            current = self.load_favourites()
            if on and name not in current:
                current.append(name)
            if not on:
                current = [item for item in current if item != name]
            write_json(self.favourites_path, current)
        return on

    def toggle_favourite(self, name):
        return self.set_favourite(name, not self.is_favourite(name))

    # --------------------------------------------------------- catalog

    def entry(self, name):
        gallery, family, label = self.split(name)
        source, _relative = self.source_of(name)
        return {
            "name": name,
            "source": source,
            "label": label,
            "gallery": gallery,
            "family": family,
            "key": slug(name),
            "favourite": self.is_favourite(name),
            self.text_field: self.text_for(name),
        }

    def catalog(self, refresh=False):
        live = self.names(refresh)
        fixed = self.reconcile(live) if refresh else {"moved": [], "detached": []}
        rows = [self.entry(name) for name in live]
        galleries = {}
        for row in rows:
            bucket = galleries.setdefault(row["gallery"],
                                          {"name": row["gallery"], "count": 0, "families": []})
            bucket["count"] += 1
            if row["family"] and row["family"] not in bucket["families"]:
                bucket["families"].append(row["family"])
        for bucket in galleries.values():
            bucket["families"].sort()
        order = sorted(galleries, key=lambda name: (name == UNSORTED, name.lower()))
        return {
            "assets": rows,
            "galleries": [galleries[name] for name in order],
            "favourites": self.load_favourites(),
            self.text_field: self.load_text(),
            "count": len(rows),
            "moved": [{"from": old, "to": new} for old, new in fixed["moved"]],
            "detached": fixed["detached"],
        }

    # --------------------------------------------------------- previews

    def gallery_dir(self, gallery):
        return os.path.join(self.root, slug(gallery) or UNSORTED)

    def manifest_path(self, gallery):
        return os.path.join(self.gallery_dir(gallery), "manifest.json")

    def previews_dir(self, gallery):
        return os.path.join(self.gallery_dir(gallery), "previews")

    # the folder a gallery lives in is slugged ("Qwen-Image 2.1" ->
    # "Qwen_Image_2_1"), so the real name is kept inside the manifest under
    # this key. Without it the browser asked for a gallery the server had
    # filed under a different name, and any folder containing a space, a dot
    # or a dash appeared to have no previews at all.
    GALLERY_KEY = "__gallery__"

    def real_gallery(self, directory):
        """The gallery name a manifest folder belongs to."""
        data = read_json(os.path.join(self.root, directory, "manifest.json"), {})
        if isinstance(data, dict):
            named = data.get(self.GALLERY_KEY)
            if isinstance(named, str) and named:
                return named
            # written before the name was stored: take it from any record
            for record in data.values():
                if isinstance(record, dict):
                    path = record.get("asset") or record.get("lora")
                    if path:
                        return self.split(path)[0]
        return directory

    def _signature(self, path, folder):
        try:
            stamp = os.stat(path)
        except OSError:
            return None
        try:
            folder_stamp = os.stat(folder).st_mtime_ns
        except OSError:
            folder_stamp = 0
        return (stamp.st_mtime_ns, stamp.st_size, folder_stamp)

    def manifest(self, gallery):
        path = self.manifest_path(gallery)
        signature = self._signature(path, self.previews_dir(gallery))
        cached = self._built.get(path)
        if cached and signature is not None and cached[0] == signature:
            return cached[1]      # treat as read-only
        data = read_json(path, {})
        if not isinstance(data, dict):
            return {}
        out = {}
        for key, record in data.items():
            if key == self.GALLERY_KEY or not isinstance(record, dict):
                continue
            shots = [shot for shot in record.get("shots", [])
                     if isinstance(shot, dict) and shot.get("file")]
            if not shots:
                continue
            cover = record.get("cover") if record.get("cover") in {s["file"] for s in shots} \
                else shots[-1]["file"]
            out[key] = {**record, "shots": shots, "cover": cover, "count": len(shots)}
        if signature is not None:
            self._built[path] = (signature, out)
        return out

    def all_manifests(self):
        """Every gallery's previews, keyed by the name the browser knows."""
        out = {}
        for directory in self._galleries_on_disk():
            name = self.real_gallery(directory)
            out[name] = self.manifest(name)
        return out

    def shot_path(self, gallery, key, filename=None):
        directory = self.previews_dir(gallery)
        if filename:
            candidate = os.path.join(directory, os.path.basename(filename))
            return candidate if os.path.isfile(candidate) else None
        record = self.manifest(gallery).get(slug(key))
        if not record:
            return None
        return os.path.join(directory, record["cover"])

    def shot_filename(self, directory, key):
        """A filename nothing else in this folder is using.

        The millisecond stamp alone collided when two images were saved inside
        the same millisecond: the second overwrote the first.
        """
        for _ in range(100):
            candidate = f"{key}--{int(time.time() * 1000)}-{uuid.uuid4().hex[:6]}.jpg"
            if not os.path.exists(os.path.join(directory, candidate)):
                return candidate
        return f"{key}--{uuid.uuid4().hex}.jpg"

    def to_jpeg(self, source):
        from PIL import Image

        if isinstance(source, (bytes, bytearray)):
            image = Image.open(io.BytesIO(bytes(source)))
        elif isinstance(source, str):
            image = Image.open(source)
        else:
            image = source
        image = image.convert("RGB")
        image.thumbnail((THUMB, THUMB), Image.LANCZOS)
        buffer = io.BytesIO()
        image.save(buffer, "JPEG", quality=88, optimize=True, progressive=True)
        return buffer.getvalue()

    def add_shot(self, name, source, prompt="", make_cover=True, max_shots=MAX_SHOTS):
        gallery, _family, label = self.split(name)
        key = slug(name)
        if not key:
            return None
        os.makedirs(self.previews_dir(gallery), exist_ok=True)
        filename = self.shot_filename(self.previews_dir(gallery), key)
        with open(os.path.join(self.previews_dir(gallery), filename), "wb") as handle:
            handle.write(self.to_jpeg(source))

        with self._lock:
            data = read_json(self.manifest_path(gallery), {})
            data = data if isinstance(data, dict) else {}
            record = data.get(key) if isinstance(data.get(key), dict) else {}
            shots = [shot for shot in record.get("shots", [])
                     if isinstance(shot, dict) and shot.get("file")]
            shots.append({"file": filename, "prompt": str(prompt or "")[:600],
                          "ts": int(time.time())})
            record["fingerprint"] = self.fingerprint(name)
            while len(shots) > max_shots:
                dropped = shots.pop(0)
                stale = os.path.join(self.previews_dir(gallery), dropped.get("file", ""))
                if os.path.isfile(stale):
                    os.remove(stale)
                drop_derived(stale)
                if record.get("cover") == dropped.get("file"):
                    record["cover"] = ""
            record.update({"shots": shots, "asset": name, "lora": name, "name": label})
            if make_cover or not record.get("cover"):
                record["cover"] = filename
            data[key] = record
            data[self.GALLERY_KEY] = gallery
            write_json(self.manifest_path(gallery), data)
        return {"gallery": gallery, "key": key, "file": filename,
                "record": {"shots": shots, "cover": record["cover"], "count": len(shots),
                           "asset": name, "lora": name, "name": label}}

    def set_cover(self, gallery, key, filename):
        with self._lock:
            data = read_json(self.manifest_path(gallery), {})
            record = data.get(slug(key)) if isinstance(data, dict) else None
            if not isinstance(record, dict):
                return False
            if filename not in {shot.get("file") for shot in record.get("shots", [])}:
                return False
            record["cover"] = filename
            write_json(self.manifest_path(gallery), data)
        return True

    def delete_shot(self, gallery, key, filename):
        with self._lock:
            data = read_json(self.manifest_path(gallery), {})
            record = data.get(slug(key)) if isinstance(data, dict) else None
            if not isinstance(record, dict):
                return False
            kept = [shot for shot in record.get("shots", []) if shot.get("file") != filename]
            if len(kept) == len(record.get("shots", [])):
                return False
            stale = os.path.join(self.previews_dir(gallery), os.path.basename(filename))
            if os.path.isfile(stale):
                os.remove(stale)
            drop_derived(stale)
            record["shots"] = kept
            if record.get("cover") == filename:
                record["cover"] = kept[-1]["file"] if kept else ""
            if not kept:
                data.pop(slug(key), None)
            write_json(self.manifest_path(gallery), data)
        return True

    def shot_paths(self):
        """Every preview image this gallery holds, across its folders."""
        found = []
        for directory in self._galleries_on_disk():
            name = self.real_gallery(directory)
            folder = self.previews_dir(name)
            for record in self.manifest(name).values():
                for shot in record.get("shots", []):
                    path = os.path.join(folder, shot.get("file", ""))
                    if shot.get("file") and os.path.isfile(path):
                        found.append(path)
        return found

    def build_thumbs(self):
        return build_derived(self.shot_paths())

    def delete_all_shots(self, name):
        gallery, _family, _label = self.split(name)
        key = slug(name)
        with self._lock:
            data = read_json(self.manifest_path(gallery), {})
            record = data.pop(key, None) if isinstance(data, dict) else None
            if not isinstance(record, dict):
                return False
            for shot in record.get("shots", []):
                stale = os.path.join(self.previews_dir(gallery), shot.get("file", ""))
                if os.path.isfile(stale):
                    os.remove(stale)
                drop_derived(stale)
            write_json(self.manifest_path(gallery), data)
        return True
