"""Build data/roller_words.txt — the Neons Style Roller's word list.

    python tools/mine_roller.py            write the list
    python tools/mine_roller.py --check    exit 1 if the file on disk is stale
    python tools/mine_roller.py --sample   print a sample of each aspect

Three sources, merged:

  tools/roller_core.txt   the hand-written core: the terms most models know
  styles/*.json           every short descriptor phrase the original catalog uses
  styles_v2/*.json        the leads and descriptors of the version 2 catalog

A style clause is a comma-separated run of descriptors, so the catalog already
holds thousands of pieces of style language. This script lifts them out, throws
away anything that names picture content or is not a self-standing term, and
sorts what is left by aspect (lighting, colour, texture ...) and by kind
(realism, anime, painting ...). The result is deterministic: the same inputs
always write the same file.
"""

import collections
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CORE = os.path.join(HERE, "roller_core.txt")
OUT = os.path.join(ROOT, "data", "roller_words.txt")
STYLES = os.path.join(ROOT, "styles")
STYLES_V2 = os.path.join(ROOT, "styles_v2")
VOCAB = os.path.join(ROOT, "data", "tags.txt")

ASPECTS = ["look", "lighting", "colour", "texture", "mood", "composition", "movement", "shape"]
KINDS = ["realism", "anime", "cartoon", "comics", "painting", "illustration", "3d", "design",
         "abstract"]

FAMILY_KIND = {
    "Anime & Manga": "anime",
    "Western Animation": "cartoon",
    "Comics & Print": "comics",
    "Traditional Painting": "painting",
    "Illustration": "illustration",
    "Photography & Film": "realism",
    "3D & Games": "3d",
    "Design & Aesthetics": "design",
    "Experimental & Material": "abstract",
}

# version 2 files are named for their category; this is the kind each one feeds
V2_KIND = {
    "photo": "realism", "cinema": "realism", "anime": "anime", "cartoon": "cartoon",
    "comics": "comics", "print": "comics", "paint": "painting", "draw": "illustration",
    "world": "painting", "cgi": "3d", "games": "3d", "design": "design",
    "aesthetic": "design", "genre": "illustration", "craft": "abstract",
    "abstract": "abstract",
}

MAX_WORDS = 4
MAX_CHARS = 34

# ------------------------------------------------------------------ rejects

# what a picture shows, rather than how it is made
CONTENT = re.compile(
    r"\b(wom[ae]n|m[ae]n|girls?|boys?|person|people|child(?:ren)?|bab(?:y|ies)|figures?|faces?|"
    r"facial|characters?|creatures?|animals?|cats?|dogs?|birds?|fish|horses?|dragons?|robots?|"
    r"mechas?|monsters?|cit(?:y|ies)|cityscapes?|skylines?|buildings?|skyscrapers?|rooms?|"
    r"interiors?|houses?|homes?|forests?|trees?|woods|mountains?|oceans?|seas?|beach(?:es)?|"
    r"rivers?|lakes?|sk(?:y|ies)|flowers?|blossoms?|petals?|gardens?|oasis|grottos?|deserts?|"
    r"jungles?|castles?|temples?|ruins|cars?|vehicles?|spaceships?|ships?|weapons?|swords?|"
    r"guns?|food|fruits?|hair|eyes?|lips|skin|hands?|bod(?:y|ies)|limbs?|heads?|clothing|"
    r"cloth(?:es)?|dress(?:es)?|costumes?|uniforms?|armou?r|scenes?|scenery|backgrounds?|"
    r"backdrops?|subjects?|objects?|motifs?|imagery|interfaces?|heroes|heroines?|villains?|"
    r"warriors?|knights?|soldiers?|samurai|ninjas?|witch(?:es)?|wizards?|angels?|demons?|"
    r"ghosts?|skulls?|skeletons?|planets?|stars|galax(?:y|ies)|nebulae?|moons?|suns|"
    r"streets?(?! photography| art)|roads?|alleys?|bridges?|villages?|towns?|landscapes?"
    r"(?! painting| photography)|seascapes?|portraits?(?! photography| painting| lighting)|"
    r"nudes?|erotic|nsfw|sexy|gore|blood|makeup|eyewear|jewell?ery|musculature|anatomy|"
    r"rain|snow|storms?|sun|nature|wildlife|urban|architecture|columns?|banners?|"
    r"crowds?|fashion(?! illustration| photography)|"
    r"clouds|cloud(?! pattern|s| render)|cumul\w+|foliage|leaves|leafy|vegetation|meadows?|"
    r"fields(?! of)|waves|flames|rocks|cliffs?|caves?|waterfalls?|gazes?|ripples|"
    r"gemstones?|jewels|feathers|wings|horns|tentacles|machinery|circuitry|"
    r"viewer|logo|text|caption|watermark|signature)\b"
)

