"""Build styles/ from the hand-written packs in tools/written/.

Base = the current styles/*.json (ids, families, axes). Every pack in
tools/written/ is applied on top by name; any entry in a pack that is not in the
catalog yet is appended as a new style, so adding looks is just a matter of
dropping a record into a pack.

A new record needs at least ``name`` and ``nl``. ``family`` and ``axis`` are
derived from the name's bracket tag when they are not given, and ``medium``
falls back to the family default.

    python tools/import_source.py            rebuild styles/
    python tools/import_source.py --report   show what would change
"""

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
STYLES = os.path.join(ROOT, "styles")
WRITTEN = os.path.join(HERE, "written")
BOOTSTRAP = os.path.join(HERE, "source")

FAMILY_ORDER = [
    "Anime & Manga", "Western Animation", "Comics & Print", "Traditional Painting",
    "Illustration", "Photography & Film", "3D & Games", "Design & Aesthetics",
    "Experimental & Material", "Other",
]

FAMILY_FILES = {
    "Anime & Manga": "01_anime_manga.json",
    "Western Animation": "02_western_animation.json",
    "Comics & Print": "03_comics_print.json",
    "Traditional Painting": "04_painting.json",
    "Illustration": "05_illustration.json",
    "Photography & Film": "06_photo_film.json",
    "3D & Games": "07_3d_games.json",
    "Design & Aesthetics": "08_design_aesthetics.json",
    "Experimental & Material": "09_experimental_material.json",
    "Other": "10_other.json",
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
    "Other": "style image",
}

TAG_FAMILY = {
    "Anime": "Anime & Manga", "Manga": "Anime & Manga",
    "Cartoon": "Western Animation",
    "Comic": "Comics & Print", "Print": "Comics & Print",
    "Painting": "Traditional Painting",
    "Illustration": "Illustration", "Drawing": "Illustration",
    "Cover": "Illustration", "Digital": "Illustration",
    "Photo": "Photography & Film", "Cinema": "Photography & Film",
    "Light": "Photography & Film",
    "3D": "3D & Games", "Object": "3D & Games", "Pixel": "3D & Games",
    "Aesthetic": "Design & Aesthetics", "Design": "Design & Aesthetics",
    "Experimental": "Experimental & Material", "Material": "Experimental & Material",
}

FIELDS = ("medium", "nl", "tags", "tags_negative", "negative", "aliases")


def slug(text, limit=52):
    text = re.sub(r"[^a-z0-9]+", "_", str(text or "").lower()).strip("_")
    return text[:limit] or "entry"


def base_name(name):
    return re.sub(r"^(\[[^\]]+\]\s*)+", "", str(name or "")).strip()


def bracket_tags(name):
    return re.findall(r"\[([^\]]+)\]", str(name or ""))


def derive_axis(name, given=None):
    if given in ("style", "format", "finish"):
        return given
    tags = bracket_tags(name)
    if "Format" in tags:
        return "format"
    if "Finish" in tags:
        return "finish"
    return "style"


def derive_family(name, given=None):
    if given:
        return given
    for tag in bracket_tags(name):
        if tag in TAG_FAMILY:
            return TAG_FAMILY[tag]
    return "Other"


def load_base():
    """Current catalog, or the original import if styles/ is empty."""
    entries = []
    source = STYLES if any(f.endswith(".json") for f in os.listdir(STYLES)) else BOOTSTRAP
    if not os.path.isdir(source):
        return entries
    for filename in sorted(os.listdir(source)):
        if not filename.endswith(".json"):
            continue
        with open(os.path.join(source, filename), "r", encoding="utf-8") as handle:
            data = json.load(handle)
        entries.extend((data.get("styles") if isinstance(data, dict) else data) or [])
    return entries


def load_written():
    packs = {}
    if not os.path.isdir(WRITTEN):
        return packs
    for filename in sorted(os.listdir(WRITTEN)):
        if not filename.endswith(".json"):
            continue
        with open(os.path.join(WRITTEN, filename), "r", encoding="utf-8") as handle:
            for record in json.load(handle):
                packs[record["name"]] = record
    return packs


def main():
    report_only = "--report" in sys.argv
    base = load_base()
    written = load_written()
    by_name = {entry["name"]: entry for entry in base}
    ids = {entry.get("id", "") for entry in base}

    updated, added = 0, []
    for name, record in written.items():
        entry = by_name.get(name)
        if entry is None:
            family = derive_family(name, record.get("family"))
            axis = derive_axis(name, record.get("axis"))
            ident = f"{slug(family.split(' ')[0], 8)}.{slug(base_name(name))}"
            while ident in ids:
                ident += "_x"
            ids.add(ident)
            entry = {
                "id": ident, "name": name, "family": family, "axis": axis,
                "medium": record.get("medium") or FAMILY_MEDIUM.get(family, "style image"),
                "nl": "", "tags": [], "tags_negative": [], "negative": "",
                "aliases": [], "written": True,
            }
            by_name[name] = entry
            base.append(entry)
            added.append(name)
        else:
            updated += 1
            if record.get("family"):
                entry["family"] = record["family"]
            entry["axis"] = derive_axis(name, record.get("axis") or entry.get("axis"))
        for field in FIELDS:
            if record.get(field) is not None:
                entry[field] = record[field]
        entry["written"] = True

    families = {family: [] for family in FAMILY_ORDER}
    for entry in base:
        families.setdefault(entry.get("family", "Other"), []).append(entry)

    if not report_only:
        for family, rows in families.items():
            rows.sort(key=lambda e: (e.get("axis", "style"), e["name"].lower()))
            path = os.path.join(STYLES, FAMILY_FILES.get(family, "10_other.json"))
            with open(path, "w", encoding="utf-8") as handle:
                json.dump({"schema": 1, "family": family, "styles": rows}, handle,
                          indent=2, ensure_ascii=False)
                handle.write("\n")

    total = len(base)
    written_count = sum(1 for entry in base if entry.get("written"))
    print(f"catalog: {total} entries ({written_count} hand-written)")
    print(f"updated from packs: {updated}   new entries added: {len(added)}")
    for name in added[:25]:
        print(f"   + {name}")
    if len(added) > 25:
        print(f"   … and {len(added) - 25} more")
    for family in FAMILY_ORDER:
        rows = families.get(family) or []
        if rows:
            axes = {}
            for entry in rows:
                axes[entry.get("axis", "style")] = axes.get(entry.get("axis", "style"), 0) + 1
            detail = ", ".join(f"{count} {axis}" for axis, count in sorted(axes.items()))
            print(f"  {family:<26} {len(rows):>4}  ({detail})")


if __name__ == "__main__":
    main()
