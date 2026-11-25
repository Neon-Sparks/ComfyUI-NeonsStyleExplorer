"""Neons Style Roller — rolls style language from a list of thousands of terms.

The list is data/roller_words.txt (built by tools/mine_roller.py) plus whatever
the user keeps in user/roller_words.txt. Every term carries an aspect (what
part of a look it describes) and the kinds of picture it suits, so a roll can
be narrowed to "anime" or "lighting" and still spread itself sensibly.

Nothing here talks to the network or takes a path from outside: the two files
are read from fixed places and every line is treated as text.
"""

import hashlib
import math
import os
import random
import re

HERE = os.path.dirname(os.path.abspath(__file__))
SHIPPED = os.path.join(HERE, "data", "roller_words.txt")
USER = os.path.join(HERE, "user", "roller_words.txt")

MAX_COUNT = 50
MAX_PINNED = 20
MAX_TERM = 80                       # characters, for a user's own line
MAX_BOX = 4000                      # characters read from a text box
MAX_USER_BYTES = 2 * 1024 * 1024
MAX_USER_TERMS = 20000

ASPECTS = ["look", "lighting", "colour", "texture", "mood", "composition", "movement", "shape"]
KINDS = ["realism", "anime", "cartoon", "comics", "painting", "illustration", "3d", "design",
         "abstract"]

# what the dropdowns show -> what the list calls it
KIND_CHOICES = {
    "all": None,
    "realism": "realism",
    "anime & manga": "anime",
    "cartoon & animation": "cartoon",
    "comics & print": "comics",
    "painting": "painting",
    "illustration & drawing": "illustration",
    "3D & games": "3d",
    "graphic design": "design",
    "abstract & experimental": "abstract",
}
ASPECT_CHOICES = {
    "any (balanced)": None,
    "look & medium": "look",
    "lighting": "lighting",
    "colour": "colour",
    "texture & surface": "texture",
    "mood": "mood",
    "composition & camera": "composition",
    "era & movement": "movement",
    "line & shape": "shape",
}
VOCABULARIES = ["everything", "well known", "deep cuts", "my words"]
OUTPUTS = ["phrases", "tags"]
POSITIONS = ["after text", "before text"]

# A balanced roll deals aspects from this deck, so "look" — the part that says
# what kind of picture it is — turns up about three times as often as each of
# the others, and five words are never five kinds of lighting.
DECK = ["look", "look", "look", "lighting", "colour", "texture", "mood", "composition",
        "movement", "shape"]
# with a kind chosen, how often a slot insists on a term written for that kind
KIND_BIAS = 0.75

# Pairs that cancel each other out in one prompt. (aspects or None, this, that)
_CONFLICTS = [
    (None,
     r"\b(monochrom\w*|black and white|gr[ae]yscale|1-?bit|sepia|desaturat\w*|muted|"
     r"colou?rless|achromatic|duotone)\b",
     r"\b(vivid|vibrant|(?<!de)saturated|colou?rful|rainbow|technicolor|neon|multicolou?r\w*|"
     r"candy|psychedelic|kaleidoscop\w*|hyper-?saturated|polychrom\w*)\b"),
    (None,
     r"\b(high-?key|overexposed|sun-?drenched|bleached|blown|daylight|sunlit|sunlight|noon|"
     r"golden hour|dawn|sunny)\b",
     r"\b(low-?key|nocturnal|night|shadowy|underexposed|pitch-?black|moonlit|moonlight|"
     r"midnight|noir|tenebris\w*|starlight|candlelit|candlelight)\b"),
    ({"lighting"},
     r"\b(soft|diffused|gentle|hazy|flat|overcast)\b",
     r"\b(hard|harsh|stark|sharp|spotlight)\b"),
    (None,
     r"\b(minimal|minimalis[mt]|minimalistic|sparse|uncluttered|understated|restrained|"
     r"austere|simplified)\b",
     r"\b(maximalis[mt]|ornate|intricate|dense|busy|cluttered|lavish|baroque|rococo|"
     r"hyper-?embellished|highly detailed|elaborate|opulent)\b"),
    ({"colour", "lighting"},
     r"\b(warm|amber|golden)\b",
     r"\b(cool|cold|icy|frosty)\b"),
    (None,
     r"\b(matte|chalky|powdery)\b",
     r"\b(gloss\w*|shiny|chrome|mirror\w*|lacquer\w*|wet)\b"),
    (None,
     r"\b(sharp focus|deep focus|razor-?sharp|tack-?sharp|sharp detail|crisp detail)\b",
     r"\b(blur\w*|soft focus|soft-focus|defocus\w*|out of focus)\b"),
    (None,
     r"\b(photoreal\w*|hyperreal\w*|lifelike|true to life|naturalistic|unretouched)\b",
     r"\b(abstract\w*|non-?representational|cartoon\w*|chibi|super deformed|flat vector|"
     r"pictogram\w*|pixel art|voxel\w*)\b"),
]
CONFLICTS = [(aspects, re.compile(a), re.compile(b)) for aspects, a, b in _CONFLICTS]

