"""Neons Style Explorer 2 — the nodes.

The style is not a dropdown. A catalog of thousands in a combo makes ComfyUI's
node list heavy and the menu unusable, so the selection is a line of text —
``Oil Impasto, Film Noir:0.6`` or a dice such as ``@favourites`` — that the
browser fills in and anyone can type or wire. Only the six small modifier
lists are dropdowns.
"""

import hashlib
import uuid

from . import explorer2 as v2


def _mod_combo(kind):
    return [v2.NONE, v2.RANDOM] + v2.modifier_names(kind)


def widgets():
    fields = {
        "prompt": ("STRING", {
            "default": "", "multiline": True,
            "tooltip": "What the picture shows. The style is added around it.",
        }),
        "prompt_prefix": ("STRING", {
            "default": "", "multiline": False,
            "tooltip": "Written at the front of the prompt, after any LoRA triggers and before "
                       "the style and your prompt: quality words, a framing phrase, anything "
                       "every image should start with.",
        }),
        "negative": ("STRING", {
            "default": "", "multiline": True,
            "tooltip": "What to keep out. Passed through to the negative outputs as you wrote "
                       "it; version 2 styles add nothing to it.",
        }),
        "styles": ("STRING", {
            "default": "", "multiline": False,
            "tooltip": "Up to three styles, comma-separated. Add :0.6 after a name to blend it "
                       "in lightly. A dice rolls one for you: @all, @favourites, @recent, "
                       "@missing, @next, @<category>, @<category>/<sub>, @<collection name>. "
                       "The Browse button fills this in.",
        }),
        "strength": (list(v2.STRENGTHS), {
            "default": "standard",
            "tooltip": "How much of the style is written: light keeps its two defining "
                       "descriptors, standard four, heavy all of them.",
        }),
        "output_as": (v2.OUTPUTS, {
            "default": "natural language",
            "tooltip": "natural language for Flux, Krea, Qwen, Z-Image and similar; tags for "
                       "SDXL, Illustrious and Pony models; or both together.",
        }),
        "style_position": (v2.POSITIONS, {
            "default": "before prompt",
            "tooltip": "Whether the style is written before your prompt or after it.",
        }),
    }
    tips = {
        "lighting": "How the picture is lit.",
        "palette": "The colour scheme.",
        "camera": "Framing, viewpoint, lens and focus.",
        "mood": "The atmosphere.",
        "format": "The kind of artefact the picture is laid out as.",
        "finish": "A surface treatment on top.",
    }
    for kind in v2.MOD_KINDS:
        fields[kind] = (_mod_combo(kind), {
            "default": v2.NONE,
            "tooltip": f"{tips[kind]} Random picks one each run, decided by roll_seed.",
        })
    fields["roll_seed"] = ("INT", {
        "default": 54321, "min": 0, "max": 0xFFFFFFFF, "control_after_generate": True,
        "tooltip": "Decides every dice and Random on this node. The same seed gives the same "
                   "result; 0 rolls afresh on every run.",
    })
    fields["auto_preview"] = (v2.AUTO_PREVIEW, {
        "default": "off",
        "tooltip": "Save the image a run makes as the style's preview in the browser: only "
                   "when it has none yet, or every time.",
    })
    return fields


# The same three inputs, under the same names, as the original node: a LoRA
# Explorer wired to one can be moved to the other without rewiring by hand.
LORA_TRIGGER_INPUTS = {
    f"lora_triggers_{n}": ("STRING", {
        "forceInput": True,
        "tooltip": "Trigger words from a Neons LoRA Explorer's 'triggers' output. They are "
                   "placed at the very start of the prompt, ahead of the style, in input "
                   "order. Duplicates are dropped.",
    })
    for n in (1, 2, 3)
}


def lora_triggers(kwargs):
    """The trigger words wired in, in order, without repeats."""
    seen, out = set(), []
    for n in (1, 2, 3):
        for term in str(kwargs.get(f"lora_triggers_{n}") or "")[:4000].split(","):
            term = v2.clean(term, 200)
            if term and term.lower() not in seen:
                seen.add(term.lower())
                out.append(term)
    return out