# words that only make sense inside the clause the phrase was cut from
DANGLING = re.compile(
    r"\b(richer|more|less|fewer|no|not|without|never|only|each|every|its|their|that|which|"
    r"where|than|into|onto|from|across|between|behind|against|kept|left|held|built|made|"
    r"drawn|chosen|shown|seen|reads?|as|at|by|to|for|on|over|under|through|within|around|"
    r"per|with|the|a|an|is|are|was|be|but|or|so|then|still|very|just|rather|instead|"
    r"itself|themselves|like|one|two|three|four|five|six|both|all|any|some|other|same|"
    r"alone|together|nothing|everything|something|general)\b"
)
# ... unless the whole term is a known fixed expression
FIXED = {
    "rule of thirds", "depth of field", "shallow depth of field", "pen and ink",
    "ink in water", "frame within a frame", "dust and scratches", "black and white",
    "arts and crafts", "wet-on-wet", "wet on wet", "alla prima", "art of the title",
    "trompe l'oeil", "day for night", "long exposure", "point of view",
}
QUALITY = re.compile(r"\b(4k|8k|16k|uhd|hd|hdr|masterpiece|best quality|award[- ]winning|"
                     r"trending|artstation|deviantart|pixiv|behance|unsplash|"
                     r"ultra[- ]detailed|high[- ]quality|high[- ]resolution|professional)\b")
# real studios, people and brands: the catalog describes looks, not names
NAMES = re.compile(r"\b(ghibli|disney|pixar|marvel|dc comics|dreamworks|nintendo|pokemon|"
                   r"magritte|dali|picasso|van gogh|monet|klimt|mucha|rembrandt|vermeer|"
                   r"caravaggio|hokusai|warhol|banksy|giger|escher|miyazaki|tarantino|"
                   r"kubrick|wes anderson|lynch|moebius|leica|hasselblad|kodak|fuji(?:film)?|"
                   r"polaroid|canon|nikon|sony|lego|barbie|inspired)\b")
ALLOWED = re.compile(r"^[a-z0-9][a-z0-9 '&.\-]*[a-z0-9.]$")
WEAK_HEADS = {"capture", "truth", "feel", "feeling", "sense", "quality", "effect", "effects",
              "vibe", "vibes", "elements", "details", "detail", "touches", "accents", "work",
              "treatment", "handling", "approach", "manner", "way", "kind", "type", "idea"}

# ------------------------------------------------------------------ aspects

