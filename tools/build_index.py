"""Regenerate web/style_index.js — the offline fallback the UI boots from.

The UI refreshes from /neons_style/catalog as soon as ComfyUI is up, so this
only has to populate the combos on first paint: names and metadata, no prompt
text.
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
STYLES_DIR = os.path.join(ROOT, "styles")
OUT = os.path.join(ROOT, "web", "style_index.js")

FAMILY_ORDER = [
    "Anime & Manga", "Western Animation", "Comics & Print", "Traditional Painting",
    "Illustration", "Photography & Film", "3D & Games", "Design & Aesthetics",
    "Experimental & Material", "Other",
]


def main():
    entries = []
    for filename in sorted(os.listdir(STYLES_DIR)):
        if not filename.endswith(".json"):
            continue
        with open(os.path.join(STYLES_DIR, filename), "r", encoding="utf-8") as handle:
            data = json.load(handle)
        entries.extend((data.get("styles") if isinstance(data, dict) else data) or [])

    by_name, families = {}, {}
    for entry in entries:
        by_name[entry["name"]] = {
            "id": entry.get("id", ""),
            "family": entry.get("family", "Other"),
            "axis": entry.get("axis", "style"),
            "medium": entry.get("medium", ""),
            "nl": entry.get("nl", ""),
            "tags": entry.get("tags", []),
            "aliases": entry.get("aliases", []),
            "written": bool(entry.get("written")),
            "source": "v2" if "[v2]" in entry["name"] else "shipped",
        }
        families.setdefault(entry.get("family", "Other"), []).append(entry["name"])

    def names(axis):
        return sorted((e["name"] for e in entries if e.get("axis", "style") == axis), key=str.lower)

    written = sum(1 for e in entries if e.get("written"))
    index = {
        "schema": 1,
        "styles": names("style"),
        "formats": names("format"),
        "finishes": names("finish"),
        "families": families,
        "family_order": [f for f in FAMILY_ORDER if f in families],
        "axes": ["style", "format", "finish"],
        "random_token": "\U0001F3B2 Random",
        "by_name": by_name,
        "coverage": {"total": len(entries), "written": written},
        "count": len(by_name),
    }
    with open(OUT, "w", encoding="utf-8") as handle:
        handle.write("export const NEONS_STYLE_INDEX = ")
        json.dump(index, handle, ensure_ascii=False, separators=(",", ":"))
        handle.write(";\n")
    print(f"wrote web/style_index.js — {len(by_name)} entries "
          f"({len(index['styles'])} styles / {len(index['formats'])} formats / "
          f"{len(index['finishes'])} finishes), {written} hand-written")


if __name__ == "__main__":
    main()
