"""Regenerate STYLES.md from the built catalog."""

import json
import os
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
STYLES_DIR = os.path.join(ROOT, "styles")
OUT = os.path.join(ROOT, "STYLES.md")


def main():
    entries = []
    for filename in sorted(os.listdir(STYLES_DIR)):
        if not filename.endswith(".json"):
            continue
        with open(os.path.join(STYLES_DIR, filename), "r", encoding="utf-8") as handle:
            data = json.load(handle)
        entries.extend((data.get("styles") if isinstance(data, dict) else data) or [])

    axes = Counter(e.get("axis", "style") for e in entries)
    mediums = Counter(e.get("medium", "") for e in entries)
    families = defaultdict(list)
    for entry in entries:
        families[entry.get("family", "Other")].append(entry)

    lines = [
        "# Style catalog",
        "",
        f"{len(entries)} entries, all hand-written — "
        f"{axes.get('style', 0)} styles, {axes.get('format', 0)} formats, "
        f"{axes.get('finish', 0)} finishes.",
        "",
        "Each entry is a style prefix: it describes only how the picture is rendered",
        "and closes with its medium. The node adds nothing else.",
        "",
        "| medium | entries |",
        "| --- | --- |",
    ]
    for medium, count in mediums.most_common():
        lines.append(f"| {medium} | {count} |")
    lines.append("")

    for family in sorted(families):
        rows = sorted(families[family], key=lambda e: e["name"].lower())
        lines += [f"## {family} ({len(rows)})", "", "| name | axis | tags | clause |", "| --- | --- | --- | --- |"]
        for entry in rows:
            clause = entry["nl"].replace("|", "/")
            if len(clause) > 160:
                clause = clause[:157] + "..."
            lines.append(
                f"| {entry['name']} | {entry.get('axis', 'style')} | "
                f"{', '.join(entry.get('tags', [])[:4])} | {clause} |"
            )
        lines.append("")

    with open(OUT, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines))
    print(f"wrote STYLES.md ({len(entries)} entries)")


if __name__ == "__main__":
    main()
