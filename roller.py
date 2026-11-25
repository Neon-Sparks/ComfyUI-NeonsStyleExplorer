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

ASPECTS = ["look", "lighting", "colour", "texture", "mood", "composition", "movement", "shape",
           "effects"]
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
# An aspect choice is one aspect, or a deck of them to deal from.
#   big changes   the words that decide what kind of picture it is
#   fine details  the words that adjust a picture without changing its kind
ASPECT_CHOICES = {
    "any (balanced)": None,
    "big changes (look, era, colour, light)": ("look", "look", "look", "movement", "movement",
                                               "colour", "colour", "lighting", "effects"),
    "fine details (texture, shape, mood, camera)": ("texture", "texture", "shape", "shape",
                                                    "mood", "composition", "lighting"),
    "look & medium": "look",
    "lighting": "lighting",
    "colour": "colour",
    "texture & surface": "texture",
    "mood": "mood",
    "composition & camera": "composition",
    "era & movement": "movement",
    "line & shape": "shape",
    "effects & magic": "effects",
}
VOCABULARIES = ["everything", "well known", "deep cuts", "my words"]
LENGTHS = {"any": (1, 99), "one word": (1, 1), "one or two words": (1, 2),
           "three or more words": (3, 99)}

# A theme is a flavour that cuts across kinds and aspects: "dark & gothic" finds
# dark lighting, dark palettes, gothic looks and grim moods alike. A term
# belongs to every theme whose rule it matches. The shipped list carries its
# themes ready-made (tools/mine_roller.py writes them); a user's own words are
# matched as they are read.
THEME_CHOICES = {
    "any": None,
    "retro & vintage": "retro",
    "futuristic & cyber": "future",
    "dark & gothic": "dark",
    "bright & playful": "playful",
    "fantasy & mythic": "fantasy",
    "historical & world": "historic",
    "handmade & craft": "craft",
    "nature & seasons": "nature",
    "neon & glow": "neon",
    "minimal & clean": "minimal",
    "ornate & detailed": "ornate",
}
_THEMES = {
    "retro": r"retro\w*|vintage|nostalg\w*|old(?:-\w+)?|olden|antique|aged|\d{2,4}s|mid-?century|"
             r"victorian|edwardian|art deco|art nouveau|bygone|throwback|classic|heirloom|sepia|"
             r"faded|yellowed|analog(?:ue)?|vhs|crt|8-?bit|16-?bit|pulp|golden age|silver age|"
             r"old-?school|period piece",
    "future": r"futur\w*|cyber\w*|sci-?fi|neon\w*|hologra\w*|tech\w*|robot\w*|chrome|glitch\w*|"
              r"digital|synth\w*|space-?age|laser\w*|\w+punk|plasma|android|mecha\w*|circuit\w*|"
              r"hud|virtual|galactic|stellar|atomic|nano\w*|bio-?mech\w*|next-?gen|high-?tech",
    "dark": r"dark\w*|goth\w*|noir|horror|macabre|eerie|sinister|gloom\w*|shadow\w*|grim\w*|"
            r"haunt\w*|occult|black|pitch-?black|nocturnal|midnight|ominous|creepy|spooky|"
            r"ghost\w*|infernal|hellish|demonic|doom\w*|bleak|sombre|somber|morbid|dread\w*|"
            r"nightmar\w*|cursed|murky|low-?key|tenebris\w*|underworld|sooty|charred",
    "playful": r"cute|cutesy|kawaii|playful|whimsical|whimsy|candy|pastel\w*|bubbl\w*|cheerful|"
               r"cartoon\w*|toy\w*|bright|rainbow|joy\w*|happy|funny|silly|quirky|wacky|zany|"
               r"chibi|doodle\w*|sticker\w*|sugary|sweet|bouncy|lively|colou?rful|sunny|jolly|"
               r"merry|kidcore|crayon|comical|jazzy|funky|groovy",
    "fantasy": r"fantas\w*|myth\w*|fairy\w*|pixie|magic\w*|enchant\w*|celestial|heavenly|angelic|"
               r"spell\w*|sorcery|rune\w*|sigil\w*|mana|portal|wisp\w*|stardust|"
               r"divine|holy|sacred|mystic\w*|legend\w*|arcane|ethereal|dream\w*|otherworld\w*|"
               r"spirit\w*|alchem\w*|esoteric|wizard\w*|witch\w*|heroic|epic|storybook|"
               r"folklore|wonder\w*|halo|aura|astral|supernatural|bewitched|blessed",
    "historic": r"ancient|medieval|renaissance|baroque|rococo|classical|neoclassic\w*|gothic|"
                r"byzantine|romanesque|antique|archaic|histor\w*|folk|tribal|traditional|"
                r"dynasty|imperial|colonial|feudal|egyptian|greek|roman|celtic|norse|nordic|"
                r"persian|mughal|ottoman|ukiyo-?e|illuminat\w*|fresco|tempera|heritage|"
                r"ancestral|prehistoric|primeval|mesoamerican|indigenous|regency|georgian",
    "craft": r"handmade|hand-?made|hand-?craft\w*|craft\w*|paper\w*|textile\w*|woven|weav\w*|"
             r"embroider\w*|ceramic\w*|clay|carv\w*|collage\w*|stitch\w*|quilt\w*|knit\w*|"
             r"crochet\w*|felt\w*|wool\w*|thread\w*|origami|mosaic|stained glass|wood\w*|"
             r"linocut|woodcut|block print|pottery|porcelain|enamel\w*|bead\w*|macram\w*|"
             r"cardboard|plasticine|braided|tufted|patchwork",
    "nature": r"organic|botanic\w*|floral|earth\w*|natural\w*|moss\w*|aquatic|oceanic|tropical|"
              r"arctic|polar|desert|volcanic|autumn\w*|wint\w*|spring\w*|summer\w*|seasonal|"
              r"pastoral|rustic|rural|weather\w*|biomorph\w*|mineral|crystal\w*|stony|wooden|"
              r"sunlit|dappled|misty|foggy|dewy|frost\w*|stormy|lunar|solar",
    "neon": r"neon\w*|glow\w*|fluoresc\w*|luminesc\w*|luminous|radiant|laser\w*|blacklight|"
            r"ultraviolet|bioluminesc\w*|phosphor\w*|electric|plasma|incandescent|day-?glo|"
            r"holograph\w*|iridescen\w*|emissive|strobe|aurora",
    "minimal": r"minimal\w*|clean|simple|simplif\w*|flat|sparse|plain|tidy|uncluttered|"
               r"understated|restrained|austere|pure|sleek|crisp|negative space|monochrom\w*|"
               r"quiet|subtle|bare|neat|monotone",
    "ornate": r"ornate|ornament\w*|intricate|detail\w*|elaborate|lavish|opulent|dense|"
              r"maximalis\w*|baroque|rococo|filigree|gilded|decorat\w*|embellish\w*|rich|"
              r"luxur\w*|sumptuous|jewel\w*|pattern\w*|arabesque|damask|lace\w*|extravagant",
}
THEME_RULES = {key: re.compile(rf"(?<![a-z0-9])(?:{rule})(?![a-z0-9])")
               for key, rule in _THEMES.items()}