def _mods(kwargs, seed):
    """Resolve the six modifier dropdowns; Random is decided by the seed."""
    import random

    out, names = [], {}
    for index, kind in enumerate(v2.MOD_KINDS):
        value = kwargs.get(kind, v2.NONE)
        if value == v2.RANDOM:
            pool = v2.catalog()["mods"].get(kind) or []
            if not pool:
                continue
            rng = random.Random(f"{int(seed)}:mod:{index}") if seed else random.Random()
            entry = rng.choice(pool)
        else:
            entry = v2.modifier(kind, value)
        if entry:
            out.append(entry)
            names[kind] = entry["name"]
    return out, names


def _rolling(kwargs):
    return v2.has_dice(kwargs.get("styles")) or any(
        kwargs.get(kind) == v2.RANDOM for kind in v2.MOD_KINDS)


def run(claim=True, **kwargs):
    """Everything one run produces, as a dict."""
    seed = int(kwargs.get("roll_seed") or 0)
    picks, notes = v2.pick(kwargs.get("styles"), seed=seed, claim=claim)
    mods, mod_names = _mods(kwargs, seed)
    triggers = lora_triggers(kwargs)
    positive, style = v2.compose(
        prompt=kwargs.get("prompt", ""), picks=picks, mods=mods,
        strength=kwargs.get("strength", "standard"),
        output_as=kwargs.get("output_as", v2.OUTPUTS[0]),
        position=kwargs.get("style_position", v2.POSITIONS[0]),
        triggers=triggers, prefix=kwargs.get("prompt_prefix", ""))
    # the negative is yours alone: version 2 styles carry none of their own
    negative = str(kwargs.get("negative") or "").strip()
    out = {"positive": positive, "negative": negative, "style": style, "picks": picks,
           "mod_names": mod_names, "notes": notes, "triggers": triggers,
           "names": ", ".join(entry["name"] for entry, _w in picks)}
    out["debug"] = build_debug(kwargs, out)
    return out


def build_debug(kwargs, out):
    """What the node did and why, for a Preview Text node."""
    styles = ", ".join(
        entry["name"] + (f" x{weight:g}" if abs(weight - 1.0) > 0.001 else "")
        for entry, weight in out["picks"]) or "none"
    mods = ", ".join(f"{kind}: {name}" for kind, name in out["mod_names"].items()) or "none"
    lines = [
        "Neons Style Explorer 2",
        f"styles box:    {v2.clean(kwargs.get('styles'), 300) or '(empty)'}",
        f"styles used:   {styles}",
        f"strength:      {kwargs.get('strength', 'standard')}",
        f"output as:     {kwargs.get('output_as', v2.OUTPUTS[0])}",
        f"style goes:    {kwargs.get('style_position', v2.POSITIONS[0])}",
        f"modifiers:     {mods}",
        f"lora triggers: {', '.join(out['triggers']) or 'none'}",
        f"prompt prefix: {v2.clean(kwargs.get('prompt_prefix'), 300) or 'none'}",
        f"roll seed:     {int(kwargs.get('roll_seed') or 0)}",
    ]
    if out["notes"]:
        lines.append(f"notes:         {'; '.join(out['notes'])}")
    lines += ["", "style text:", out["style"] or "(none)", "", "positive:", out["positive"],
              "", "negative:", out["negative"] or "(empty)"]
    return "\n".join(lines)


def encode(clip, text):
    tokens = clip.tokenize(text or "")
    if hasattr(clip, "encode_from_tokens_scheduled"):
        return clip.encode_from_tokens_scheduled(tokens)
    cond, pooled = clip.encode_from_tokens(tokens, return_pooled=True)
    return [[cond, {"pooled_output": pooled}]]


