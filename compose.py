"""Prompt composition.

A style entry is a style PREFIX and nothing else: it describes how the picture
is rendered and closes with the medium ("... anime style image"). No sentences
about what the image contains, no instructions to the model.

Layout (style_position = start):
    <quality>, <style clause ... style image.> <your prompt>
Layout (style_position = end):
    <quality>, <your prompt>, <style clause ... style image.>

The UI calls this through POST /neons_style/compose, so there is exactly one
implementation.
"""

import re

OUTPUT_FORMATS = ["natural", "danbooru", "natural + danbooru"]
STYLE_POSITIONS = ["start", "end"]
MIX_WORDS = {
    "blended with": "blended with",
    "mixed with": "mixed with",
    "layered over": "layered over",
    "then also": "then also",
}
TAG_SEPARATORS = {"comma+space": ", ", "comma": ",", "space": " "}
STYLE_WEIGHT_RANGE = (1.0, 5.0)


def weight_of(value):
    """Clamp the style-weight slider; 1.0 means no emphasis."""
    try:
        weight = float(value)
    except (TypeError, ValueError):
        return 1.0
    low, high = STYLE_WEIGHT_RANGE
    return max(low, min(high, weight))


def emphasise(text, weight):
    """Wrap text in ComfyUI's ``(text:weight)`` emphasis syntax."""
    weight = weight_of(weight)
    if weight <= 1.001 or not text:
        return text
    body = _drop_terminal(text).replace(":", " -")
    return f"({body}:{weight:.2f}),"


def clean(text):
    text = re.sub(r"[ \t]+", " ", str(text or "").strip())
    return re.sub(r"\n{3,}", "\n\n", text)


def _drop_terminal(text):
    """Strip the clause's closing punctuation — a comma now, a period before."""
    return re.sub(r"[.,\s]+$", "", clean(text))


def _lower_first(text):
    if not text:
        return text
    if len(text) > 1 and text[1].isupper():  # keep acronyms (CRT, VHS, 3D)
        return text
    return text[0].lower() + text[1:]


def split_terms(text):
    return [clean(part) for part in re.split(r"[,\n]", str(text or "")) if clean(part)]


def dedupe(items):
    seen, out = set(), []
    for item in items:
        key = str(item).strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(str(item).strip())
    return out


def join_prompt(parts):
    """Join prompt pieces, inserting ', ' only where punctuation is missing."""
    out = ""
    for part in parts:
        part = clean(part)
        if not part:
            continue
        if not out:
            out = part
            continue
        # a clause already ends in a comma, so do not add a second one
        out = f"{out} {part}" if re.search(r"[.!?;:,]$", out) else f"{out}, {part}"
    # the closing comma exists to hand over to the next part; with nothing
    # after it, it would only dangle
    return out.strip().rstrip(",")


# ---------------------------------------------------------------- entries

def entry_nl(entry):
    return clean(entry.get("nl") or "")


def entry_negative(entry):
    return clean(entry.get("negative") or "")


def entry_tags(entry):
    return [str(tag).strip() for tag in (entry.get("tags") or []) if str(tag).strip()]


def entry_negative_tags(entry):
    return [str(tag).strip() for tag in (entry.get("tags_negative") or []) if str(tag).strip()]


# ------------------------------------------------------------------ text

def entry_medium(entry):
    return clean(entry.get("medium") or "")


def strip_medium(entry):
    """The clause without its closing medium, so only one medium is emitted."""
    text = _drop_terminal(entry_nl(entry))
    medium = _drop_terminal(entry_medium(entry))
    if medium and text.lower().endswith(medium.lower()):
        text = text[: -len(medium)].rstrip(" ,;:")
    return text


def style_clause(styles, fmt=None, finish=None, mix="blended with", with_medium=True):
    """One clause chain from 1-3 styles plus optional format and finish.

    Only the leading entry's medium closes the chain: a magazine-cover format or
    a natural-skin finish must not end an anime prompt with 'photograph style
    image'. Their own mediums are stripped when something else already supplies
    one.
    """
    entries = [entry for entry in (styles or []) if entry]
    lead = entries[0] if entries else (fmt or finish)
    if lead is None:
        return ""

    word = MIX_WORDS.get(mix, "blended with")
    parts = []
    for index, entry in enumerate(entries):
        body = strip_medium(entry)
        if not body:
            continue
        parts.append(body if index == 0 else f"{word} {_lower_first(body)}")
    for extra in (fmt, finish):
        if not extra or extra is lead:
            continue
        body = _lower_first(strip_medium(extra))
        if body:
            parts.append(body)
    if lead in (fmt, finish) and not entries:
        body = strip_medium(lead)
        parts.insert(0, body) if body else None

    text = ", ".join(part for part in parts if part)
    # the closing medium can be switched off for the whole catalog: some
    # checkpoints read "photograph style image" as a subject rather than a look
    medium = _drop_terminal(entry_medium(lead)) if with_medium else ""
    if medium:
        text = f"{text}, {medium}" if text else medium
    # a prompt fragment, handed over to whatever the user typed
    return f"{text}," if text else ""


