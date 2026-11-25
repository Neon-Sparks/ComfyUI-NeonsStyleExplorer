"""Neons Style Explorer — nodes."""

import hashlib
import random
import uuid

from . import compose as composer
from . import loras
from . import models
from . import nodes2
from . import roller
from . import runs
from .catalog import (RANDOM_TOKEN, SOURCES, crawl_names, custom_names, entries,
                      imported_style_names, names_for, push_recent, resolve, roll,
                      scope_fell_back, source_pool, written_names)

WEB_DIRECTORY = "./web"

ROLL_SCOPES = ["all", "family", "favourites", "recent", "has preview", "missing preview"]
LORA_ROLL_SCOPES = ["all", "same gallery", "same family", "favourites"]


def _combo(axis):
    return ["None", RANDOM_TOKEN] + names_for(axis)


def widgets():
    # the main slots carry the written catalog only; imported and custom entries
    # have their own dropdowns, which keeps every menu short enough to open
    styles = ["None"] + written_names("style")
    return {
        "prompt": ("STRING", {
            "multiline": True, "dynamicPrompts": True, "default": "",
            "tooltip": "Your subject and scene.",
        }),
        "quality": ("STRING", {
            "multiline": True, "dynamicPrompts": True, "default": "",
            "tooltip": "Quality prefix, kept at the very front of the prompt (e.g. masterpiece, best quality, highres).",
        }),
        "negative": ("STRING", {
            "multiline": True, "dynamicPrompts": True, "default": "",
            "tooltip": "Your avoid terms. Style negatives are merged in when enabled.",
        }),
        "style": (styles, {
            "default": "None",
            "tooltip": "The written catalog. Only one style slot is active at a time — choosing here switches the others off.",
        }),
        "extra_style": (["None"] + imported_style_names(), {
            "default": "None",
            "tooltip": "The imported [Extra] pack, kept out of the main dropdowns so those stay quick to open. Composes as another style slot.",
        }),
        "custom_style": (["None"] + custom_names("style"), {
            "default": "None",
            "tooltip": "Your own styles only — anything you wrote in the editor. Composes as a fourth style slot. Empty until you create one; use Refresh Node Definitions after adding one.",
        }),
        "format": (_combo("format"), {
            "default": "None",
            "tooltip": "Optional picture format (sheet, cover, contact sheet, widescreen...).",
        }),
        "finish": (_combo("finish"), {
            "default": "None",
            "tooltip": "Optional finish qualifier layered on top of the style.",
        }),
        "output_format": (composer.OUTPUT_FORMATS, {
            "default": "natural",
            "tooltip": "natural = sentences. danbooru = booru tags. both = sentences plus a tag line.",
        }),
        "style_position": (composer.STYLE_POSITIONS, {
            "default": "start",
            "tooltip": "Put the style clause in front of your prompt or after it.",
        }),
        "close_with_medium": ("BOOLEAN", {
            "default": True, "label_on": "close with medium", "label_off": "no closing medium",
            "tooltip": "Every written clause ends with its medium — 'anime style image', 'photograph style image', 'oil painting style image'. Turn this off to drop that closing phrase from every prompt, for checkpoints that read it as a subject rather than a look. Booru output is unaffected; the medium is not a tag.",
        }),
        "include_style_negative": ("BOOLEAN", {
            "default": True,
            "tooltip": "Merge the style's own avoid terms into the negative output.",
        }),
        "style_weight": ("FLOAT", {
            "default": 1.0, "min": 1.0, "max": 5.0, "step": 0.05, "round": 0.01,
            "display": "slider",
            "tooltip": "How hard the style pushes. 1.0 = no emphasis. Wraps the style clause as (clause:weight) in natural mode and every style tag as (tag:weight) in booru modes.",
        }),
        "tag_separator": (list(composer.TAG_SEPARATORS.keys()), {
            "default": "comma+space",
            "tooltip": "Booru modes: how tags are joined.",
        }),
        "crawl": ("BOOLEAN", {
            "default": False, "label_on": "crawl through", "label_off": "crawl off",
            "tooltip": "Walk the main style dropdown one entry per queued run instead of rolling, so a batch fills the gallery in order. It starts from whatever style is selected, so park on the one you want to begin at. Turns the dice off on every slot while it is on; the set it walks is roll_scope (use 'missing preview' with auto_gallery to fill the gaps).",
        }),
        "crawl_source": (list(SOURCES), {
            "default": "main",
            "tooltip": "Which dropdown crawl walks: main (the written catalog), extra (the imported pack), or custom (your own styles).",
        }),
        "crawl_missing_only": ("BOOLEAN", {
            "default": False, "label_on": "only missing previews", "label_off": "every entry",
            "tooltip": "While crawling, skip styles that already have a preview. The list is re-checked at every step, so entries drop out as their previews are made. Ignored when crawl is off.",
        }),
        "auto_gallery": (["off", "first", "every"], {
            "default": "off",
            "tooltip": "Save generated images to the style gallery automatically.",
        }),
        "random_roll": ("BOOLEAN", {
            "default": False, "label_on": "random style", "label_off": "chosen style",
            "tooltip": "Roll a random style for every run instead of using the dropdowns. Which pool it draws from is random_source, narrowed further by roll_scope; roll_seed decides the roll. Crawl overrides it while crawl is on.",
        }),
        "random_source": (("all",) + tuple(SOURCES), {
            "default": "all",
            "tooltip": "Where a random style comes from: all three lists, main (the written catalog), extra (the imported pack), or custom (your own styles).",
        }),
        "roll_scope": (ROLL_SCOPES, {
            "default": "all",
            "tooltip": "Which styles the dice may land on, and which set crawl walks: everything, the primary style's family, your favourites, recently used, or by preview state. An empty favourites or recent list rolls from everything, and the debug output says so.",
        }),
        "roll_seed": ("INT", {
            "default": 54321, "min": 0, "max": 0xFFFFFFFF,
            "control_after_generate": True,
            "tooltip": "Seeds the dice. Use the control under it (randomize / increment) so every run rolls a different style; 0 also rolls freshly each run. The control only advances while random_roll is on.",
        }),
    }


