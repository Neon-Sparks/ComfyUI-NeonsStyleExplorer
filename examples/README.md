# Example workflows

Drop a JSON onto the ComfyUI canvas, or use **Load**.

| File | What it shows |
| --- | --- |
| `neons_style_explorer.json` | The styler node with a quality prefix and one style |
| `neons_style_explorer_encode.json` | The encode variant, ready for a CLIPLoader |
| `neons_style_explorer_danbooru.json` | Booru-tag output with the style weight at 1.2 |
| `neons_style_explorer_roll.json` | `random_roll` on with `roll_scope: missing preview` and the seed control set to randomize — a new style every run, handy for filling the gallery |

These are prompt-side templates on purpose: wire `positive` / `negative` into
whatever sampler stack you already use, or use the encode variant to get
conditioning directly.