def compose_natural(prompt, quality, styles, fmt, finish, opts):
    clause = style_clause(styles, fmt, finish, opts.get("style_mix", "blended with"),
                          with_medium=bool(opts.get("close_with_medium", True)))
    clause = emphasise(clause, opts.get("style_weight", 1.0))
    prompt = clean(prompt)
    quality = _drop_terminal(quality)
    if not clause:
        return join_prompt([quality, prompt])
    if opts.get("style_position", "start") == "end":
        return join_prompt([quality, prompt, clause])
    return join_prompt([quality, clause, prompt])


def compose_natural_negative(negative, styles, fmt, finish, include_style_negative):
    terms = split_terms(negative)
    if include_style_negative:
        for entry in list(styles or []) + [e for e in (fmt, finish) if e]:
            terms.extend(split_terms(entry_negative(entry)))
    return ", ".join(dedupe(terms))


# ------------------------------------------------------------------ tags

def escape_tag(tag):
    """Escape the parentheses inside booru tags so prompt parsers keep them."""
    return str(tag).replace("\\", "").replace("(", "\\(").replace(")", "\\)")


def _weight(tags, weight):
    weight = weight_of(weight)
    if not tags:
        return tags
    if weight <= 1.001:
        return [escape_tag(tag) for tag in tags]
    return [f"({escape_tag(tag)}:{weight:.2f})" for tag in tags]


def collect_tags(styles, fmt, finish, weight):
    primary = dedupe(entry_tags(styles[0])) if styles else []
    rest = []
    for entry in (styles or [])[1:]:
        rest.extend(entry_tags(entry))
    for entry in (fmt, finish):
        if entry:
            rest.extend(entry_tags(entry))
    rest = [tag for tag in dedupe(rest) if tag not in primary]
    return _weight(primary, weight) + [escape_tag(tag) for tag in rest]


def compose_tags(prompt, quality, styles, fmt, finish, opts):
    separator = TAG_SEPARATORS.get(opts.get("tag_separator", "comma+space"), ", ")
    style_tags = collect_tags(styles, fmt, finish, opts.get("style_weight", 1.0))
    quality_tags = split_terms(quality)
    prompt_tags = split_terms(prompt)
    order = (
        quality_tags + prompt_tags + style_tags
        if opts.get("style_position", "start") == "end"
        else quality_tags + style_tags + prompt_tags
    )
    return separator.join(dedupe(order))


def compose_tags_negative(negative, styles, fmt, finish, include_style_negative, opts):
    separator = TAG_SEPARATORS.get(opts.get("tag_separator", "comma+space"), ", ")
    tags = split_terms(negative)
    entries = list(styles or []) + [e for e in (fmt, finish) if e]
    positive = set()
    for entry in entries:
        positive.update(entry_tags(entry))
    if include_style_negative:
        for entry in entries:
            tags.extend(escape_tag(tag) for tag in entry_negative_tags(entry) if tag not in positive)
    return separator.join(dedupe(tags))


# ------------------------------------------------------------- public API

DEFAULTS = {
    "output_format": "natural",
    "style_position": "start",
    "style_mix": "blended with",
    "tag_separator": "comma+space",
    "style_weight": 1.0,  # the node ships 1.5; the composer itself stays neutral
    "include_style_negative": True,
    "close_with_medium": True,
}


def compose(prompt="", quality="", negative="", styles=None, fmt=None, finish=None, **opts):
    """Return ``(positive, negative)`` for the active output format."""
    settings = dict(DEFAULTS)
    settings.update({key: value for key, value in opts.items() if value is not None})
    styles = [entry for entry in (styles or []) if entry]
    include_neg = bool(settings.get("include_style_negative", True))
    mode = settings.get("output_format", "natural")

    if mode == "danbooru":
        return (
            compose_tags(prompt, quality, styles, fmt, finish, settings),
            compose_tags_negative(negative, styles, fmt, finish, include_neg, settings),
        )

    positive = compose_natural(prompt, quality, styles, fmt, finish, settings)
    negative_text = compose_natural_negative(negative, styles, fmt, finish, include_neg)

    if mode == "natural + danbooru":
        tags = compose_tags("", "", styles, fmt, finish, settings)
        neg_tags = compose_tags_negative("", styles, fmt, finish, include_neg, settings)
        if tags:
            positive = f"{positive}\n\nTags: {tags}" if positive else f"Tags: {tags}"
        if neg_tags:
            negative_text = ", ".join(dedupe(split_terms(negative_text) + split_terms(neg_tags)))
    return positive, negative_text