ASPECT_RULES = [
    ("lighting", re.compile(
        r"\b(light(?:ing|s|ed)?|\w+light|lit|backlit|sunlit|moonlit|candlelit|glow(?:ing|s)?|"
        r"shadows?|shading|chiaroscuro|tenebris[mt]|rim|illuminat\w*|luminous|luminosity|"
        r"flares?|haze|god rays|sunbeams?|sun rays|rays|beams?|bloom|halation|highlights?|"
        r"spotlight|silhouettes?|radian(?:t|ce)|gleam\w*|shimmer\w*|glint\w*|caustics?|"
        r"bioluminescen\w+|phosphorescen\w+|golden hour|blue hour|twilight|dusk|dawn|"
        r"overcast|flash|strobe|exposure glow)\b")),
    ("colour", re.compile(
        r"\b(palettes?|tones?|toned|hues?|colou?rs?|colou?red|colou?ring|monochrom\w*|"
        r"duotone|tritone|pastels?|saturat\w*|desaturat\w*|gradients?|black and white|"
        r"grayscale|greyscale|sepia|tint(?:ed|s)?|chroma\w*|technicolor|cmyk|rgb|ombre|"
        r"red|orange|yellow|green|blue|purple|violet|pink|magenta|cyan|teal|turquoise|"
        r"indigo|cobalt|crimson|scarlet|amber|ochre|gold(?:en)?|silver|bronze|copper|"
        r"emerald|sapphire|ruby|ivory|beige|brown|umber|sienna|charcoal|contrast)\b")),
    ("composition", re.compile(
        r"\b(composition|compositional|framing|framed|perspective|angle|angles|lens|lenses|"
        r"depth of field|bokeh|exposure|shot|shots|close-?up|symmetr\w*|asymmetr\w*|"
        r"negative space|blur(?:red|ry)?|focus|fisheye|tilt-?shift|macro|wide-?angle|"
        r"telephoto|panoram\w*|aerial|bird'?s-?eye|worm'?s-?eye|isometric|orthographic|"
        r"foreshorten\w*|cropp?(?:ed|ing)?|layout|vignett\w*|shutter|zoom|pov|viewpoint|"
        r"vantage|overhead|top-?down|flat lay|knolling|camera movement|motion trails?|"
        r"long exposure|panning|rule of thirds|leading lines|focal|diptych|triptych)\b")),
    ("texture", re.compile(
        r"\b(textur\w*|grain(?:y|ed)?|surfaces?|brush\w*|strokes?|impasto|halftone|"
        r"stippl\w*|hatch\w*|cross-?hatch\w*|noise|noisy|scanlines?|dither\w*|glitch\w*|"
        r"paper|canvas|patina|weather(?:ed|ing)|distress\w*|scratch\w*|dust|grit(?:ty)?|"
        r"splatter\w*|drips?|smudg\w*|bleed|washes|wash|glaz\w*|sheen|gloss\w*|matte|"
        r"satin|velvet\w*|metallic|chrome|foil|emboss\w*|crackl\w*|craquelure|peeling|"
        r"rust\w*|tarnish\w*|artefacts?|artifacts?|pixelat\w*|aberration|screentones?|"
        r"speckl\w*|mottl\w*|marbl\w*|frost\w*|finish|sgraffito|scumbl\w*|dry-?brush|"
        r"woven|knit\w*|embroider\w*|felt|wool|fibr\w*|fiber\w*|threads?|grainy)\b")),
    ("mood", re.compile(
        r"\b(atmospher\w*|mood\w*|dream\w*|ethereal|eerie|melanchol\w*|serene|serenity|"
        r"nostalgi\w*|whimsical|whimsy|ominous|mysterious|mystery|mystical|haunting|"
        r"haunted|tranquil\w*|romantic|dramatic|drama|epic|cosy|cozy|gloomy|gloom|"
        r"brooding|uncanny|unsettling|sinister|macabre|sombre|somber|bleak|desolat\w*|"
        r"lonel\w*|contemplative|meditative|playful|joyful|cheerful|tense|tension|"
        r"suspense\w*|chaotic|chaos|feverish|hallucinat\w*|magical|enchant\w*|solemn|"
        r"sacred|spiritual|dystopian|utopian|apocalyptic|noir|wistful|bittersweet|"
        r"hopeful|foreboding|otherworldly|cosmic|pastoral|idyllic|nocturnal|surreal\w*|"
        r"liminal|quiet|stillness|calm|energy|energetic|vibe)\b")),
    ("movement", re.compile(
        r"(\b\w+ism\b|\b\w+ist\b|\b\w+core\b|\b\w+punk\b|\b\w+wave\b|\b(baroque|rococo|"
        r"renaissance|gothic|medieval|byzantine|victorian|edwardian|art deco|art nouveau|"
        r"bauhaus|de stijl|ukiyo-?e|pop art|op art|retro\w*|vintage|mid-?century|"
        r"\d{2,4}s|neo-?\w+|post-?\w+|futuris\w+|avant-?garde|classical|antique|"
        r"ancient|folk|tribal|art brut|jugendstil|secession|memphis|y2k|era)\b)")),
    ("shape", re.compile(
        r"\b(geometr\w*|shapes?|forms?|lines?|linework|line art|lineart|outlines?|"
        r"contours?|patterns?|curves?|curv\w+|angular|circles?|squares?|triang\w*|"
        r"grids?|lattice|tessellat\w*|spirals?|stripes?|striped|dots?|dotted|edges?|"
        r"edged|proportions?|faceted|blocky|polygon\w*|fractal\w*|voronoi|mandala\w*|"
        r"kaleidoscop\w*|arabesque|ornament\w*|filigree|borders?|planes?|planar|"
        r"volumes?|volumetric forms|structures?|symmetry)\b")),
]

# ------------------------------------------------------------------- kinds