LORA_TRIGGER_INPUTS = {
    f"lora_triggers_{n}": ("STRING", {
        "forceInput": True,
        "tooltip": "Trigger words from a Neons LoRA Explorer's 'triggers' output. "
                   "They are placed at the very start of the composed prompt, "
                   "before the quality prefix, in input order. Duplicates are dropped.",
    })
    for n in (1, 2, 3)
}


def lora_triggers(kwargs):
    """The trigger strings wired in, in order, without repeats."""
    seen, out = set(), []
    for n in (1, 2, 3):
        for term in str(kwargs.get(f"lora_triggers_{n}") or "").split(","):
            term = term.strip()
            if term and term.lower() not in seen:
                seen.add(term.lower())
                out.append(term)
    return out


def pick_styles(values, pool, scope, family, seed, previews, crawl=False,
                kwargs_missing_only=False, random_roll=False, source="all"):
    """The styles one run composes with.

    random_roll replaces the dropdowns entirely: the dice used to live in the
    lists themselves, which meant picking it and losing sight of what you had
    chosen. Crawl still wins — it owns the sequence.
    """
    if random_roll and not crawl:
        entry = roll(axis="style", scope=scope, family=family, seed=seed or None,
                     previews=previews, source=source)
        return [entry] if entry else []
    picked, used = [], set()
    for value in values:
        if value == RANDOM_TOKEN and crawl:
            # crawl mode owns the sequence: the dice must not fire underneath it.
            # An unresolved dice on the main slot falls back to the first entry
            # of the crawl set, so a run is never styleless.
            names = crawl_names(
                scope, family, previews,
                missing_only=bool(kwargs_missing_only),
            ) if not picked else []
            entry = resolve(names[0], pool) if names else None
        elif value == RANDOM_TOKEN:
            entry = roll(
                axis="style", scope=scope, family=family, seed=seed or None,
                previews=previews, exclude=used,
            )
        else:
            entry = resolve(value, pool)
        if entry and entry["axis"] == "style" and entry["name"] not in used:
            used.add(entry["name"])
            picked.append(entry)
    return picked


def pick_axis(value, axis, pool, previews, crawl=False):
    if value == RANDOM_TOKEN and crawl:
        return None  # no rolling anywhere while crawling
    if value == RANDOM_TOKEN:
        return roll(axis=axis, previews=previews)
    entry = resolve(value, pool)
    return entry if entry and entry["axis"] == axis else None


def _random_line(kwargs):
    """How the dice is set, and whether its source had anything in it."""
    if not kwargs.get("random_roll"):
        return "off"
    source = str(kwargs.get("random_source", "all") or "all")
    scope = str(kwargs.get("roll_scope", "all") or "all")
    if source != "all" and not source_pool(source):
        return f"on — {source} is empty, rolled from the whole catalog instead"
    if scope_fell_back(scope, source):
        # an empty shortlist rolls from everything; say so rather than letting
        # the dice look as though it ignored the scope
        where = "the whole catalog" if source == "all" else f"every {source} style"
        return f"on — {source}, but '{scope}' is empty so it rolled from {where} instead"
    return f"on — {source}, scope {scope}"


