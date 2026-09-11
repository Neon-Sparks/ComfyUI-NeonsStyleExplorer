"""Share a whole catalog: its previews, the styles they belong to, and the
prompts they were made with.

A bundle is a plain zip:

    bundle.json          what the catalog is called, its prompts, this format's
                         version, and a row per preview naming its style
    previews/<file>.jpg  the images themselves
    styles.json          any custom or edited styles the previews depend on, so
                         they resolve on the machine that opens the bundle

Reading one is the dangerous direction. A zip carries its own file names, and a
name like ``../../autorun`` would write outside the catalog if it were trusted,
so nothing from the archive is used as a path: every entry is matched against a
whitelist, its name is rebuilt from a slug, and the archive is refused if it is
too large, holds too many files, or expands too far.
"""

import io
import json
import os
import re
import time
import zipfile

from . import catalogs

SCHEMA = 1
MAX_BYTES = 512 * 1024 * 1024        # a big gallery, not a disk filler
MAX_FILES = 20000
MAX_RATIO = 200                      # expanded : stored, guards a zip bomb
IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".webp")


def safe_file(name):
    """A stored image name reduced to something that cannot be a path."""
    base = os.path.basename(str(name or "").replace("\\", "/"))
    stem, dot, suffix = base.rpartition(".")
    if not dot or f".{suffix.lower()}" not in IMAGE_SUFFIXES:
        return ""
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", stem)[:120].strip("._-")
    return f"{stem}.{suffix.lower()}" if stem else ""


# ------------------------------------------------------------------ export


def export_catalog(cid=None, styles=None):
    """Build a bundle for one catalog and return (filename, bytes)."""
    from . import gallery

    cid = cid or catalogs.active()
    name = catalogs.name_of(cid)
    paths = catalogs.paths(cid)
    manifest = {}
    if os.path.isfile(paths["manifest"]):
        try:
            with open(paths["manifest"], "r", encoding="utf-8") as handle:
                loaded = json.load(handle)
            manifest = loaded if isinstance(loaded, dict) else {}
        except (OSError, json.JSONDecodeError):
            manifest = {}

    rows, files = [], []
    for key, record in manifest.items():
        if not isinstance(record, dict):
            continue
        shots = [shot for shot in record.get("shots", []) if isinstance(shot, dict) and shot.get("file")]
        kept = []
        for shot in shots:
            stored = os.path.join(paths["previews"], shot["file"])
            if os.path.isfile(stored):
                kept.append(shot)
                files.append((shot["file"], stored))
        if not kept:
            continue
        rows.append({
            "key": key,
            "style": record.get("style") or record.get("name") or key,
            "cover": record.get("cover") or kept[0]["file"],
            "shots": [{"file": shot["file"], "prompt": shot.get("prompt", ""), "ts": shot.get("ts", 0)}
                      for shot in kept],
        })

    meta = {
        "schema": SCHEMA,
        "kind": "neons-style-catalog",
        "name": name,
        "created": int(time.time()),
        "prompts": catalogs.prompts_of(cid),
        "entries": rows,
    }

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("bundle.json", json.dumps(meta, indent=2, ensure_ascii=False))
        if styles:
            archive.writestr("styles.json", json.dumps({"schema": 1, "styles": styles},
                                                       indent=2, ensure_ascii=False))
        for stored_name, path in files:
            archive.write(path, f"previews/{stored_name}")

    slug = re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-").lower() or "catalog"
    return f"neons-catalog-{slug}.zip", buffer.getvalue()


# ------------------------------------------------------------------ import


def _check(archive, raw_size):
    """Refuse an archive that is too big, too many files, or too expansive."""
    infos = archive.infolist()
    if len(infos) > MAX_FILES:
        return f"the bundle holds {len(infos)} files, more than this will unpack"
    total = sum(info.file_size for info in infos)
    if total > MAX_BYTES:
        return f"the bundle expands to {total // (1024 * 1024)} MB, more than this will unpack"
    if raw_size and total / max(1, raw_size) > MAX_RATIO:
        return "the bundle expands far more than its size suggests, so it was not unpacked"
    return ""


def import_bundle(raw, name=None, into=None):
    """Unpack a bundle into a new catalog (or *into* an existing one).

    Returns (ok, message, info).
    """
    from . import gallery
    from .store import save_custom

    try:
        archive = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile:
        return False, "that file is not a zip bundle", {}

    problem = _check(archive, len(raw))
    if problem:
        return False, problem, {}

    try:
        meta = json.loads(archive.read("bundle.json").decode("utf-8"))
    except (KeyError, ValueError, UnicodeDecodeError):
        return False, "the bundle has no readable bundle.json", {}
    if meta.get("kind") != "neons-style-catalog":
        return False, "that zip is not a Neons catalog bundle", {}

    label = catalogs.clean_name(name or meta.get("name") or "Imported catalog")
    target = into or catalogs.create(label)["id"]
    paths = catalogs.paths(target)
    os.makedirs(paths["previews"], exist_ok=True)

    # any styles the bundle needs, so its previews attach to something
    styles_added = 0
    if "styles.json" in archive.namelist():
        try:
            payload = json.loads(archive.read("styles.json").decode("utf-8"))
            for row in payload.get("styles") or []:
                if not isinstance(row, dict) or not row.get("name"):
                    continue
                ok, _info = save_custom(
                    row.get("name", ""), family=row.get("family", "Other"),
                    axis=row.get("axis", "style"), nl=row.get("nl", ""),
                    medium=row.get("medium", ""), negative=row.get("negative", ""),
                    tags=row.get("tags"), tags_negative=row.get("tags_negative"),
                )
                styles_added += 1 if ok else 0
        except (ValueError, UnicodeDecodeError):
            pass

    # the images: nothing from the archive is trusted as a path
    stored = {}
    for info in archive.infolist():
        if info.is_dir():
            continue
        parts = info.filename.replace("\\", "/").split("/")
        if len(parts) != 2 or parts[0] != "previews":
            continue
        filename = safe_file(parts[1])
        if not filename:
            continue
        destination = os.path.join(paths["previews"], filename)
        if os.path.realpath(destination) != os.path.join(os.path.realpath(paths["previews"]), filename):
            continue
        with archive.open(info) as source, open(destination, "wb") as sink:
            sink.write(source.read())
        stored[parts[1]] = filename

    # rebuild the manifest from the bundle's rows, keeping only stored images
    manifest = {}
    for row in meta.get("entries") or []:
        if not isinstance(row, dict):
            continue
        key = gallery.safe(row.get("key") or row.get("style") or "")
        if not key:
            continue
        shots = []
        for shot in row.get("shots") or []:
            filename = stored.get(str(shot.get("file", "")))
            if filename:
                shots.append({"file": filename, "prompt": str(shot.get("prompt", ""))[:600],
                              "ts": int(shot.get("ts") or 0)})
        if not shots:
            continue
        cover = stored.get(str(row.get("cover", ""))) or shots[0]["file"]
        manifest[key] = {"shots": shots, "cover": cover, "count": len(shots),
                         "style": str(row.get("style") or "")[:160]}

    with open(paths["manifest"], "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, ensure_ascii=False)

    for prompt in meta.get("prompts") or []:
        catalogs.add_prompt(target, prompt)

    return True, "", {
        "catalog": target,
        "name": catalogs.name_of(target),
        "styles": len(manifest),
        "images": len(stored),
        "styles_added": styles_added,
        "prompts": len(meta.get("prompts") or []),
    }