KIND_RULES = {
    "anime": re.compile(r"\b(anime|manga|manhwa|manhua|donghua|chibi|shonen|shoujo|shojo|"
                        r"seinen|josei|moe|kawaii|cel-?shad\w*|cel|otaku|mecha|bishou?jo|"
                        r"bishou?nen|light novel|visual novel|gacha|doujin|screentones?|"
                        r"tokusatsu|gekiga|webtoon)\b"),
    "cartoon": re.compile(r"\b(cartoon\w*|animation|animated|rubber-?hose|toon|claymation|"
                          r"stop-?motion|cutout animation|caricature|storyboard|puppet\w*|"
                          r"squash and stretch|mascot)\b"),
    "comics": re.compile(r"\b(comics?|comix|graphic novel|pulp|halftone|ben-?day|risograph|"
                         r"riso|screen-?print\w*|silkscreen|linocut|woodcut|woodblock|"
                         r"letterpress|lithograph\w*|etching|engrav\w*|mezzotint|aquatint|"
                         r"offset|zine|poster|print(?:ed|s|making)?|overprint|misregist\w*|"
                         r"xerox|photocop\w*|stamp|tarot|ligne claire|inked panel|panels?)\b"),
    "painting": re.compile(r"\b(paint(?:ing|ed|erly|s)?|oils?|watercolou?rs?|gouache|"
                           r"acrylics?|tempera|fresco|encaustic|impasto|palette-?knife|"
                           r"brush\w*|canvas|glaz\w*|sfumato|grisaille|plein-?air|"
                           r"alla prima|underpainting|sumi-?e|nihonga|ink wash|pastels?|"
                           r"impressionis\w+|expressionis\w+|fauvis\w+|baroque|rococo|"
                           r"renaissance|tenebris\w+|chiaroscuro|pointillis\w+|mural)\b"),
    "illustration": re.compile(r"\b(illustrat\w*|drawing|drawn|sketch\w*|pencil\w*|graphite|"
                               r"charcoal|crayon|marker|ballpoint|pen|ink(?:ed|ing|s)?|"
                               r"stippl\w*|hatch\w*|cross-?hatch\w*|storybook|picture book|"
                               r"scratchboard|doodle|line art|lineart|linework|"
                               r"calligraph\w*|concept art|botanical)\b"),
    "realism": re.compile(r"\b(photo\w*|film|filmic|cinema\w*|lens\w*|exposure|bokeh|shutter|"
                          r"35mm|16mm|8mm|70mm|analog(?:ue)?|camera|focus|depth of field|"
                          r"realis\w+|hyperreal\w*|documentary|darkroom|daguerreotype|"
                          r"tintype|cyanotype|infrared|aperture|iso|negative|kodachrome|"
                          r"emulsion|flash|strobe|vhs|footage|super 8|anamorphic)\b"),
    "3d": re.compile(r"\b(3d|cgi|render(?:ed|ing|s)?|voxels?|low-?poly|polygon\w*|pixel\w*|"
                     r"8-?bit|16-?bit|32-?bit|isometric|shader|shaders|ray-?trac\w*|"
                     r"path-?trac\w*|subsurface|wireframe|game|sprite|sprites|engine|"
                     r"sculpt(?:ed|ing)?|zbrush|matcap|ambient occlusion|photogrammetry|"
                     r"diorama|miniature|claymorph\w*|vinyl toy|papercraft)\b"),
    "design": re.compile(r"\b(vector|graphic|design|typograph\w*|bauhaus|swiss|constructivis\w+|"
                         r"memphis|brutalis\w+|minimalis\w+|flat|logo|emblem|icon|"
                         r"pictogram|infographic|diagram\w*|blueprint|schematic|signage|"
                         r"lettering|packaging|layout|art deco|art nouveau|mid-?century|"
                         r"aesthetic|\w+core|\w+punk|\w+wave|y2k|frutiger|skeuomorph\w*|"
                         r"glassmorph\w*|pattern|textile|wallpaper|mosaic|stained glass)\b"),
    "abstract": re.compile(r"\b(abstract\w*|geometr\w*|glitch\w*|datamosh\w*|pixel-?sort\w*|"
                           r"fractal\w*|generative|algorithmic|procedural|psychedelic|"
                           r"kaleidoscop\w*|surreal\w*|liminal|non-?representational|"
                           r"op art|moire|voronoi|cubis\w+|suprematis\w+|dada\w*|"
                           r"deconstruct\w*|fragment\w*|biomorph\w*|amorphous|collage|"
                           r"assemblage|double exposure|multiple exposure|photogram|"
                           r"experimental|distort\w*|warp\w*|fluid|marbl\w*)\b"),
}

# aspects that suit every kind unless the term itself says otherwise
UNIVERSAL = {"lighting", "colour", "mood", "composition", "shape"}