def build_debug(kwargs, positive, negative, styles, fmt, finish):
    lines = [
        "Neons Style Explorer",
        f"output_format:  {kwargs.get('output_format')}",
        f"style_position: {kwargs.get('style_position')}",
        f"styles:         {' + '.join(e['name'] for e in styles) or 'None'}",
        f"format:         {fmt['name'] if fmt else 'None'}",
        f"finish:         {finish['name'] if finish else 'None'}",
        f"medium:         {styles[0]['medium'] if styles else 'n/a'}",
        f"style_weight:   {kwargs.get('style_weight', 1.0)}",
        f"closing medium: {'on' if kwargs.get('close_with_medium', True) else 'off'}",
        f"random:         {_random_line(kwargs)}",
        f"crawl:          {'on — ' + str(kwargs.get('roll_scope', 'all')) + (', missing previews only' if kwargs.get('crawl_missing_only') else '') if kwargs.get('crawl') else 'off'}",
        f"hand-written:   {all(e['written'] for e in styles) if styles else 'n/a'}",
        "",
        "QUALITY", kwargs.get("quality") or "(empty)",
        "", "PROMPT", kwargs.get("prompt") or "(empty)",
        "", "USER NEGATIVE", kwargs.get("negative") or "(empty)",
        "", "COMPOSED POSITIVE", positive or "(empty)",
        "", "COMPOSED NEGATIVE", negative or "(empty)",
    ]
    return "\n".join(lines)


def style_slots(kwargs):
    return [kwargs.get("style", "None"), kwargs.get("custom_style", "None"),
            kwargs.get("extra_style", "None")]


def family_hint_of(kwargs, pool):
    """The family 'family' scope works from: whichever slot holds a concrete
    style, since slot 1 may be the dice itself."""
    for field in ("style", "custom_style", "extra_style"):
        entry = resolve(kwargs.get(field, "None"), pool)
        if entry:
            return entry["family"]
    return None


def is_rolling(kwargs):
    """Is the dice deciding this run's style?

    An older workflow may still hold the dice token in a slot; that is what the
    switch means now. Crawl owns the sequence while it is on.
    """
    if bool(kwargs.get("crawl", False)):
        return False
    return bool(kwargs.get("random_roll", False)) or RANDOM_TOKEN in style_slots(kwargs)


def style_name_of(styles):
    """The name of the style a run used, for the style_name output."""
    return styles[0]["name"] if styles else ""


def run(**kwargs):
    from .gallery import manifest

    pool = entries()
    previews = manifest()
    seed = int(kwargs.get("roll_seed") or 0)
    scope = kwargs.get("roll_scope", "all")
    crawl = bool(kwargs.get("crawl", False))
    family_hint = family_hint_of(kwargs, pool)

    slots = style_slots(kwargs)
    random_roll = bool(kwargs.get("random_roll", False)) or RANDOM_TOKEN in slots
    styles = pick_styles(
        # one active slot, but all three are read so an older workflow that set
        # several still composes rather than losing a style silently
        slots,
        pool, scope, family_hint, seed, previews, crawl,
        bool(kwargs.get("crawl_missing_only", False)),
        random_roll=random_roll,
        source=str(kwargs.get("random_source", "all") or "all"),
    )
    fmt = pick_axis(kwargs.get("format", "None"), "format", pool, previews, crawl)
    finish = pick_axis(kwargs.get("finish", "None"), "finish", pool, previews, crawl)

    triggers = lora_triggers(kwargs)
    positive, negative = composer.compose(
        prompt=kwargs.get("prompt", ""),
        quality=kwargs.get("quality", ""),
        negative=kwargs.get("negative", ""),
        styles=styles,
        fmt=fmt,
        finish=finish,
        output_format=kwargs.get("output_format", "natural"),
        style_position=kwargs.get("style_position", "start"),
        close_with_medium=bool(kwargs.get("close_with_medium", True)),
        lora_triggers=triggers,
        style_mix=kwargs.get("style_mix", "blended with"),
        tag_separator=kwargs.get("tag_separator", "comma+space"),
        style_weight=kwargs.get("style_weight", 1.0),
        include_style_negative=kwargs.get("include_style_negative", True),
    )
    if styles:
        # remember what was actually used, so 'recent' scope and the browser's
        # Recent filter reflect real runs (including dice rolls)
        push_recent(styles[0]["name"])
    debug = build_debug(kwargs, positive, negative, styles, fmt, finish)
    return positive, negative, debug, styles


def encode(clip, text):
    tokens = clip.tokenize(text or "")
    if hasattr(clip, "encode_from_tokens_scheduled"):
        return clip.encode_from_tokens_scheduled(tokens)
    cond, pooled = clip.encode_from_tokens(tokens, return_pooled=True)
    return [[cond, {"pooled_output": pooled}]]


