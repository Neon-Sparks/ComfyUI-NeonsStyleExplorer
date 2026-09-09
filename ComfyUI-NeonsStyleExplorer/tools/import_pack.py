"""Convert an external style export into a written pack.

    python3 tools/import_pack.py <export.js|export.json> [--family Extra] [--out 40_extra.json]

The input is a JSON array (or a JS file with one assigned to a variable) whose
records carry a prompt string. Each record becomes a catalog entry:

* the NAME comes from the text after "Style:" when present, otherwise from the
  first descriptor in the string, title-cased and de-duplicated;
* the CLAUSE is the record's own text, capitalised and closed with the family's
  medium — the closing medium is what keeps a stacked prompt coherent, so it is
  added even when the source has none;
* the TAGS are the record's descriptors with spaces turned into underscores,
  which is what the danbooru output modes emit for these entries.

Imported entries are marked with a `pack` field so their provenance stays
visible in the data itself, and the linter treats the family as an import: its
structure is checked, but not the house writing rules that apply to entries
written for this project.
"""

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WRITTEN = os.path.join(HERE, "written")

MAX_CLAUSE = 380
SMALL = {"a", "an", "and", "as", "at", "by", "for", "in", "of", "on", "or", "the", "to", "with"}


def load_records(path):
    """Read a JSON array, or a .js file with one assigned to a variable."""
    with open(path, "r", encoding="utf-8", errors="ignore") as handle:
        raw = handle.read()
    start, end = raw.find("["), raw.rfind("]")
    if start < 0 or end < start:
        raise SystemExit(f"no JSON array found in {path}")
    return json.loads(raw[start:end + 1])


def descriptors(prompt):
    out = []
    for part in str(prompt or "").split(","):
        part = re.sub(r"\s+", " ", part).strip()
        if part:
            out.append(part)
    return out


def title_case(text):
    words = re.sub(r"[^A-Za-z0-9 '\-]+", " ", text).split()
    if not words:
        return ""
    titled = [
        word if word.isupper() and len(word) <= 4
        else (word.lower() if index and word.lower() in SMALL else word.capitalize())
        for index, word in enumerate(words)
    ]
    return " ".join(titled)[:60].strip()


def entry_name(prompt, parts, taken, prefix):
    """Prefer an explicit 'Style: name', else the leading descriptor."""
    match = re.match(r"\s*style\s*:\s*([^,\n]+)", str(prompt or ""), re.I)
    base = title_case(match.group(1) if match else (parts[0] if parts else ""))
    if not base:
        base = "Untitled"
    candidate, n = f"[{prefix}] {base}", 2
    while candidate.lower() in taken:
        candidate = f"[{prefix}] {base} {n}"
        n += 1
    taken.add(candidate.lower())
    return candidate


def clause(parts, medium):
    """The record's own text, capitalised and closed with the medium."""
    body = ", ".join(parts)
    body = body[0].upper() + body[1:] if body else ""
    tail = f", {medium}."
    room = MAX_CLAUSE - len(tail)
    if len(body) > room:                      # trim on a descriptor boundary
        kept = []
        for part in parts:
            if len(", ".join(kept + [part])) > room:
                break
            kept.append(part)
        body = ", ".join(kept) or parts[0][:room]
        body = body[0].upper() + body[1:]
    return f"{body}{tail}"


def as_tag(text):
    tag = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return tag[:60]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("--family", default="Extra")
    parser.add_argument("--prefix", default="Extra", help="bracket tag on each name")
    parser.add_argument("--medium", default="style image")
    parser.add_argument("--out", default="40_extra.json")
    parser.add_argument("--pack", default="", help="provenance note stored on every entry")
    args = parser.parse_args()

    records = load_records(args.source)
    taken, entries, skipped = set(), [], 0
    for record in records:
        prompt = record.get("prompt") if isinstance(record, dict) else record
        parts = descriptors(prompt)
        if not parts:
            skipped += 1
            continue
        tags = []
        for part in parts:
            tag = as_tag(part)
            if tag and tag not in tags:
                tags.append(tag)
        entry = {
            "name": entry_name(prompt, parts, taken, args.prefix),
            "family": args.family,
            "axis": "style",
            "medium": args.medium,
            "nl": clause(parts, args.medium),
            "tags": tags,
            "tags_negative": [],
            "negative": "",
        }
        if args.pack:
            entry["pack"] = args.pack
        entries.append(entry)

    out = os.path.join(WRITTEN, args.out)
    with open(out, "w", encoding="utf-8") as handle:
        json.dump(entries, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    print(f"{len(entries)} entries -> tools/written/{args.out}"
          + (f"  ({skipped} skipped, empty)" if skipped else ""))
    print("now run: python3 tools/import_source.py && python3 tools/lint.py")


if __name__ == "__main__":
    sys.exit(main())