def norm(term):
    key = term.lower().strip()
    key = key.replace("colour", "color").replace("grey", "gray")
    key = key.replace("stylis", "styliz").replace("artefact", "artifact")
    key = re.sub(r"[\-_]+", " ", key)
    key = re.sub(r"\s+", " ", key)
    return key


def tidy(term):
    term = re.sub(r"\s+", " ", str(term or "")).strip().strip(".,;:").lower()
    return term


def acceptable(term, mined=True):
    if not term or len(term) > MAX_CHARS or len(term) < 3:
        return False
    words = term.split()
    if not ALLOWED.match(term):
        return False
    if not mined:
        return len(words) <= MAX_WORDS + 2
    if len(words) > MAX_WORDS:
        return False
    if QUALITY.search(term) or NAMES.search(term) or CONTENT.search(term):
        return False
    if term not in FIXED and norm(term) not in FIXED and DANGLING.search(term):
        return False
    if words[-1] in WEAK_HEADS:
        return False
    if re.search(r"\d", term) and not re.search(
            r"\b(3d|2d|2\.5d|35mm|16mm|8mm|70mm|8-?bit|16-?bit|32-?bit|1-?bit|"
            r"\d{2,4}s|super 8|y2k|ps1|n64)\b", term):
        return False
    return True


def aspect_of(term):
    # the last word is what the term IS ("charcoal grain texture" is a
    # texture, not a colour), so it gets the first say
    head = term.split()[-1]
    for aspect, rule in ASPECT_RULES:
        if rule.search(head):
            return aspect
    for aspect, rule in ASPECT_RULES:
        if rule.search(term):
            return aspect
    return "look"


def kinds_of(term):
    return {kind for kind, rule in KIND_RULES.items() if rule.search(term)}


