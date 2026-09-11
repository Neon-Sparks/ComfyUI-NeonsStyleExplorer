"""Catalog linter.

    python tools/lint.py            summary + first findings
    python tools/lint.py --all      every finding
    python tools/lint.py --strict   exit 1 on warnings too

Rules
-----
E  clause missing, not sentence-cased, over MAX chars, or truncated
E  clause does not end with the entry's closing medium
E  clause contains scope/instruction language (this node only writes style)
E  clause names picture content (a person, a place, an action)
E  unknown booru tag, duplicate tag, tag both positive and negative
E  duplicate id or name, bad axis
W  entry not hand-written yet (still an imported placeholder)
W  no tags (unusable in danbooru mode)
"""

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
STYLES_DIR = os.path.join(ROOT, "styles")
VOCAB_PATH = os.path.join(ROOT, "data", "tags.txt")

MAX = 380

# The frame's shape and size belong to the workflow, never to a style clause.
# Written narrowly on purpose: "two-head-tall bodies" is a proportion and
# "vertical scanlines" is a texture, so neither may trip this.
RATIO = re.compile(
    r"\b\d+(?:\.\d+)?\s*:\s*\d+\b"                       # 16:9, 2.39:1
    r"|\baspect\b"                                            # aspect, aspect ratio
    r"|\bletterbox(?:ed|ing)?\b"
    r"|\bwidescreen\b"
    r"|\b(?:tall|wide|vertical|horizontal|square|landscape|portrait)\s+"
    r"(?:framing|crop|format|orientation|composition|panel|panels|frame)\b",
    re.I,
)
AXES = {"style", "format", "finish"}

# Families brought in from another project. Their structure is checked — name,
# axis, closing medium, duplicates, clause length — but not the house writing
# rules, which apply to clauses written for this catalog: their descriptors are
# not booru vocabulary and their phrasing is their own.
IMPORTED_FAMILIES = {"Extra"}

INSTRUCTION = re.compile(
    r"governs the entire image|do not add|do not invent|apply it only|"
    r"not an object|whole scene|entire image|style only|edge to edge|"
    r"you should|the model should|render the entire",
    re.I,
)
CONTENT = re.compile(
    r"\b(a woman|a man|a girl|a boy|a cat|a dog|standing|sitting|holding|"
    r"wearing|walking|looking at (?:the )?viewer)\b",
    re.I,
)
TRUNCATED = re.compile(r"([,;:-]|\b(and|with|of|for|the|a|an|that|into|built|holding))$", re.I)


def vocab():
    tags = set()
    if os.path.isfile(VOCAB_PATH):
        with open(VOCAB_PATH, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line and not line.startswith("#"):
                    tags.add(line)
    return tags


def load():
    rows = []
    for filename in sorted(os.listdir(STYLES_DIR)):
        if not filename.endswith(".json"):
            continue
        with open(os.path.join(STYLES_DIR, filename), "r", encoding="utf-8") as handle:
            data = json.load(handle)
        for entry in (data.get("styles") if isinstance(data, dict) else data) or []:
            rows.append((filename, entry))
    return rows


def main():
    show_all = "--all" in sys.argv
    strict = "--strict" in sys.argv
    known = vocab()
    rows = load()
    errors, warnings = [], []
    ids, names = {}, {}
    written = 0
    imported_count = 0

    for filename, entry in rows:
        name = entry.get("name", "")
        where = f"{filename}: {name or '(unnamed)'}"
        if entry.get("family") in IMPORTED_FAMILIES or entry.get("pack"):
            imported_count += 1
        elif entry.get("written"):
            written += 1
        else:
            warnings.append(f"{where}: placeholder clause, not hand-written yet")

        imported = entry.get("family") in IMPORTED_FAMILIES or bool(entry.get("pack"))

        ident = entry.get("id", "")
        if ident in ids:
            errors.append(f"{where}: duplicate id '{ident}' (also {ids[ident]})")
        ids[ident] = name
        if name.lower() in names:
            errors.append(f"{where}: duplicate name (also {names[name.lower()]})")
        names[name.lower()] = filename
        if entry.get("axis") not in AXES:
            errors.append(f"{where}: bad axis '{entry.get('axis')}'")

        medium = str(entry.get("medium", "")).strip()
        clause = str(entry.get("nl", "")).strip()
        if not clause:
            errors.append(f"{where}: empty clause")
        else:
            if not clause[0].isupper() and not clause[0].isdigit():
                errors.append(f"{where}: clause not sentence-cased")
            if clause[-1] != ".":
                errors.append(f"{where}: clause must end with a period")
            if len(clause) > MAX:
                errors.append(f"{where}: clause {len(clause)} chars > {MAX}")
            if TRUNCATED.search(clause.rstrip(".")):
                errors.append(f"{where}: clause looks truncated -> ...{clause[-40:]}")
            if INSTRUCTION.search(clause) and not imported:
                errors.append(f"{where}: instruction/scope language in the clause")
            if CONTENT.search(clause) and not imported:
                errors.append(f"{where}: clause names picture content")
            # the process phrase is separated by a comma, not a colon
            if ": " in clause and not imported:
                errors.append(f"{where}: colon after the process phrase, use a comma")
            # the workflow sets the frame size, so a clause never names one
            if RATIO.search(clause) and not imported:
                errors.append(f"{where}: names an aspect ratio, the workflow sets that")
            if medium and entry.get("written") and not clause.rstrip(".").lower().endswith(medium.lower()):
                errors.append(f"{where}: clause must close with '{medium}'")

        tags = entry.get("tags") or []
        negs = entry.get("tags_negative") or []
        if not tags:
            warnings.append(f"{where}: no tags")
        if len(tags) != len(set(tags)):
            errors.append(f"{where}: duplicate tags")
        for tag in tags:
            if known and tag not in known and not imported:
                errors.append(f"{where}: unknown tag '{tag}'")
        for tag in negs:
            if known and tag not in known and not imported:
                errors.append(f"{where}: unknown negative tag '{tag}'")
            if tag in tags:
                errors.append(f"{where}: '{tag}' is both positive and negative")

    limit = None if show_all else 20
    print(f"entries:      {len(rows)}")
    own = len(rows) - imported_count
    print(f"hand-written: {written} of {own} written for this catalog "
          f"({written * 100 // max(1, own)}%)")
    if imported_count:
        print(f"imported:     {imported_count} (structure checked, house rules not applied)")
    print(f"errors:       {len(errors)}")
    for line in errors[:limit]:
        print(f"  E {line}")
    placeholders = sum(1 for line in warnings if "placeholder" in line)
    print(f"warnings:     {len(warnings)} ({placeholders} placeholders)")
    for line in [w for w in warnings if "placeholder" not in w][:limit]:
        print(f"  W {line}")
    if errors or (strict and warnings):
        sys.exit(1)


if __name__ == "__main__":
    main()
