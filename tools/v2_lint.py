"""Linter for version 2 styles.

    python tools/v2_lint.py                    lint styles_v2/*.json
    python tools/v2_lint.py batch.jsonl ...    lint working batches (one JSON object per line)

A version 2 style is a LEAD that names the look and its medium, followed by
five to seven PARTS: concrete visual descriptors, most defining first. The
order matters — the node's light strength keeps only the first parts.

Exit code 1 if anything is wrong.
"""

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
V2 = os.path.join(ROOT, "styles_v2")
VOCAB = os.path.join(ROOT, "data", "tags.txt")

MAX_NAME = 40
MAX_LEAD = 70
MAX_PART = 60
MAX_CLAUSE = 420
MOD_KINDS = {"lighting", "palette", "camera", "mood", "format", "finish"}

CONTENT = re.compile(
    r"\b(a woman|a man|a girl|a boy|women|men|girls|boys|a cat|a dog|standing|sitting|"
    r"holding|wearing|walking|running|smiling|looking at (?:the )?viewer|her |his |she |he )\b",
    re.I)
INSTRUCTION = re.compile(
    r"\b(do not|don't|you should|the model|must be|make sure|ensure|apply (?:it|this)|"
    r"entire image|whole image|whole scene|edge to edge)\b", re.I)
NEGATION = re.compile(r"^(no|not|never|without|avoid\w*|free of|lacking)\b|\bwithout\b|\bno\s", re.I)
QUALITY = re.compile(
    r"\b(4k|8k|16k|uhd|hdr|masterpiece|best quality|award[- ]winning|trending|artstation|"
    r"deviantart|pixiv|behance|unsplash|ultra[- ]detailed|high[- ]quality|high[- ]resolution|"
    r"professional|stunning|beautiful|amazing|gorgeous|breathtaking)\b", re.I)
RATIO = re.compile(r"\b\d+(?:\.\d+)?\s*:\s*\d+\b|\baspect ratio\b|\bwidescreen\b|\bletterbox\w*\b",
                   re.I)
# real people, studios and brands: a style describes a look, it does not borrow a name
NAMES = re.compile(
    r"\b(ghibli|disney|pixar|marvel|dc comics|dreamworks|nintendo|pokemon|sega|capcom|"
    r"magritte|dal[ií]|picasso|van gogh|monet|manet|klimt|mucha|rembrandt|vermeer|"
    r"caravaggio|hokusai|hiroshige|warhol|banksy|giger|escher|miyazaki|tarantino|kubrick|"
    r"wes anderson|lynch|spielberg|moebius|frazetta|rockwell|leyendecker|basquiat|rothko|"
    r"pollock|mondrian|kandinsky|matisse|cezanne|gauguin|turner|hopper|kahlo|lichtenstein|"
    r"schiele|bosch|bruegel|goya|durer|beksinski|kinkade|shinkai|toriyama|tezuka|otomo|"
    r"leica|hasselblad|kodak|kodachrome|fuji(?:film)?|polaroid|canon|nikon|sony|lego|"
    r"barbie|ikea|apple|unreal engine|octane|blender|zbrush|photoshop|minecraft|"
    r"simpsons|studio trigger|kyoto animation)\b", re.I)


def load_taxonomy():
    with open(os.path.join(V2, "_taxonomy.json"), "r", encoding="utf-8") as handle:
        data = json.load(handle)
    subs = {cat["id"]: set(cat["subs"]) for cat in data["categories"]}
    return subs, set(data["traits"])