_cache = {"stamp": None, "terms": [], "index": {}}


def norm(text):
    key = str(text or "").lower().strip()
    key = key.replace("colour", "color").replace("grey", "gray")
    key = key.replace("stylis", "styliz").replace("artefact", "artifact")
    key = re.sub(r"[\-_]+", " ", key)
    return re.sub(r"\s+", " ", key)


def clean_term(text):
    """One line of someone's word list, made safe to put in a prompt."""
    text = re.sub(r"[\x00-\x1f\x7f]", " ", str(text or ""))
    text = re.sub(r"\s+", " ", text).strip().strip(",")
    return text[:MAX_TERM].strip()


def _flags(term, aspect):
    flags = set()
    for index, (aspects, this, that) in enumerate(CONFLICTS):
        if aspects and aspect not in aspects:
            continue
        if this.search(term):
            flags.add((index, 0))
        if that.search(term):
            flags.add((index, 1))
    return frozenset(flags)


def _make(term, aspect, kinds, tier, tag, user=False):
    key = norm(term)
    words = key.split()
    return {"term": term, "key": key, "aspect": aspect, "kinds": frozenset(kinds),
            "tier": tier, "tag": tag, "user": user, "head": words[-1] if words else "",
            "flags": _flags(key, aspect)}


def _parse(line, user=False):
    line = line.rstrip("\r\n")
    if not line.strip() or line.lstrip().startswith("#"):
        return None
    # the shipped file is tab-separated; a user's own may use | instead
    parts = [part.strip() for part in (line.split("\t") if "\t" in line else line.split("|"))]
    term = clean_term(parts[0])
    if not term:
        return None
    aspect = parts[1].lower() if len(parts) > 1 else "look"
    if aspect not in ASPECTS:
        aspect = "look"
    kinds = set()
    if len(parts) > 2 and parts[2] != "*":
        kinds = {kind for kind in parts[2].lower().split() if kind in KINDS}
    tier = parts[3] if len(parts) > 3 and parts[3] in ("a", "b") else "a"
    tag = clean_term(parts[4]) if len(parts) > 4 else ""
    return _make(term, aspect, kinds, tier, tag, user=user)


def _stamp():
    marks = []
    for path in (SHIPPED, USER):
        try:
            info = os.stat(path)
            marks.append((info.st_mtime_ns, info.st_size))
        except OSError:
            marks.append(None)
    return tuple(marks)


def _read(path, user=False):
    try:
        if user and os.path.getsize(path) > MAX_USER_BYTES:
            return []
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            lines = handle.readlines()
    except OSError:
        return []
    out = []
    for line in lines:
        row = _parse(line, user=user)
        if row:
            out.append(row)
        if user and len(out) >= MAX_USER_TERMS:
            break
    return out


def terms():
    """Every term, shipped then the user's own; re-read when either file changes."""
    stamp = _stamp()
    if _cache["stamp"] != stamp:
        seen, merged = set(), []
        # the user's line wins: it may re-file a shipped term under another kind
        for row in _read(USER, user=True) + _read(SHIPPED):
            if row["key"] in seen:
                continue
            seen.add(row["key"])
            merged.append(row)
        merged.sort(key=lambda row: (row["aspect"], row["key"]))
        _cache.update(stamp=stamp, terms=merged, index={})
    return _cache["terms"]


def signature():
    """Changes when the word list does, so a cached roll is not served stale."""
    return hashlib.sha1(repr(_stamp()).encode("utf-8")).hexdigest()[:12]


def counts():
    rows = terms()
    return {
        "total": len(rows),
        "user": sum(1 for row in rows if row["user"]),
        "kinds": {kind: sum(1 for row in rows if kind in row["kinds"]) for kind in KINDS},
        "aspects": {aspect: sum(1 for row in rows if row["aspect"] == aspect)
                    for aspect in ASPECTS},
    }


def split_list(text, limit=None):
    items = [clean_term(part) for part in re.split(r"[,\n;]", str(text or "")[:MAX_BOX])]
    items = [item for item in items if item]
    return items[:limit] if limit else items


def _ban_rule(bans):
    # a ban is a word or phrase: "neon" removes every term that contains it
    if not bans:
        return None
    return re.compile("(?<![a-z0-9])(?:" + "|".join(re.escape(ban) for ban in bans)
                      + ")(?![a-z0-9])")


def _groups(kind, aspect, vocabulary):
    """Candidate terms for one slot, grouped by their last word.

    Returned as (specific, universal): terms written for the chosen kind, and
    terms that suit any kind. Grouping by the last word is what stops a list
    with sixty kinds of "film grain" from rolling film grain sixty times as
    often as anything else — a group is drawn first, then a term inside it.
    """
    key = (kind, aspect, vocabulary)
    if key in _cache["index"]:
        return _cache["index"][key]
    specific, universal = {}, {}
    for row in terms():
        if row["aspect"] != aspect:
            continue
        if vocabulary == "well known" and row["tier"] != "a":
            continue
        if vocabulary == "deep cuts" and row["tier"] != "b":
            continue
        if vocabulary == "my words" and not row["user"]:
            continue
        if kind and row["kinds"]:
            if kind not in row["kinds"]:
                continue
            specific.setdefault(row["head"], []).append(row)
        elif kind:
            universal.setdefault(row["head"], []).append(row)
        else:
            specific.setdefault(row["head"], []).append(row)

    def pack(groups):
        names = sorted(groups)
        return names, [math.sqrt(len(groups[name])) for name in names], groups

    result = (pack(specific), pack(universal))
    _cache["index"][key] = result
    return result