class _Base:
    CATEGORY = "Neons"

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        """Re-run when the *meaning* of the inputs changes.

        ComfyUI caches a node whose widget values are unchanged — and editing a
        style leaves every widget exactly as it was while changing the clause
        behind the name. The run was then skipped and the sampler kept the old
        conditioning: the browser showed the edit, the picture did not. Folding
        the resolved entries into the signature fixes that, and nothing else
        re-runs: pick the same style twice and the signature repeats.
        """
        pool = entries()
        parts = []

        def fold(field, entry):
            if not entry:
                parts.append(f"{field}=None")
                return
            parts.append("|".join([
                field, entry["id"], entry.get("nl", ""), entry.get("medium", ""),
                entry.get("negative", ""), ",".join(entry.get("tags") or []),
                ",".join(entry.get("tags_negative") or []),
            ]))

        for field in ("style", "extra_style", "custom_style", "format", "finish"):
            fold(field, resolve(kwargs.get(field, "None"), pool))

        # A dice on the format or finish slot is unseeded, and roll_seed 0 means
        # "roll afresh every run". Neither moves a widget, so without this the
        # node was served from cache and the promised new roll never happened.
        crawl = bool(kwargs.get("crawl", False))
        if not crawl and RANDOM_TOKEN in (kwargs.get("format"), kwargs.get("finish")):
            return uuid.uuid4().hex
        if is_rolling(kwargs):
            seed = int(kwargs.get("roll_seed") or 0)
            if not seed:
                return uuid.uuid4().hex
            # A seeded roll repeats only while its pool stands still, and the
            # pool moves without any widget moving — a favourite starred, a
            # preview saved under 'missing preview'. Fold in what the dice
            # would land on now: the run is skipped only when the answer is
            # the same one.
            from .gallery import manifest

            fold("rolled", roll(
                axis="style", scope=kwargs.get("roll_scope", "all"),
                family=family_hint_of(kwargs, pool), seed=seed, previews=manifest(),
                source=str(kwargs.get("random_source", "all") or "all"),
            ))
        return hashlib.sha1("\n".join(parts).encode("utf-8")).hexdigest()

    @classmethod
    def VALIDATE_INPUTS(cls, style=None, custom_style=None, extra_style=None,
                        format=None, finish=None, **_kw):
        pool = entries()
        for value in (style, custom_style, extra_style, format, finish):
            if value in (None, "", "None", RANDOM_TOKEN):
                continue
            if resolve(value, pool) is None:
                return f"Unknown style: {value}"
        return True

    def _record(self, unique_id, kwargs, styles):
        """Log the style this prompt really used, so auto-gallery can ask the
        server rather than read a widget that has since moved on."""
        if not styles:
            return
        runs.record(
            runs.current_prompt_id(),
            unique_id,
            style=styles[0]["name"],
            mode=kwargs.get("auto_gallery", "off"),
            prompt=kwargs.get("prompt", ""),
        )

    def _ui(self, kwargs, styles):
        return {
            "ns_style": [styles[0]["name"] if styles else ""],
            "ns_style_id": [styles[0]["id"] if styles else ""],
            "ns_rolled": [", ".join(e["name"] for e in styles)],
            "ns_prompt": [kwargs.get("prompt") or ""],
            "ns_auto_gallery": [kwargs.get("auto_gallery", "off")],
            "ns_crawl": [bool(kwargs.get("crawl", False))],
        }


class NeonsStyleExplorer(_Base):
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": widgets(), "optional": dict(LORA_TRIGGER_INPUTS),
                "hidden": {"unique_id": "UNIQUE_ID"}}

    # style_name is last so the outputs a saved workflow already wires keep
    # their positions
    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("positive", "negative", "debug", "style_name")
    OUTPUT_TOOLTIPS = (
        "The composed prompt.",
        "The composed avoid terms.",
        "What the node did and why — wire it to a Preview Text node.",
        "The style this run used, rolls and crawl steps included; empty when no style "
        "is set. Use it in a filename, a label, or Gallery Capture's style_name.",
    )
    FUNCTION = "apply"
    DESCRIPTION = "Neons Style Explorer — style prefixes in natural language or booru tags."

    def apply(self, unique_id=None, **kwargs):
        positive, negative, debug, styles = run(**kwargs)
        self._record(unique_id, kwargs, styles)
        return {"ui": self._ui(kwargs, styles),
                "result": (positive, negative, debug, style_name_of(styles))}


class NeonsStyleExplorerEncode(_Base):
    @classmethod
    def INPUT_TYPES(cls):
        required = {"clip": ("CLIP",)}
        required.update(widgets())
        return {"required": required, "optional": dict(LORA_TRIGGER_INPUTS),
                "hidden": {"unique_id": "UNIQUE_ID"}}

    RETURN_TYPES = ("CONDITIONING", "CONDITIONING", "STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("positive_conditioning", "negative_conditioning", "positive", "negative",
                    "debug", "style_name")
    FUNCTION = "apply"
    DESCRIPTION = "Neons Style Explorer with CLIP encode."

    def apply(self, clip, unique_id=None, **kwargs):
        positive, negative, debug, styles = run(**kwargs)
        self._record(unique_id, kwargs, styles)
        return {
            "ui": self._ui(kwargs, styles),
            "result": (encode(clip, positive), encode(clip, negative), positive, negative,
                       debug, style_name_of(styles)),
        }