class _Base2:
    CATEGORY = "Neons"

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        seed = int(kwargs.get("roll_seed") or 0)
        if _rolling(kwargs) and not seed:
            return uuid.uuid4().hex
        if any(token == "@next" for token, _w in v2.parse(kwargs.get("styles"))):
            # @next moves on by itself once the previous style has its preview
            return uuid.uuid4().hex
        # Fold in what the node would write now: a style that was edited, a
        # favourite that was starred or a preview that was saved changes the
        # result without moving a widget.
        out = run(claim=False, **kwargs)
        parts = [out["positive"], out["negative"], out["style"], kwargs.get("auto_preview", "off")]
        return hashlib.sha1("\n".join(parts).encode("utf-8")).hexdigest()

    def _ui(self, kwargs, out):
        if out["picks"]:
            v2.push_recent(out["picks"][0][0]["id"])
        return {
            "ns2_style_ids": [[entry["id"] for entry, _w in out["picks"]]],
            "ns2_style_names": [out["names"]],
            "ns2_mods": [out["mod_names"]],
            "ns2_notes": ["; ".join(out["notes"])],
            "ns2_auto": [kwargs.get("auto_preview", "off")],
            "ns2_positive": [out["positive"]],
        }


class NeonsStyleExplorer2(_Base2):
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": widgets(), "optional": dict(LORA_TRIGGER_INPUTS)}

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("positive", "negative", "style_text", "style_name", "debug")
    OUTPUT_TOOLTIPS = (
        "Your prompt with the prefix, LoRA triggers and style written around it.",
        "Your negative prompt, passed through unchanged.",
        "The style on its own, without your prompt.",
        "The style or styles this run used, dice rolls included.",
        "What the node did and why. Wire it to a Preview Text node.",
    )
    FUNCTION = "apply"
    DESCRIPTION = ("Neons Style Explorer 2 — thousands of categorised styles for "
                   "natural-language and tag models, with blending, strength and modifiers.")

    def apply(self, **kwargs):
        out = run(**kwargs)
        return {"ui": self._ui(kwargs, out),
                "result": (out["positive"], out["negative"], out["style"], out["names"],
                           out["debug"])}


class NeonsStyleExplorer2Encode(_Base2):
    @classmethod
    def INPUT_TYPES(cls):
        required = {"clip": ("CLIP",)}
        required.update(widgets())
        return {"required": required, "optional": dict(LORA_TRIGGER_INPUTS)}

    RETURN_TYPES = ("CONDITIONING", "CONDITIONING", "STRING", "STRING", "STRING", "STRING",
                    "STRING")
    RETURN_NAMES = ("positive_conditioning", "negative_conditioning", "positive", "negative",
                    "style_text", "style_name", "debug")
    OUTPUT_TOOLTIPS = (
        "The positive prompt, encoded.",
        "The negative prompt, encoded. An empty negative is encoded as empty, which is what "
        "a sampler's negative input wants when you use none.",
        "Your prompt with the prefix, LoRA triggers and style written around it.",
        "Your negative prompt, passed through unchanged.",
        "The style on its own, without your prompt.",
        "The style or styles this run used, dice rolls included.",
        "What the node did and why. Wire it to a Preview Text node.",
    )
    FUNCTION = "apply"
    DESCRIPTION = "Neons Style Explorer 2 with CLIP encode."

    def apply(self, clip, **kwargs):
        out = run(**kwargs)
        return {"ui": self._ui(kwargs, out),
                "result": (encode(clip, out["positive"]), encode(clip, out["negative"]),
                           out["positive"], out["negative"], out["style"], out["names"],
                           out["debug"])}


NODE_CLASS_MAPPINGS = {
    "NeonsStyleExplorer2": NeonsStyleExplorer2,
    "NeonsStyleExplorer2Encode": NeonsStyleExplorer2Encode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "NeonsStyleExplorer2": "Neons Style Explorer 2",
    "NeonsStyleExplorer2Encode": "Neons Style Explorer 2 (Encode)",
}