def _draw(rng, packed):
    names, weights, groups = packed
    if not names:
        return None
    return rng.choice(groups[rng.choices(names, weights=weights, k=1)[0]])


def roll(count=5, kind="all", aspect="any (balanced)", vocabulary="everything", seed=0,
         never_include="", always_include=""):
    """Return ``(rolled, pinned, note)``: lists of term rows, and a line for the
    user when the roll could not be filled as asked."""
    try:
        count = max(0, min(MAX_COUNT, int(count)))
    except (TypeError, ValueError):
        count = 5
    kind_key = KIND_CHOICES.get(kind)
    aspect_key = ASPECT_CHOICES.get(aspect)
    if vocabulary not in VOCABULARIES:
        vocabulary = "everything"
    banned = _ban_rule([norm(item) for item in split_list(never_include, 100) if norm(item)])
    pinned = [_make(item, "look", (), "a", "", user=True)
              for item in split_list(always_include, MAX_PINNED)]

    rng = random.Random(int(seed)) if seed else random.Random()
    used = {row["key"] for row in pinned}
    heads = set()
    flags = set()
    for row in pinned:
        flags |= row["flags"]
    rolled = []

    def fits(row, strict):
        if row["key"] in used:
            return False
        if banned and banned.search(row["key"]):
            return False
        if any((index, 1 - side) in flags for index, side in row["flags"]):
            return False
        return not (strict and row["head"] in heads)

    def take(slot_aspect, lead):
        specific, universal = _groups(kind_key, slot_aspect, vocabulary)
        if not specific[0] and not universal[0]:
            return None
        for strict in (True, False):
            for _ in range(40):
                first, second = specific, universal
                # the leading word is always one written for the chosen kind
                if (kind_key and universal[0] and not lead
                        and (not specific[0] or rng.random() > KIND_BIAS)):
                    first, second = universal, specific
                row = _draw(rng, first) or _draw(rng, second)
                if row is not None and fits(row, strict):
                    return row
        # forty misses in a row means nearly everything is ruled out, not bad
        # luck: look at every term once rather than give up on the slot
        left = [row for packed in (specific, universal) for name in packed[0]
                for row in packed[2][name] if fits(row, False)]
        return rng.choice(left) if left else None

    deck = []
    for slot in range(count):
        if aspect_key:
            order = [aspect_key]
        else:
            if not deck:
                deck = list(DECK)
                rng.shuffle(deck)
            # the first word says what kind of picture this is
            first = "look" if slot == 0 else deck.pop()
            if slot == 0 and "look" in deck:
                deck.remove("look")
            order = [first] + [name for name in ASPECTS if name != first]
        row = None
        for slot_aspect in order:
            row = take(slot_aspect, lead=slot == 0)
            if row:
                break
        if row is None:
            break
        rolled.append(row)
        used.add(row["key"])
        heads.add(row["head"])
        flags |= row["flags"]

    note = ""
    if len(rolled) < count:
        scope = "your own word list" if vocabulary == "my words" else "this selection"
        note = (f"Only {len(rolled)} of {count} could be rolled: {scope} has no more terms "
                f"that fit. Widen the kind, aspect or vocabulary, or shorten never_include.")
    return rolled, pinned, note


def as_tag(row):
    tag = row["tag"] or re.sub(r"[\s\-]+", "_", row["term"].lower())
    return tag.replace("\\", "").replace("(", "\\(").replace(")", "\\)")


def plain_tag(row):
    """The term as a tag, unescaped: for saving, not for a prompt."""
    return row["tag"] or re.sub(r"[\s\-]+", "_", row["term"].lower())


def as_phrase(row):
    # a bracket in a user's own term would be read as prompt emphasis
    return row["term"].replace("\\", "").replace("(", "\\(").replace(")", "\\)")


def render(rows, output="phrases", weight=1.0):
    try:
        weight = max(0.1, min(2.0, float(weight)))
    except (TypeError, ValueError):
        weight = 1.0
    parts = [as_tag(row) if output == "tags" else as_phrase(row) for row in rows]
    if abs(weight - 1.0) > 0.001:
        parts = [f"({part.replace(':', ' -')}:{weight:.2f})" for part in parts]
    return ", ".join(parts)


def join_text(text, words, position="after text"):
    text = str(text or "").strip()
    if not words:
        return text
    if not text:
        return words
    if position == "before text":
        return f"{words}, {text}"
    return f"{text.rstrip(',').rstrip()}, {words}"
