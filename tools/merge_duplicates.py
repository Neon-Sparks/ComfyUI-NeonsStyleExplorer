"""Merge duplicate entries into one, keeping the other names as search aliases.

Only pairs that describe the same look are listed here — near neighbours
(1980s vs 1990s anime, packshot vs lifestyle product, Marvel vs DC house style)
are deliberately left alone.

    python tools/merge_duplicates.py --report   list what would happen
    python tools/merge_duplicates.py            apply to styles/ and tools/written/
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
STYLES = os.path.join(ROOT, "styles")
WRITTEN = os.path.join(HERE, "written")

# keeper -> entries folded into it
MERGES = {
    # cross-family twins
    "[Cover][v2] Dark Fantasy Illustration": ["[Aesthetic] Dark Fantasy Illustration"],
    "[Print] Woodcut": ["[3D][v2] Woodcut"],
    "[Painting] Op Art": ["[3D][v2] Op-Art"],
    "[Aesthetic] Frutiger Aero": ["[3D][v2] Frutiger Aero"],
    "[Aesthetic] Corporate Memphis": ["[Design][v2] Corporate Memphis"],
    "[Aesthetic] Bauhaus": ["[Design][v2] Bauhaus"],
    "[Aesthetic] Steampunk": ["[3D][v2] Steampunk"],
    "[Aesthetic] WPA Poster": ["[Illustration] WPA Park Poster"],
    "[Object] Origami": ["[Design][v2] Origami"],
    "[Object] Claymation": ["[3D][v2] Claymation"],
    "[Object] Papercraft": ["[3D] Papercraft Lowpoly Toy"],
    "[Pixel] 8-bit": ["[Design][v2] 8-Bit"],
    "[Experimental] Stained Glass": ["[3D][v2] Stained Glass Flat Art"],
    "[Experimental] Mosaic Tesserae": ["[3D][v2] Mosaic Art"],
    "[Digital][v2] X-Ray": ["[Experimental] X-Ray Film"],
    "[Illustration] Matte Painting": ["[Photo][v2] Atmospheric Matte Painting"],
    "[Cover][v2] Hyper-Stylized Digital Painting": ["[Design][v2] Hyper-Stylized Illustration"],

    # same look, two names
    "[3D] Low-Poly": ["[3D] Low Poly (2)", "[3D][v2] Low Poly"],
    "[3D] Clay Render": ["[3D] Clay Shader"],
    "[3D] Isometric 3D": ["[3D][v2] Isometric 3D Graphic"],
    "[3D] Cycles Render": ["[3D] Blender Cycles"],
    "[3D] PS1 Affine": ["[3D][v2] PS1 Graphics", "[3D][v2] PS1 Screenshot"],
    "[Format] Packshot": ["[Format] Product Packshot"],
    "[Format] Storyboard Panel": ["[Cartoon] Storyboard Frame"],
    "[Photo][v2] Film Noir": ["[Photo][v2] Film Noir (2)"],
    "[Photo] Platinum / Palladium": ["[Photo] Platinum Palladium"],
    "[Photo] Holga Toy Camera": ["[Photo] Toy Camera"],
    "[Photo] Cross-Processed": ["[Photo][v2] Cross Process Photography",
                                "[Photo][v2] Cross-Processed Film Photography"],
    "[Photo] Halation Subtle": ["[Photo][v2] Halation"],
    "[Photo] Kodachrome 1970s": ["[Photo][v2] Kodachrome"],
    "[Photo] Large Format": ["[Photo] Large-Format 4x5"],
    "[Photo] Wet Plate Collodion": ["[Photo] Wet Plate"],
    "[Photo] Polaroid": ["[Photo] Polaroid Instant"],
    "[Photo] Tri-X 400": ["[Photo] Tri-X Black-and-White"],
    "[Photo] Expired Film": ["[Photo] Expired Color Negative"],
    "[Photo] Paparazzi Tele": ["[Photo] Paparazzi Long Lens"],
    "[Photo] Sports Peak": ["[Photo] Sports Freeze"],
    "[Photo] Underwater": ["[Photo][v2] Underwater Photography"],
    "[Photo] Motion-Blur Panning": ["[Photo][v2] Motion Blur Photography"],
    "[Photo] CCTV Surveillance": ["[Photo][v2] Surveillance Camera Photo"],
    "[Photo] 35mm Film": ["[Photo][v2] 35mm Photography"],
    "[Painting] Watercolor": ["[Painting][v2] Watercolor Painting"],
    "[Painting] Gouache": ["[Painting] Gouache Opaque"],
    "[Painting] Colored Pencil": ["[Painting] Colored Pencil Layered"],
    "[Painting] Charcoal": ["[Drawing][v2] Charcoal Rendering"],
    "[Painting] Thangka": ["[Painting] Tibetan Thangka"],
    "[Painting] Gongbi": ["[Painting] Gongbi Fine Brush"],
    "[Painting] Ink Calligraphic Brush": ["[Drawing][v2] Calligraphic Linework"],
    "[Painting][v2] Hyperrealism": ["[Painting][v2] Ultrarealism"],
    "[Print] Letterpress": ["[Print] Letterpress Bite"],
    "[Aesthetic] Synthwave": ["[Aesthetic] Synthwave Outrun"],
    "[Aesthetic] Maximalism": ["[Aesthetic] Maximalist Pattern"],
    "[Aesthetic] Tropical Modernism": ["[Aesthetic] Tropical Modern"],
    "[Anime] Cel Shading Bands": ["[Anime][v2] Cel Shading"],
    "[Anime] Manga Screentone": ["[Anime] Screentone Manga"],
    "[Anime] Chibi": ["[Anime][v2] Chibi Anime"],
    "[Anime] Super Deformed": ["[Anime] Chibi Super-Deformed"],
    "[Anime] Watercolor Anime": ["[Anime][v2] Watercolor Anime Illustration"],
    "[Anime] Josei Fashion": ["[Manga] Josei Fashion Line"],
    "[Anime] Shōjo Line": ["[Anime] Shōjo Line Weight"],
    "[Anime] Gekiga": ["[Manga] Gekiga Grit"],
    "[Drawing][v2] Beatrix Potter": ["[Drawing][v2] Beatrix Potter Style (2)"],
}

# keeper -> tidier name (the old name is kept as an alias)
RENAMES = {
    "[Painting] Abstract Expressionism (2)": "[Painting] Abstract Expressionism",
}
MERGES["[Painting] Abstract Expressionism (2)"] = ["[Painting][v2] Abstract Expressionism"]


def load(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def save(path, data):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def main():
    report_only = "--report" in sys.argv
    absorbed = {name: keeper for keeper, names in MERGES.items() for name in names}

    # ---- styles/ ----
    kept_alias = {}
    removed, missing = [], []
    files = {}
    index = {}
    for filename in sorted(os.listdir(STYLES)):
        if not filename.endswith(".json"):
            continue
        data = load(os.path.join(STYLES, filename))
        files[filename] = data
        for entry in data["styles"]:
            index[entry["name"]] = entry

    for keeper, names in MERGES.items():
        target = index.get(keeper)
        if target is None:
            missing.append(keeper)
            continue
        aliases = list(target.get("aliases", []))
        for name in names:
            entry = index.get(name)
            if entry is None:
                missing.append(name)
                continue
            for alias in [name] + list(entry.get("aliases", [])):
                if alias not in aliases:
                    aliases.append(alias)
            removed.append(name)
        kept_alias[keeper] = aliases

    for keeper, aliases in kept_alias.items():
        index[keeper]["aliases"] = aliases
    for old, new in RENAMES.items():
        entry = index.get(old)
        if entry:
            aliases = list(entry.get("aliases", []))
            if old not in aliases:
                aliases.append(old)
            entry["aliases"] = aliases
            entry["name"] = new

    if not report_only:
        for filename, data in files.items():
            data["styles"] = [e for e in data["styles"] if e["name"] not in absorbed]
            save(os.path.join(STYLES, filename), data)

        # ---- tools/written/ : same edit, so a rebuild keeps the merge ----
        for filename in sorted(os.listdir(WRITTEN)):
            if not filename.endswith(".json"):
                continue
            path = os.path.join(WRITTEN, filename)
            records = load(path)
            changed = False
            kept = []
            for record in records:
                if record["name"] in absorbed:
                    changed = True
                    continue
                if record["name"] in kept_alias:
                    record["aliases"] = kept_alias[record["name"]]
                    changed = True
                if record["name"] in RENAMES:
                    aliases = list(record.get("aliases", []))
                    if record["name"] not in aliases:
                        aliases.append(record["name"])
                    record["aliases"] = aliases
                    record["name"] = RENAMES[record["name"]]
                    changed = True
                kept.append(record)
            if changed:
                save(path, kept)

    print(f"merge groups: {len(MERGES)}")
    print(f"entries folded away: {len(removed)}")
    print(f"renames: {len(RENAMES)}")
    if missing:
        print(f"NOT FOUND ({len(missing)}): {missing}")
    for keeper, names in MERGES.items():
        label = RENAMES.get(keeper, keeper)
        print(f"  {label}  <-  {', '.join(names)}")


if __name__ == "__main__":
    main()