class NeonsGalleryCapture:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "style_name": ("STRING", {"default": ""}),
                "mode": (["first", "always", "off"], {"default": "first"}),
            },
            "optional": {"prompt": ("STRING", {"forceInput": True})},
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("image", "saved_file")
    FUNCTION = "capture"
    CATEGORY = "Neons"
    DESCRIPTION = "Save this image into a style's preview gallery."
    OUTPUT_NODE = True

    def capture(self, image, style_name, mode="first", prompt=""):
        from .gallery import add_shot, has_shots

        name = (style_name or "").split(",")[0].strip()
        if mode == "off" or not name or name == "None":
            return (image, "")
        if mode == "first" and has_shots(name):
            return (image, "")
        saved = add_shot(resolve(name) or name, image, prompt=prompt)
        return (image, saved["file"] if saved else "")


class NeonsLoraExplorer:
    """A LoRA loader with the gallery beside it.

    The picker is grouped by the folders in ComfyUI's loras directory: the
    top-level folder is a gallery and a folder inside it is a family, so
    `loras/krea 2/portraits/soft.safetensors` is the "portraits" family of the
    "krea 2" gallery. Each gallery keeps its own previews, which is the whole
    point — the same LoRA behaves differently on different checkpoints.
    """

    @classmethod
    def INPUT_TYPES(cls):
        available = loras.names(refresh=True)
        return {
            "required": {
                "model": ("MODEL",),
                "clip": ("CLIP",),
                "lora": (["None"] + available, {
                    "default": "None",
                    "tooltip": "Which LoRA to load. Grouped by the folders in your loras directory: the top folder is its gallery, a folder inside that is its family.",
                }),
                "strength_model": ("FLOAT", {
                    "default": 1.0, "min": -20.0, "max": 20.0, "step": 0.01,
                    "tooltip": "How strongly the LoRA is applied to the model.",
                }),
                "strength_clip": ("FLOAT", {
                    "default": 1.0, "min": -20.0, "max": 20.0, "step": 0.01,
                    "tooltip": "How strongly the LoRA is applied to the text encoder.",
                }),
                "random_roll": ("BOOLEAN", {
                    "default": False, "label_on": "random LoRA", "label_off": "chosen LoRA",
                    "tooltip": "Roll a random LoRA for every run instead of using the dropdown, at a strength drawn from the range below. roll_seed decides the roll — set its control to randomize.",
                }),
                "random_low": ("FLOAT", {
                    "default": 0.6, "min": -20.0, "max": 20.0, "step": 0.05,
                    "tooltip": "Lowest strength a random roll may choose. Applied to both the model and the text encoder.",
                }),
                "random_high": ("FLOAT", {
                    "default": 1.0, "min": -20.0, "max": 20.0, "step": 0.05,
                    "tooltip": "Highest strength a random roll may choose. Set it equal to random_low to roll the LoRA but keep a fixed strength.",
                }),
                "roll_seed": ("INT", {
                    "default": 54321, "min": 0, "max": 0xFFFFFFFF,
                    "control_after_generate": True,
                    "tooltip": "Seeds the roll: which LoRA, and which strength inside the range. Use the control under it (randomize) so every run differs; 0 also rolls freshly each run.",
                }),
            },
            # Optional, and last: a workflow saved before this existed loads
            # every value in its place, and an API-format prompt that does not
            # mention it still validates.
            "optional": {
                "roll_scope": (LORA_ROLL_SCOPES, {
                    "default": "all",
                    "tooltip": "Which LoRAs a random roll may land on: all of them, only the gallery (top folder) of the LoRA chosen above, only its family (the folder inside that), or your favourites. Keeps the dice inside the LoRAs made for the model you are using. An empty set rolls from all of them.",
                }),
            },
            "hidden": {"unique_id": "UNIQUE_ID"},
        }

    @classmethod
    def IS_CHANGED(cls, lora="None", strength_model=1.0, strength_clip=1.0,
                   random_roll=False, random_low=0.6, random_high=1.0, roll_seed=0,
                   roll_scope="all", **_kw):
        """Re-run when the trigger words change, not just when the LoRA does."""
        name = str(lora or "None")
        if random_roll:
            # seed 0 rolls afresh each run, which no widget change announces
            if not int(roll_seed or 0):
                return uuid.uuid4().hex
            # a seeded roll depends on the pool — a rescan or a new favourite
            # moves it — so key on what the dice lands on now
            name = cls._roll(roll_seed, random_low, random_high, roll_scope, name)[0]
        triggers = loras.triggers_for(name) if name != "None" else ""
        parts = [name, triggers, str(strength_model), str(strength_clip),
                 str(bool(random_roll)), str(random_low), str(random_high), str(roll_seed),
                 str(roll_scope)]
        return hashlib.sha1("\n".join(parts).encode("utf-8")).hexdigest()

    @classmethod
    def VALIDATE_INPUTS(cls, roll_scope="all"):
        """Accept whatever an older workflow left in roll_scope.

        Naming the input here takes it out of ComfyUI's own dropdown check. A
        workflow saved before the widget existed restores values by position
        and can leave an empty string in it; refusing to run over a setting
        that falls back to "all" anyway would be a poor welcome to an update.
        """
        return True

    RETURN_TYPES = ("MODEL", "CLIP", "STRING", "STRING")
    RETURN_NAMES = ("model", "clip", "lora_name", "triggers")
    FUNCTION = "apply"
    CATEGORY = "Neons"
    DESCRIPTION = "Neons LoRA Explorer — load a LoRA, with a preview gallery per model folder."

    @staticmethod
    def roll_pool(scope="all", anchor="None"):
        """(the LoRAs a roll may land on, whether the scope had to be widened).

        The folders are the filing, so a scope is just a folder test: the same
        gallery is the same top folder as the LoRA in the picker, the same
        family is the same folder inside it. A scope with nothing in it — no
        favourites yet, no LoRA picked to take the folder from — widens to
        every LoRA rather than loading none, and reports that it did.
        """
        everything = [name for name in loras.names() if name]
        anchor = str(anchor or "None").replace("\\", "/")
        scope = str(scope or "all")
        if scope not in LORA_ROLL_SCOPES:
            scope = "all"       # an older workflow can hand this slot anything
        if scope == "all":
            return everything, False
        pool = []
        if scope == "favourites":
            wanted = set(loras.load_favourites())
            pool = [name for name in everything if name in wanted]
        elif scope in ("same gallery", "same family") and anchor not in ("", "None"):
            gallery, family, _label = loras.split(anchor)
            for name in everything:
                other_gallery, other_family, _other = loras.split(name)
                if other_gallery != gallery:
                    continue
                if scope == "same family" and other_family != family:
                    continue
                pool.append(name)
        return (pool, False) if pool else (everything, True)

    @classmethod
    def _roll(cls, seed, low, high, scope="all", anchor="None"):
        """Pick a LoRA and a strength inside the range.

        The range is read in either order, so low=1.0 high=0.6 behaves the same
        as the other way round rather than rolling nothing.
        """
        pool, _widened = cls.roll_pool(scope, anchor)
        if not pool:
            return "None", 0.0
        rng = random.Random(seed) if seed else random
        low, high = (low, high) if low <= high else (high, low)
        chosen = rng.choice(pool)
        strength = low if low == high else round(rng.uniform(low, high), 3)
        return chosen, strength

    def apply(self, model, clip, lora="None", strength_model=1.0, strength_clip=1.0,
              random_roll=False, random_low=0.6, random_high=1.0, roll_seed=0,
              roll_scope="all", unique_id=None):
        note = ""
        if random_roll:
            if self.roll_pool(roll_scope, lora)[1]:
                note = f"'{roll_scope}' is empty — rolled from every LoRA"
            lora, strength = self._roll(roll_seed, random_low, random_high, roll_scope, lora)
            strength_model = strength_clip = strength
        name = str(lora or "None")
        triggers = loras.triggers_for(name) if name != "None" else ""
        if name in ("", "None") or (not strength_model and not strength_clip):
            return {"ui": self._ui(name, note),
                    "result": (model, clip, "" if name == "None" else name, triggers)}

        import comfy.sd
        import comfy.utils
        import folder_paths

        path = folder_paths.get_full_path("loras", name)
        if not path:
            return {"ui": self._ui(name, note), "result": (model, clip, name, triggers)}
        weights = comfy.utils.load_torch_file(path, safe_load=True)
        patched_model, patched_clip = comfy.sd.load_lora_for_models(
            model, clip, weights, strength_model, strength_clip
        )
        return {"ui": self._ui(name, note),
                "result": (patched_model, patched_clip, name, triggers)}

    def _ui(self, name, note=""):
        gallery, family, label = loras.split(name) if name not in ("", "None") else ("", "", "")
        return {
            "ns_lora_note": [note],
            "ns_lora": [name if name != "None" else ""],
            "ns_lora_gallery": [gallery],
            "ns_lora_family": [family],
            "ns_lora_label": [label],
            "ns_lora_triggers": [loras.triggers_for(name) if name not in ("", "None") else ""],
        }


