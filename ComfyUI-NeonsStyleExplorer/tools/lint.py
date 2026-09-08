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
AXES = {"style", "format", "finish"}

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

    for filename, entry in rows:
        name = entry.get("name", "")
        where = f"{filename}: {name or '(unnamed)'}"
        if entry.get("written"):
            written += 1
        else:
            warnings.append(f"{where}: placeholder clause, not hand-written yet")

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
            if INSTRUCTION.search(clause):
                errors.append(f"{where}: instruction/scope language in the clause")
            if CONTENT.search(clause):
                errors.append(f"{where}: clause names picture content")
            if medium and entry.get("written") and not clause.rstrip(".").lower().endswith(medium.lower()):
                errors.append(f"{where}: clause must close with '{medium}'")

        tags = entry.get("tags") or []
        negs = entry.get("tags_negative") or []
        if not tags:
            warnings.append(f"{where}: no tags")
        if len(tags) != len(set(tags)):
            errors.append(f"{where}: duplicate tags")
        for tag in tags:
            if known and tag not in known:
                errors.append(f"{where}: unknown tag '{tag}'")
        for tag in negs:
            if known and tag not in known:
                errors.append(f"{where}: unknown negative tag '{tag}'")
            if tag in tags:
                errors.append(f"{where}: '{tag}' is both positive and negative")

    limit = None if show_all else 20
    print(f"entries:      {len(rows)}")
    print(f"hand-written: {written} ({written * 100 // max(1, len(rows))}%)")
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
