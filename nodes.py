"""Neons Style Explorer — nodes."""

from . import compose as composer
from . import loras
from . import runs
from .catalog import (RANDOM_TOKEN, SOURCES, crawl_names, custom_names, entries,
                      imported_style_names, names_for, push_recent, resolve, roll,
                      source_pool, written_names)

WEB_DIRECTORY = "./web"

ROLL_SCOPES = ["all", "family", "favourites", "recent", "has preview", "missing preview"]


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
            "tooltip": "Which styles the dice may land on, and which set crawl walks: everything, the primary style's family, your favourites, recently used, or by preview state.",
        }),
        "roll_seed": ("INT", {
            "default": 54321, "min": 0, "max": 0xFFFFFFFF,
            "control_after_generate": True,
            "tooltip": "Seeds the dice. Use the control under it (randomize / increment) so every run rolls a different style; 0 also rolls freshly each run.",
        }),
    }


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
    if source != "all" and not source_pool(source):
        return f"on — {source} is empty, rolled from the whole catalog instead"
    return f"on — {source}"


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


def run(**kwargs):
    from .gallery import manifest

    pool = entries()
    previews = manifest()
    seed = int(kwargs.get("roll_seed") or 0)
    scope = kwargs.get("roll_scope", "all")
    crawl = bool(kwargs.get("crawl", False))
    # 'family' scope needs a family to work from: take it from whichever slot
    # holds a concrete style, since slot 1 may be the dice itself
    family_hint = None
    for field in ("style", "custom_style", "extra_style"):
        entry = resolve(kwargs.get(field, "None"), pool)
        if entry:
            family_hint = entry["family"]
            break

    # an older workflow may still hold the dice token in a slot; that is what
    # the switch means now
    slots = [kwargs.get("style", "None"), kwargs.get("custom_style", "None"),
             kwargs.get("extra_style", "None")]
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

    positive, negative = composer.compose(
        prompt=kwargs.get("prompt", ""),
        quality=kwargs.get("quality", ""),
        negative=kwargs.get("negative", ""),
        styles=styles,
        fmt=fmt,
        finish=finish,
        output_format=kwargs.get("output_format", "natural"),
        style_position=kwargs.get("style_position", "start"),
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
        return {"required": widgets(), "hidden": {"unique_id": "UNIQUE_ID"}}

    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("positive", "negative", "debug")
    FUNCTION = "apply"
    DESCRIPTION = "Neons Style Explorer — style prefixes in natural language or booru tags."

    def apply(self, unique_id=None, **kwargs):
        positive, negative, debug, styles = run(**kwargs)
        self._record(unique_id, kwargs, styles)
        return {"ui": self._ui(kwargs, styles), "result": (positive, negative, debug)}


class NeonsStyleExplorerEncode(_Base):
    @classmethod
    def INPUT_TYPES(cls):
        required = {"clip": ("CLIP",)}
        required.update(widgets())
        return {"required": required, "hidden": {"unique_id": "UNIQUE_ID"}}

    RETURN_TYPES = ("CONDITIONING", "CONDITIONING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("positive_conditioning", "negative_conditioning", "positive", "negative", "debug")
    FUNCTION = "apply"
    DESCRIPTION = "Neons Style Explorer with CLIP encode."

    def apply(self, clip, unique_id=None, **kwargs):
        positive, negative, debug, styles = run(**kwargs)
        self._record(unique_id, kwargs, styles)
        return {
            "ui": self._ui(kwargs, styles),
            "result": (encode(clip, positive), encode(clip, negative), positive, negative, debug),
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
            },
            "hidden": {"unique_id": "UNIQUE_ID"},
        }

    RETURN_TYPES = ("MODEL", "CLIP", "STRING", "STRING")
    RETURN_NAMES = ("model", "clip", "lora_name", "triggers")
    FUNCTION = "apply"
    CATEGORY = "Neons"
    DESCRIPTION = "Neons LoRA Explorer — load a LoRA, with a preview gallery per model folder."

    def apply(self, model, clip, lora="None", strength_model=1.0, strength_clip=1.0, unique_id=None):
        name = str(lora or "None")
        triggers = loras.triggers_for(name) if name != "None" else ""
        if name in ("", "None") or (not strength_model and not strength_clip):
            return {"ui": self._ui(name),
                    "result": (model, clip, "" if name == "None" else name, triggers)}

        import comfy.sd
        import comfy.utils
        import folder_paths

        path = folder_paths.get_full_path("loras", name)
        if not path:
            return {"ui": self._ui(name), "result": (model, clip, name, triggers)}
        weights = comfy.utils.load_torch_file(path, safe_load=True)
        patched_model, patched_clip = comfy.sd.load_lora_for_models(
            model, clip, weights, strength_model, strength_clip
        )
        return {"ui": self._ui(name), "result": (patched_model, patched_clip, name, triggers)}

    def _ui(self, name):
        gallery, family, label = loras.split(name) if name not in ("", "None") else ("", "", "")
        return {
            "ns_lora": [name if name != "None" else ""],
            "ns_lora_gallery": [gallery],
            "ns_lora_family": [family],
            "ns_lora_label": [label],
            "ns_lora_triggers": [loras.triggers_for(name) if name not in ("", "None") else ""],
        }


NODE_CLASS_MAPPINGS = {
    "NeonsStyleExplorer": NeonsStyleExplorer,
    "NeonsStyleExplorerEncode": NeonsStyleExplorerEncode,
    "NeonsGalleryCapture": NeonsGalleryCapture,
    "NeonsLoraExplorer": NeonsLoraExplorer,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "NeonsStyleExplorer": "Neons Style Explorer",
    "NeonsStyleExplorerEncode": "Neons Style Explorer (Encode)",
    "NeonsGalleryCapture": "Neons Gallery Capture",
    "NeonsLoraExplorer": "Neons LoRA Explorer",
}
