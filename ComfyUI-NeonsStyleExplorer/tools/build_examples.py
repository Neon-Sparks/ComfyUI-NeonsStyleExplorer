"""Regenerate the example workflows so widget order matches the node."""

import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "examples")
PKG = "neons_example_pkg"

NOTE = (
    "Neons Style Explorer\n\n"
    "prompt    - your subject\n"
    "quality   - quality prefix, always kept at the very front\n"
    "negative  - your avoid terms\n\n"
    "style / style_2 / style_3   the look (pick the dice to roll)\n"
    "format / finish             optional extra axes\n"
    "output_format               natural | danbooru | natural + danbooru\n"
    "style_position              style clause at the start or the end\n"
    "style_weight                1.0-5.0 emphasis on the style\n"
    "roll_scope / roll_seed      how the dice picks (set the control under\n"
    "                            roll_seed to randomize for a new roll each run)\n\n"
    "Panel: Roll, Catalog, Save (stores the last generated image as this\n"
    "style's preview), Edit, and a more menu. The composed prompt updates live."
)


def load_pkg():
    spec = importlib.util.spec_from_file_location(
        PKG, os.path.join(ROOT, "__init__.py"), submodule_search_locations=[ROOT]
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[PKG] = module
    spec.loader.exec_module(module)
    return importlib.import_module(f"{PKG}.nodes")


def widget_values(nodes, overrides):
    values = []
    for name, spec in nodes.widgets().items():
        if name in overrides:
            values.append(overrides[name])
            continue
        options = spec[1] if len(spec) > 1 and isinstance(spec[1], dict) else {}
        if "default" in options:
            values.append(options["default"])
        elif isinstance(spec[0], list):
            values.append(spec[0][0])
        else:
            values.append("")
        if options.get("control_after_generate"):
            values.append("randomize")
    return values


def workflow(nodes, node_type, overrides):
    cls = nodes.NODE_CLASS_MAPPINGS[node_type]
    graph = [
        {
            "id": 1, "type": node_type, "pos": [80, 100], "size": [460, 980],
            "flags": {}, "order": 0, "mode": 0,
            "inputs": [{"name": "clip", "type": "CLIP", "link": None}] if "Encode" in node_type else [],
            "outputs": [
                {"name": name, "type": rtype, "links": None}
                for name, rtype in zip(cls.RETURN_NAMES, cls.RETURN_TYPES)
            ],
            "properties": {"Node name for S&R": node_type},
            "widgets_values": widget_values(nodes, overrides),
        },
        {
            "id": 2, "type": "Note", "pos": [580, 100], "size": [430, 400],
            "flags": {}, "order": 1, "mode": 0, "properties": {},
            "widgets_values": [NOTE],
        },
    ]
    return {
        "last_node_id": 2, "last_link_id": 0, "nodes": graph, "links": [],
        "groups": [], "config": {}, "extra": {}, "version": 0.4,
    }


def main():
    nodes = load_pkg()
    os.makedirs(OUT, exist_ok=True)
    files = {
        "neons_style_explorer.json": workflow(nodes, "NeonsStyleExplorer", {
            "prompt": "a fox walking through deep snow at dusk",
            "quality": "masterpiece, best quality",
            "style": "[Anime] 1980s Theatrical OVA Cel",
        }),
        "neons_style_explorer_encode.json": workflow(nodes, "NeonsStyleExplorerEncode", {
            "prompt": "a lighthouse in a storm",
            "style": "[Cinema] 1940s Film Noir",
        }),
        "neons_style_explorer_danbooru.json": workflow(nodes, "NeonsStyleExplorer", {
            "prompt": "1girl, rooftop, city lights",
            "quality": "masterpiece, best quality",
            "style": "[Anime] 1990s TV Cel Action",
            "output_format": "danbooru",
            "style_weight": 1.2,
        }),
        "neons_style_explorer_roll.json": workflow(nodes, "NeonsStyleExplorer", {
            "prompt": "a woman on a fire escape at night",
            "style": "\U0001F3B2 Random",
            "roll_scope": "missing preview",
        }),
    }
    for name, data in files.items():
        with open(os.path.join(OUT, name), "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=1, ensure_ascii=False)
            handle.write("\n")
        print(f"wrote examples/{name}")


if __name__ == "__main__":
    main()