def read_core():
    terms, aspect, kinds = [], None, set()
    with open(CORE, "r", encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("@"):
                left, _, right = line[1:].partition("|")
                aspect = left.strip()
                kinds = set() if right.strip() == "*" else set(right.split())
                if aspect not in ASPECTS or not kinds <= set(KINDS):
                    raise SystemExit(f"bad section in roller_core.txt: {line}")
                continue
            term, _, tag = line.partition("=>")
            term = tidy(term)
            if not acceptable(term, mined=False):
                raise SystemExit(f"bad term in roller_core.txt: {line}")
            terms.append({"term": term, "aspect": aspect, "kinds": set(kinds),
                          "tier": "a", "tag": tag.strip()})
    return terms


def read_vocab():
    tags = set()
    if os.path.isfile(VOCAB):
        with open(VOCAB, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line and not line.startswith("#"):
                    tags.add(line)
    return tags


def read_styles():
    rows = []
    for path in sorted(glob.glob(os.path.join(STYLES, "*.json"))):
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        items = data if isinstance(data, list) else next(
            (value for value in data.values() if isinstance(value, list)), [])
        rows.extend(item for item in items if isinstance(item, dict))
    return rows


def read_v2():
    """(category, style) for every version 2 style."""
    rows = []
    for path in sorted(glob.glob(os.path.join(STYLES_V2, "*.json"))):
        base = os.path.basename(path)
        if base.startswith("_") or base == "modifiers.json":
            continue
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        for style in data.get("styles") or []:
            if isinstance(style, dict):
                rows.append((data.get("category", ""), style))
    return rows


def phrases(entry):
    medium = tidy(entry.get("medium"))
    out = []
    for part in str(entry.get("nl") or "").split(","):
        part = tidy(part)
        if not part or part == medium or part.endswith("style image"):
            continue
        out.append(part)
    return out


def build():
    vocab = read_vocab()
    table = collections.OrderedDict()

    for row in read_core():
        key = norm(row["term"])
        if key in table:
            raise SystemExit(f"roller_core.txt lists '{row['term']}' twice")
        table[key] = row

    mined = {}
    for entry in read_styles():
        family = entry.get("family", "")
        family_kind = FAMILY_KIND.get(family)
        found = [p for p in phrases(entry) if acceptable(p)]
        # an imported style has no family worth trusting: vote from its phrases
        votes = collections.Counter()
        for phrase in found:
            votes.update(kinds_of(phrase))
        style_kinds = {family_kind} if family_kind else {
            kind for kind, count in votes.items() if count == max(votes.values())}
        for phrase in found:
            slot = mined.setdefault(norm(phrase), {
                "term": phrase, "count": 0, "votes": collections.Counter(),
                "imported": False})
            slot["count"] += 1
            slot["imported"] = slot["imported"] or not family_kind
            slot["votes"].update(style_kinds)
            # prefer the plain spelling: fewer hyphens, then alphabetical
            if (phrase.count("-"), phrase) < (slot["term"].count("-"), slot["term"]):
                slot["term"] = phrase

    for category, entry in read_v2():
        kind = V2_KIND.get(category)
        for phrase in [tidy(entry.get("lead"))] + [tidy(part) for part in entry.get("parts") or []]:
            if not acceptable(phrase):
                continue
            slot = mined.setdefault(norm(phrase), {
                "term": phrase, "count": 0, "votes": collections.Counter(),
                "imported": False})
            slot["count"] += 1
            # a version 2 descriptor is written to stand alone, so it is kept
            # on the same terms as an imported keyword
            slot["imported"] = True
            if kind:
                slot["votes"][kind] += 1
            if (phrase.count("-"), phrase) < (slot["term"].count("-"), slot["term"]):
                slot["term"] = phrase

    for key in sorted(mined):
        if key in table:
            continue
        slot = mined[key]
        term = slot["term"]
        aspect = aspect_of(term)
        kinds = kinds_of(term)
        # A written clause is cut at its commas, and a piece that matches no
        # rule at all is usually half a thought ("general painted", "tight
        # blues"). The imported styles are keyword lists already, so their
        # pieces stand alone and are kept.
        if not slot["imported"]:
            head = term.split()[-1]
            if aspect == "look" and not kinds:
                continue
            # ... and its last word has to be style vocabulary in its own
            # right: "warm bounce light" stands alone, "beige and grey
            # mouldings" names a thing
            if not (any(rule.search(head) for _a, rule in ASPECT_RULES)
                    or any(rule.search(head) for rule in KIND_RULES.values())):
                continue
        if not kinds and aspect not in UNIVERSAL and slot["votes"]:
            top = max(slot["votes"].values())
            kinds = {kind for kind, count in slot["votes"].items() if count * 2 >= top}
        tag = key.replace(" ", "_")
        table[key] = {"term": term, "aspect": aspect, "kinds": kinds,
                      "tier": "a" if slot["count"] >= 3 else "b",
                      "tag": tag if tag in vocab else ""}

    rows = sorted(table.values(), key=lambda row: (ASPECTS.index(row["aspect"]), row["term"]))
    return rows


def render(rows):
    lines = [
        "# Neons Style Roller word list. Written by tools/mine_roller.py - do not edit.",
        "# Your own words go in user/roller_words.txt, one per line (see MANUAL.md).",
        "#",
        "# term <tab> aspect <tab> kinds (* = every kind) <tab> tier (a = well known,",
        "# b = deep cut) <tab> booru tag, when the term has a real one",
        "",
    ]
    for row in rows:
        kinds = " ".join(kind for kind in KINDS if kind in row["kinds"]) or "*"
        lines.append("\t".join([row["term"], row["aspect"], kinds, row["tier"], row["tag"]]).rstrip())
    return "\n".join(lines) + "\n"


def main():
    rows = build()
    text = render(rows)
    if "--sample" in sys.argv:
        import random
        rng = random.Random(7)
        for aspect in ASPECTS:
            pool = [row for row in rows if row["aspect"] == aspect and row["tier"] == "b"]
            print(f"\n== {aspect} ({len(pool)} mined deep cuts)")
            for row in rng.sample(pool, min(40, len(pool))):
                print(f"   {row['term']:36s} {' '.join(sorted(row['kinds'])) or '*'}")
        return
    if "--check" in sys.argv:
        current = ""
        if os.path.isfile(OUT):
            with open(OUT, "r", encoding="utf-8", newline="") as handle:
                current = handle.read().replace("\r\n", "\n")
        if current != text:
            print("data/roller_words.txt is stale: run python tools/mine_roller.py")
            sys.exit(1)
        print(f"roller word list is current ({len(rows)} terms)")
        return
    with open(OUT, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    by_aspect = collections.Counter(row["aspect"] for row in rows)
    by_kind = collections.Counter(kind for row in rows for kind in (row["kinds"] or {"*"}))
    print(f"{len(rows)} terms -> {os.path.relpath(OUT, ROOT)}")
    print("  aspects:", ", ".join(f"{a} {by_aspect[a]}" for a in ASPECTS))
    print("  kinds:  ", ", ".join(f"{k} {by_kind[k]}" for k in KINDS + ["*"]))
    print("  well known:", sum(1 for row in rows if row["tier"] == "a"))


if __name__ == "__main__":
    main()