# with a theme chosen, how often a slot insists on a term from that theme
THEME_BIAS = 0.7
OUTPUTS = ["phrases", "tags"]
POSITIONS = ["after text", "before text"]

# A balanced roll deals aspects from this deck, so "look" — the part that says
# what kind of picture it is — turns up about three times as often as each of
# the others, and five words are never five kinds of lighting.
DECK = ["look", "look", "look", "lighting", "colour", "texture", "mood", "composition",
        "movement", "shape", "effects"]
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
# most terms take no side in anything; one test rules them out before sixteen
_ANY_CONFLICT = re.compile("|".join(f"(?:{side})" for _a, a, b in _CONFLICTS for side in (a, b)))

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
    if not _ANY_CONFLICT.search(term):
        return frozenset()
    flags = set()
    for index, (aspects, this, that) in enumerate(CONFLICTS):
        if aspects and aspect not in aspects:
            continue
        if this.search(term):
            flags.add((index, 0))
        if that.search(term):
            flags.add((index, 1))
    return frozenset(flags)


def themes_of(text):
    key = norm(text)
    return frozenset(name for name, rule in THEME_RULES.items() if rule.search(key))


def _make(term, aspect, kinds, tier, tag, user=False, themes=None):
    key = norm(term)
    words = key.split()
    return {"term": term, "key": key, "aspect": aspect, "kinds": frozenset(kinds),
            "tier": tier, "tag": tag, "user": user, "head": words[-1] if words else "",
            "flags": _flags(key, aspect), "length": len(words),
            "themes": themes_of(key) if themes is None else frozenset(themes)}


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
    # the shipped list names its themes; anything else is matched here
    themes = None
    if len(parts) > 5 and not user:
        themes = [name for name in parts[5].split() if name in THEME_RULES]
    return _make(term, aspect, kinds, tier, tag, user=user, themes=themes)


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