def load_vocab():
    tags = set()
    with open(VOCAB, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line and not line.startswith("#"):
                tags.add(line)
    return tags


def words(text):
    return len(str(text).split())


def text_problems(label, text):
    out = []
    for rule, what in ((CONTENT, "names picture content"), (INSTRUCTION, "gives an instruction"),
                       (QUALITY, "uses a quality buzzword"), (RATIO, "names a frame shape"),
                       (NAMES, "uses a real name or brand")):
        found = rule.search(text)
        if found:
            out.append(f"{label} {what}: '{found.group(0).strip()}'")
    return out


def check(entry, subs, traits, vocab, modifier=False):
    out = []
    name = entry.get("name")
    if not isinstance(name, str) or not name.strip():
        return ["no name"]
    if len(name) > MAX_NAME:
        out.append(f"name over {MAX_NAME} characters")
    if not 1 <= words(name) <= 6:
        out.append("name must be 1-6 words")
    if re.search(r"[\[\]\(\)]", name) or re.search(r"\s\d+$", name):
        out.append("name has brackets or ends in a number")
    if name != name.strip() or name[0].islower():
        out.append("name must start with a capital and have no stray spaces")
    if re.search(r"[,:@|<>\x22\x5c]", name):
        out.append("name uses a character the styles box gives a meaning to (, : @ |)")
    out += text_problems("name", name)

    if modifier:
        if entry.get("kind") not in MOD_KINDS:
            out.append(f"kind must be one of {sorted(MOD_KINDS)}")
        phrase = entry.get("nl")
        if not isinstance(phrase, str) or not 2 <= words(phrase) <= 14 or len(phrase) > 110:
            out.append("nl must be 2-14 words and at most 110 characters")
        else:
            if re.search(r"[.;:!?]$", phrase.strip()) or phrase != phrase.strip():
                out.append("nl must not end in punctuation")
            if NEGATION.search(phrase):
                out.append("nl describes what is absent; say what is there")
            out += text_problems("nl", phrase)
    else:
        cat, sub = entry.get("cat"), entry.get("sub")
        if cat not in subs:
            out.append(f"unknown cat '{cat}'")
        elif sub not in subs[cat]:
            out.append(f"'{sub}' is not a sub of {cat}")
        lead = entry.get("lead")
        if not isinstance(lead, str) or not 2 <= words(lead) <= 9 or len(lead) > MAX_LEAD:
            out.append(f"lead must be 2-9 words and at most {MAX_LEAD} characters")
        else:
            if lead[0].islower():
                out.append("lead must start with a capital")
            if re.search(r"[.,;:!?]$", lead.strip()) or "," in lead:
                out.append("lead must be one phrase with no commas or closing punctuation")
            out += text_problems("lead", lead)
        parts = entry.get("parts")
        if not isinstance(parts, list) or not 5 <= len(parts) <= 7:
            out.append("parts must be a list of 5-7 descriptors")
        else:
            seen = set()
            for part in parts:
                if not isinstance(part, str) or not 2 <= words(part) <= 9 or len(part) > MAX_PART:
                    out.append(f"part must be 2-9 words and at most {MAX_PART} characters: {part!r}")
                    continue
                if "," in part or re.search(r"[.;:!?]$", part.strip()) or part != part.strip():
                    out.append(f"part must be one phrase, no commas or closing punctuation: {part!r}")
                if part[0].isupper() and not re.match(r"[A-Z0-9]{2,}|[A-Z][a-z]*-?[A-Z]|[A-Z]\d", part):
                    out.append(f"part must start lower-case: {part!r}")
                if NEGATION.search(part):
                    out.append(f"part describes what is absent; say what is there: {part!r}")
                key = part.lower()
                if key in seen:
                    out.append(f"part repeated: {part!r}")
                seen.add(key)
                out += text_problems("part", part)
            if isinstance(lead, str) and len(", ".join([lead] + [str(p) for p in parts])) > MAX_CLAUSE:
                out.append(f"lead plus parts is over {MAX_CLAUSE} characters")
        got = entry.get("traits")
        if not isinstance(got, list) or not 2 <= len(got) <= 5 or len(set(got)) != len(got):
            out.append("traits must be 2-5 different values")
        elif not set(got) <= traits:
            out.append(f"unknown traits: {sorted(set(got) - traits)}")

    tags = entry.get("tags")
    low, high = (0, 4) if modifier else (2, 6)
    if not isinstance(tags, list) or not low <= len(tags) <= high or len(set(tags)) != len(tags):
        out.append(f"tags must be {low}-{high} different values")
    elif not set(tags) <= vocab:
        out.append(f"tags not in data/tags.txt: {sorted(set(tags) - vocab)}")
    return out


def read_jsonl(path):
    rows = []
    with open(path, "r", encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append((number, json.loads(line)))
            except ValueError as error:
                rows.append((number, {"name": None, "_error": f"not valid JSON: {error}"}))
    return rows


def read_shipped():
    rows = []
    for name in sorted(os.listdir(V2)):
        if not name.endswith(".json") or name.startswith("_"):
            continue
        with open(os.path.join(V2, name), "r", encoding="utf-8") as handle:
            data = json.load(handle)
        for index, entry in enumerate(data.get("styles") or data.get("modifiers") or [], 1):
            if "category" in data:          # a style file names its category once
                entry = dict(entry, cat=data["category"])
            rows.append((f"{name}#{index}", entry, name == "modifiers.json"))
    return rows


def main():
    subs, traits = load_taxonomy()
    vocab = load_vocab()
    problems, total, names = 0, 0, {}
    paths = [arg for arg in sys.argv[1:] if not arg.startswith("--")]
    if paths:
        items = []
        for path in paths:
            for number, entry in read_jsonl(path):
                items.append((f"{os.path.basename(path)}:{number}", entry, "kind" in entry))
    else:
        items = read_shipped()
    for where, entry, modifier in items:
        total += 1
        found = [entry["_error"]] if entry.get("_error") else check(
            entry, subs, traits, vocab, modifier=modifier)
        key = (entry.get("kind") if modifier else "style", str(entry.get("name")).lower())
        if key in names:
            found.append(f"name already used at {names[key]}")
        names.setdefault(key, where)
        for line in found:
            problems += 1
            print(f"{where}  {entry.get('name')!r}: {line}")
    print(f"\n{total} entries, {problems} problem(s)")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