class NeonsModelExplorer:
    """A checkpoint loader with the gallery beside it.

    The same idea as the LoRA explorer, and the same engine underneath: the
    folders in ComfyUI's checkpoints directory do the filing, each top folder
    keeps its own previews, and every checkpoint can carry a note — the sampler
    it likes, the CFG, the resolution. There is nothing to roll here: a
    checkpoint is a deliberate choice, not a variation.
    """

    @classmethod
    def INPUT_TYPES(cls):
        available = models.names(refresh=True)
        return {
            "required": {
                "ckpt_name": (["None"] + available, {
                    "default": "None",
                    "tooltip": "Which model to load, from your checkpoints and diffusion_models folders. The folder it came from is its gallery, so the browser's gallery dropdown switches between the two; a folder inside that is its family. A diffusion model has no CLIP or VAE of its own — those outputs stay empty and you wire your own loaders.",
                }),
            },
            # the queued graph, read only to see whether clip or vae is wired
            "hidden": {"unique_id": "UNIQUE_ID", "prompt": "PROMPT"},
        }

    @classmethod
    def IS_CHANGED(cls, ckpt_name="None", **_kw):
        """Re-run when the note changes, not just when the model does.

        ComfyUI caches a node whose widget values are unchanged, and editing a
        note leaves the picker exactly as it was — so the `notes` output kept
        handing out the old text. Folding the note into the signature fixes
        that; choosing the same model twice still caches.
        """
        name = str(ckpt_name or "None")
        note = models.notes_for(name) if name != "None" else ""
        return hashlib.sha1(f"{name}\n{note}".encode("utf-8")).hexdigest()

    RETURN_TYPES = ("MODEL", "CLIP", "VAE", "STRING", "STRING")
    RETURN_NAMES = ("model", "clip", "vae", "model_name", "notes")
    FUNCTION = "load"
    CATEGORY = "Neons"
    DESCRIPTION = "Neons Model Explorer — load a checkpoint or diffusion model, with a preview gallery."

    @staticmethod
    def wired_outputs(prompt, unique_id):
        """Which of this node's output slots something in the graph reads."""
        used = set()
        if not isinstance(prompt, dict) or unique_id is None:
            return used
        for node in prompt.values():
            inputs = node.get("inputs") if isinstance(node, dict) else None
            if not isinstance(inputs, dict):
                continue
            for value in inputs.values():
                if (isinstance(value, (list, tuple)) and len(value) == 2
                        and str(value[0]) == str(unique_id) and isinstance(value[1], int)):
                    used.add(value[1])
        return used

    def load(self, ckpt_name="None", unique_id=None, prompt=None):
        import comfy.sd
        import folder_paths

        name = str(ckpt_name or "None")
        if name == "None":
            raise ValueError("Neons Model Explorer: choose a model.")
        note = models.notes_for(name)
        source, relative = models.source_of(name)
        path = folder_paths.get_full_path(source, relative)
        if not path:
            raise ValueError(f"Neons Model Explorer: '{relative}' is not in your {source} folder.")

        if source == "checkpoints":
            model, clip, vae = comfy.sd.load_checkpoint_guess_config(
                path, output_vae=True, output_clip=True,
                embedding_directory=folder_paths.get_folder_paths("embeddings"),
            )[:3]
            return {"ui": self._ui(name), "result": (model, clip, vae, name, note)}

        # A diffusion model is the UNET on its own: there is no CLIP or VAE in
        # the file, so those outputs stay empty and you wire your own loaders.
        # Something reading them would otherwise fail far downstream with an
        # error about None that never mentions this node, so say it here —
        # and before the model is loaded, not after.
        missing = [label for slot, label in ((1, "clip"), (2, "vae"))
                   if slot in self.wired_outputs(prompt, unique_id)]
        if missing:
            raise ValueError(
                f"Neons Model Explorer: '{relative}' is a diffusion model, which carries no "
                f"{' or '.join(label.upper() for label in missing)} of its own, but this node's "
                f"{' and '.join(missing)} output{'s are' if len(missing) > 1 else ' is'} wired. "
                "Unplug it and add a CLIP loader and a VAE loader instead."
            )
        # ComfyUI renamed this function once; accept either.
        loader = getattr(comfy.sd, "load_diffusion_model", None) or getattr(comfy.sd, "load_unet")
        model = loader(path)
        return {"ui": self._ui(name), "result": (model, None, None, name, note)}

    def _ui(self, name):
        gallery, family, label = models.split(name) if name not in ("", "None") else ("", "", "")
        return {
            "ns_model": [name if name != "None" else ""],
            "ns_model_gallery": [gallery],
            "ns_model_family": [family],
            "ns_model_label": [label],
            "ns_model_notes": [models.notes_for(name) if name not in ("", "None") else ""],
        }