def _groups(kind, aspect, vocabulary, length="any", theme=None):
    """Candidate terms for one slot, grouped by their last word.

    Returned as (specific, universal): terms written for the chosen kind, and
    terms that suit any kind. Grouping by the last word is what stops a list
    with sixty kinds of "film grain" from rolling film grain sixty times as
    often as anything else — a group is drawn first, then a term inside it.
    With *theme* given, only terms of that theme are returned.
    """
    key = (kind, aspect, vocabulary, length, theme)
    if key in _cache["index"]:
        return _cache["index"][key]
    low, high = LENGTHS.get(length, LENGTHS["any"])
    specific, universal = {}, {}
    for row in terms():
        if row["aspect"] != aspect:
            continue
        if not low <= row["length"] <= high:
            continue
        if theme and theme not in row["themes"]:
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


def roll_detail(count=5, kind="all", aspect="any (balanced)", vocabulary="everything", seed=0,
                never_include="", always_include="", theme="any", words_per_term="any"):
    """Roll, and say how: ``{"rolled", "pinned", "note", "seed"}``.

    *seed* 0 means "roll afresh", but the roll is still made from a seed — a
    random one — and that seed is reported, so a roll someone likes can be
    kept by setting it.
    """
    try:
        count = max(0, min(MAX_COUNT, int(count)))
    except (TypeError, ValueError):
        count = 5
    kind_key = KIND_CHOICES.get(kind)
    aspect_key = ASPECT_CHOICES.get(aspect)
    theme_key = THEME_CHOICES.get(theme)
    length = words_per_term if words_per_term in LENGTHS else "any"
    if vocabulary not in VOCABULARIES:
        vocabulary = "everything"
    banned = _ban_rule([norm(item) for item in split_list(never_include, 100) if norm(item)])
    pinned = [_make(item, "look", (), "a", "", user=True)
              for item in split_list(always_include, MAX_PINNED)]

    try:
        seed = int(seed)
    except (TypeError, ValueError):
        seed = 0
    if not 0 < seed <= 0xFFFFFFFF:
        seed = random.SystemRandom().randint(1, 0xFFFFFFFF)
    rng = random.Random(seed)
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

    def search(pools, lead):
        specific, universal = pools
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

    def take(order, lead):
        # A theme leads the roll and flavours most of it, but leaves room for
        # words from outside it: ten words that all say "dark" is not a style.
        # A themed slot looks through every aspect it may use before it gives
        # up on the theme, because a theme is thin in some aspects.
        if theme_key and (lead or rng.random() < THEME_BIAS):
            for slot_aspect in order:
                row = search(_groups(kind_key, slot_aspect, vocabulary, length, theme_key), lead)
                if row:
                    return row
        for slot_aspect in order:
            row = search(_groups(kind_key, slot_aspect, vocabulary, length), lead)
            if row:
                return row
        return None

    source = list(aspect_key) if isinstance(aspect_key, tuple) else list(DECK)
    deck = []
    for slot in range(count):
        if isinstance(aspect_key, str):
            order = [aspect_key]
        else:
            if not deck:
                deck = list(source)
                rng.shuffle(deck)
            # the first word says what kind of picture this is
            first = "look" if slot == 0 and "look" in source else deck.pop()
            if slot == 0 and first == "look" and "look" in deck:
                deck.remove("look")
            rest = [name for name in dict.fromkeys(source) if name != first]
            # a deck's own aspects come first; the others only if it runs dry
            order = [first] + rest + [name for name in ASPECTS if name != first and name not in rest]
        row = take(order, lead=slot == 0)
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
                f"that fit. Widen the kind, theme, aspect, vocabulary or words per term, or "
                f"shorten never_include.")
    return {"rolled": rolled, "pinned": pinned, "note": note, "seed": seed}


def roll(**kwargs):
    """Return ``(rolled, pinned, note)``: lists of term rows, and a line for the
    user when the roll could not be filled as asked."""
    out = roll_detail(**kwargs)
    return out["rolled"], out["pinned"], out["note"]


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