class NeonsStyleRoller:
    """Rolls style language — "painterly, caustic lighting, geometric shapes" —
    from a list of thousands of terms. Works alone or ahead of any prompt."""

    CATEGORY = "Neons"
    FUNCTION = "roll"
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("text", "words")
    OUTPUT_TOOLTIPS = (
        "The rolled words joined to whatever is wired into text; with nothing wired, "
        "the rolled words on their own.",
        "Only the rolled words.",
    )
    DESCRIPTION = ("Neons Style Roller — rolls style words from a list of thousands: "
                   "looks, lighting, colour, texture, mood and more.")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "kind": (list(roller.KIND_CHOICES), {
                    "default": "all",
                    "tooltip": "What sort of picture the words should suit. Lighting, colour "
                               "and mood words suit every kind, so they stay in the mix.",
                }),
                "count": ("INT", {
                    "default": 5, "min": 1, "max": roller.MAX_COUNT,
                    "tooltip": "How many terms to roll. A term is usually one to three words.",
                }),
                "seed": ("INT", {
                    "default": 54321, "min": 0, "max": 0xFFFFFFFF,
                    "control_after_generate": True,
                    "tooltip": "Decides the roll. The same seed and settings give the same "
                               "words; 0 rolls afresh on every run.",
                }),
                "aspect": (list(roller.ASPECT_CHOICES), {
                    "default": "any (balanced)",
                    "tooltip": "Roll one part of a look only, or leave it balanced to spread "
                               "the words across all of them. big changes rolls the words "
                               "that decide what kind of picture it is; fine details rolls "
                               "the ones that adjust it.",
                }),
                "vocabulary": (roller.VOCABULARIES, {
                    "default": "everything",
                    "tooltip": "well known: terms most models have seen often. deep cuts: the "
                               "unusual ones. my words: only user/roller_words.txt.",
                }),
                "output_as": (roller.OUTPUTS, {
                    "default": "phrases",
                    "tooltip": "phrases for natural-language models; tags writes "
                               "booru_style_tags for tag-trained models.",
                }),
                "weight": ("FLOAT", {
                    "default": 1.0, "min": 0.1, "max": 2.0, "step": 0.05,
                    "tooltip": "Emphasis for the rolled words, written as (word:1.20). "
                               "1.0 writes them plain.",
                }),
                "always_include": ("STRING", {
                    "default": "", "multiline": False,
                    "tooltip": "Comma-separated words that lead every roll, on top of count.",
                }),
                "never_include": ("STRING", {
                    "default": "", "multiline": False,
                    "tooltip": "Comma-separated words to keep out. A word here removes every "
                               "term that contains it.",
                }),
                "position": (roller.POSITIONS, {
                    "default": "after text",
                    "tooltip": "Where the rolled words go when something is wired into text.",
                }),
                # added after 3.0.0, so they sit last: a workflow saved before
                # them keeps every value it had
                "theme": (list(roller.THEME_CHOICES), {
                    "default": "any",
                    "tooltip": "A flavour that cuts across everything else: dark & gothic finds "
                               "dark lighting, dark palettes, gothic looks and grim moods. Most "
                               "of the roll comes from the theme, the rest from outside it.",
                }),
                "words_per_term": (list(roller.LENGTHS), {
                    "default": "any",
                    "tooltip": "one word rolls plain words such as gothic, rainbow, splatter. "
                               "three or more rolls the longer, more specific descriptions.",
                }),
            },
            "optional": {
                "text": ("STRING", {
                    "forceInput": True,
                    "tooltip": "A prompt to add the rolled words to. Leave unwired to get "
                               "the words alone.",
                }),
            },
        }

    @classmethod
    def IS_CHANGED(cls, seed=0, **kwargs):
        if not int(seed or 0):
            return uuid.uuid4().hex
        parts = [str(seed), roller.signature()]
        parts += [f"{key}={kwargs[key]}" for key in sorted(kwargs)]
        return hashlib.sha1("\n".join(parts).encode("utf-8")).hexdigest()

    def roll(self, kind="all", count=5, seed=0, aspect="any (balanced)",
             vocabulary="everything", output_as="phrases", weight=1.0, always_include="",
             never_include="", position="after text", theme="any", words_per_term="any",
             text=None):
        out = roller.roll_detail(
            count=count, kind=kind, aspect=aspect, vocabulary=vocabulary, seed=seed,
            never_include=never_include, always_include=always_include, theme=theme,
            words_per_term=words_per_term)
        rolled, pinned, note = out["rolled"], out["pinned"], out["note"]
        words = roller.render(pinned + rolled, output_as, weight)
        return {"ui": {"ns_rolled_words": [words], "ns_roller_note": [note],
                       # the recipe as plain lists, for "save as style"
                       # the seed the words came from, even when the widget said 0
                       "ns_rolled_seed": [out["seed"]],
                       "ns_rolled_terms": [[row["term"] for row in pinned + rolled]],
                       "ns_rolled_tags": [[roller.plain_tag(row) for row in pinned + rolled]]},
                "result": (roller.join_text(text, words, position), words)}


NODE_CLASS_MAPPINGS = {
    "NeonsStyleExplorer": NeonsStyleExplorer,
    "NeonsStyleExplorerEncode": NeonsStyleExplorerEncode,
    "NeonsGalleryCapture": NeonsGalleryCapture,
    "NeonsLoraExplorer": NeonsLoraExplorer,
    "NeonsModelExplorer": NeonsModelExplorer,
    "NeonsStyleRoller": NeonsStyleRoller,
    **nodes2.NODE_CLASS_MAPPINGS,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "NeonsStyleExplorer": "Neons Style Explorer",
    "NeonsStyleExplorerEncode": "Neons Style Explorer (Encode)",
    "NeonsGalleryCapture": "Neons Gallery Capture",
    "NeonsLoraExplorer": "Neons LoRA Explorer",
    "NeonsModelExplorer": "Neons Model Explorer",
    "NeonsStyleRoller": "Neons Style Roller",
    **nodes2.NODE_DISPLAY_NAME_MAPPINGS,
}
