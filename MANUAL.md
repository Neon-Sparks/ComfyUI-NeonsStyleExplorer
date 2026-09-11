# Neons Style Explorer — manual

A style catalog for ComfyUI: 3015 entries — 1419 written here, 1596 imported you browse visually, drop
into a prompt, and build a preview library for.

> Screenshots are marked `[screenshot: …]`. Each one says what to capture.

---

## Contents

1. [The idea](#1-the-idea)
2. [Install](#2-install)
3. [Your first prompt](#3-your-first-prompt)
4. [The nodes](#4-the-nodes)
5. [The panel](#5-the-panel)
6. [Every widget](#6-every-widget)
7. [The catalog browser](#7-the-catalog-browser)
8. [Previews and the gallery](#8-previews-and-the-gallery)
9. [Filling the gallery: crawl](#9-filling-the-gallery-crawl)
10. [Catalogs](#10-catalogs)
11. [Favourites and recents](#11-favourites-and-recents)
12. [Writing and editing styles](#12-writing-and-editing-styles)
13. [Import and export](#13-import-and-export)
14. [Where your files live](#14-where-your-files-live)
15. [Troubleshooting](#15-troubleshooting)
16. [The Extra family](#16-the-extra-family)
17. [The LoRA node](#17-the-lora-node)
18. [Reference tables](#18-reference-tables)

---

## 1. The idea

A style entry here is a **style prefix** and nothing else. It describes how the
picture is rendered and closes with its medium. It never says what is in the
picture, never instructs the model, and never contradicts your prompt.

```
Anime broadcast still, flat cel colouring in hard shadow bands, simplified
on-model faces, painted matte background, mild compression softness and grain,
TV-frame colour, anime style image,
```

That clause is joined to your prompt, and the result is one sentence about
rendering followed by your subject:

```
masterpiece, best quality, Anime broadcast still, flat cel colouring in hard
shadow bands, simplified on-model faces, painted matte background, mild
compression softness and grain, TV-frame colour, anime style image, a woman on
a fire escape at night
```

**The medium closes the clause, and it is emitted once.** If you stack a style,
a format and a finish, only the leading style's medium survives — you never get
"photograph style image ... cgi style image" fighting each other in one prompt.

Every clause is hand-written. There is no LLM-generated filler in the catalog.

---

## 2. Install

**ComfyUI Manager** — search for *Neons Style Explorer*, install, restart.

**Manually:**

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/Neon-Sparks/ComfyUI-NeonsStyleExplorer
```

Restart ComfyUI and hard-refresh the browser tab (Ctrl/Cmd + Shift + R) so the
new front-end files load.

**Updating needs a full restart, not just a refresh.** The browser picks up the
new interface on a refresh, but the node's HTTP routes only register when the
ComfyUI process starts. A refresh alone gives you a new-looking panel talking to
an old server, and anything new fails. If a new control reports *restart
ComfyUI — the running server has not loaded this version*, that is exactly what
happened. No extra dependencies — it uses Pillow and numpy,
which ComfyUI already ships. Python 3.9 or newer.

**The gallery ships empty.** Preview images are yours: you generate them on your
machine, with your models. Section 9 fills a few hundred in one unattended run.

---

## 3. Your first prompt

Add **Neons Style Explorer** (right-click → Add Node → **Neons**), then:

1. Type your subject in **prompt** — `a woman on a fire escape at night`.
2. Click **Catalog** on the node's panel, click any card, click **Use**.
3. Wire **positive** and **negative** into your CLIP Text Encode nodes.

[screenshot: the node with a style selected, the panel showing a preview,
and the composed prompt readout at the bottom — the whole node in one shot]

To see the finished prompt, wire the node's **positive** output into a Preview
Text node — that shows it live and costs the node no height. The ⋯ menu also has
**Copy the composed prompt** when you just want it on the clipboard.

If you would rather not wire two text encoders, use **Neons Style Explorer
(Encode)** instead: it takes a `CLIP` input and outputs conditioning directly.

---

## 4. The nodes

Three nodes, all under the **Neons** category.

**Neons Style Explorer** — text in, text out.
Outputs: `positive`, `negative`, `debug`.

**Neons Style Explorer (Encode)** — the same, plus a `CLIP` input.
Outputs: `positive_conditioning`, `negative_conditioning`, `positive`,
`negative`, `debug`.

**Neons LoRA Explorer** — a LoRA loader with its own gallery. Model and clip in,
model and clip out, plus the LoRA's name as a string. See section 17.

**Neons Gallery Capture** — the Save button as a node, for headless or batch
workflows. Inputs: `image`, `style_name`, `mode` (`first` / `always` / `off`)
and an optional `prompt`. Outputs the image unchanged plus `saved_file`, so you
can insert it in a chain without disturbing it.

The **debug** output is worth wiring to a Preview Text node while you are
learning the node: it lists the styles chosen, the medium, the weight, whether
crawl was on, and both composed strings.

---

## 5. The panel

The panel is drawn inside the node itself.

[screenshot: close-up of the panel — preview image, name and family chip,
shot strip, and the button row]

* **Preview image** — the cover shot for the current style, or a placeholder
  when it has none. On the dice, it shows the style that was last rolled.
* **‹ › arrows** — appear over the preview on hover and step through the
  catalog one style at a time, following the same list a crawl step would (so
  they honour *only missing previews* too) and working whether crawl is on or
  off, so you can flip through previews and stop on the
  one you want. They wrap at both ends, and they are disabled while crawl is on
  They step whichever style slot is active, so they always walk the list you
  are looking at. With `roll_scope` set to *has preview* they visit only
  entries that have one — useful early on, when most styles are still empty. Clicking the image itself still opens the browser. To choose between several
  images of the *same* style, use the shot strip underneath.
* **Name** and **family chip** — the chip reads `random` when the dropdown is on
  the dice.
* **Shot strip** — one thumbnail per saved image for this style. Click one to
  make it the cover; the small **✕** on a thumbnail deletes that image.

Buttons:

| Button | Does |
| --- | --- |
| **Roll** | Roll a random style within `roll_scope`. Disabled while crawl is on. |
| **Catalog** | Open the browser (section 7). |
| **Save** | File the newest generated image under the style that produced it. |
| **Edit** | Edit the current style's text (section 12). |
| **☆** | Add or remove the current style from favourites. |
| **⋯** | Catalog switcher, browse formats/finishes, roll style 2 or 3, new custom style, clear styles, delete shots. |

**Save is prompt-aware.** It files the image under the style that actually
generated it, which is not always the style now showing in the dropdown — while
crawling, the dropdown has already moved on.

---

## 6. Every widget

### Writing the prompt

**prompt** — your subject and scene. This is the only place picture content
belongs.

**quality** — a quality prefix kept at the very front, ahead of the style:
`masterpiece, best quality, highres`. Separate from the style so you can change
style without retyping it.

**negative** — your own avoid terms. Style negatives are merged in unless you
turn that off.

### Choosing styles

**style** — the **written catalog**. Only one style slot is active at a time:
choosing here switches the other two off, so there is never any doubt about
which list the arrows step or which entry the preview shows. Set it to *None* to
switch this slot off. Each dropdown
starts with `None`, then `🎲 Random`, then the whole catalog. Only the first
style's medium closes the clause.

**extra_style** — a slot carrying **only the imported [Extra] pack**, kept out
of the main dropdowns so those stay quick to open. Composes as another style
slot.

**custom_style** — a slot listing **only your own entries**, so a
style you wrote is one dropdown away instead of buried among a thousand shipped
ones. Empty until you create one. It refreshes from the live catalog, so a style
written in the editor appears without restarting ComfyUI.

**format** — an optional picture format: a character sheet, a magazine cover, a
contact sheet, a widescreen still. 97 of them.

**finish** — an optional finish laid over the style: foil stamp, dot gain,
uncoated paper, moiré screen. 51 of them.

Formats and finishes contribute their description but drop their own medium
when a style is leading, so the prompt stays coherent.

### Shaping the output

**output_format** — `natural` (sentences), `danbooru` (booru tags), or
`natural + danbooru` (sentences plus a tag line).

**style_position** — `start` puts the style clause in front of your prompt,
`end` puts it after. Some models weight the front of the prompt heavily; this is
the switch for that.

**style_weight** — a 1.0–5.0 slider, default 1.0 (no emphasis). In natural mode it wraps the
clause as `(clause:weight)`; in booru modes it wraps every style tag as
`(tag:weight)`. 1.0 means no emphasis at all.

**include_style_negative** — merge the style's own avoid terms into the negative
output. On by default.

**tag_separator** — booru modes only: `comma+space`, `comma`, or `space`.

### The dice and the crawl

**crawl** — walk the main style dropdown one entry per queued run instead of
rolling. Section 9.

**roll_scope** — which styles the dice may land on, and which set crawl walks:
`all`, `family` (the primary style's family), `favourites`, `recent`,
`has preview`, `missing preview`.

**roll_seed** — seeds the dice, default 54321, with a control under it. It and
`roll_scope` sit at the bottom of the widget list, directly above the preview
panel. Set that control to
*randomize* so every run rolls afresh; `0` also rolls freshly each run.

### Saving previews

**crawl_source** — which dropdown crawl walks: `main` (the written catalog),
`extra` (the imported pack) or `custom` (your own styles). The walk drives that
slot and leaves the others alone.

**crawl_missing_only** — while crawling, skip styles that already have a
preview. The list is re-checked at every step, so entries drop out as their
previews are made; when everything is covered the walk keeps moving rather than
stalling. Ignored when crawl is off.

**auto_gallery** — `off`, `first` (only when the style has no preview yet), or
`every` (save every run). This is what makes an unattended crawl fill the
gallery.

---

## 7. The catalog browser

Click **Catalog** on the panel, or **Browse formats** / **Browse finishes** in
the ⋯ menu.

[screenshot: the full browser — banner, toolbar, a grid of cards with previews]

### Toolbar

* **Search** — matches name, family and booru tags. Press `/` to jump into it,
  `Escape` to close the browser.
* **Axis** — style, format or finish.
* **Family** — **★ My styles** (everything you wrote or edited, wherever you
  filed it), then the nine written families, then **Extra** (the imported pack),
  then your own under *— my families —*. Selecting that heading shows every
  style in a family you made, whichever one.
* **Filter** — All, ★ Favourites, Recently used, Has preview, Missing preview.
* **Source** — stock, v2, custom, override. Useful for finding your own edits.
* **Catalog** picker, **+ New catalog**, **⋯** — section 10.
* **Roll** — pick a random card from what is currently filtered.
* **Restore deleted** — bring back styles you hid, individually or all at once.
* **New style** — write your own (section 12).
* **Import / export** — section 13.
* **Delete previews** — the images for the selected family, or for everything
  when the family filter is on *All families*.

### Preview size

At the left of the same bar, **Preview size** scales the grid's thumbnails from
25% to 300% of their normal width. The choice is remembered between sessions.

Below 60% the cards drop their text and become a pure thumbnail wall — useful
for judging a whole family's coverage at a glance, with the style name on hover.
At 200% and above you get a few large previews per row for actually reading the
rendering.

### The prompt bar

Directly under the toolbar, **Prompt used for generating catalog** records the
prompt these previews were made with — the thing you will want to know in three
months when you wonder why one catalog looks different from another.

[screenshot: the prompt bar with one or two saved prompts, one selected]

* **Add prompt** opens an inline field in the bar — type it and press Enter, or
  click Save prompt. Escape cancels. Whitespace is tidied, duplicates ignored,
  up to 12 per catalog. A short "saved" appears next to the buttons, and any
  failure says so rather than doing nothing.
* Click a saved prompt to select it; **Delete prompt** removes the selected one.
* Prompts belong to the catalog, so each one carries its own.

The browser **remembers how you left it** — axis, family, filter, source,
search text, preview size and scroll position — so returning to it puts you back
where you were rather than at the top of everything.

The grid **updates itself while you watch**: previews saved by a running crawl
appear in place, the coverage count climbs, and your scroll position is kept. No
need to close and reopen the browser.

The footer shows preview coverage and your favourites count, so you can watch
`312 of 1284 have previews` climb as a crawl runs.

### Cards

[screenshot: one card hovered, showing the star, the ✕ and the Use button]

* Click anywhere on the card to select the style and close the browser.
* **Use** does the same thing explicitly.
* **Edit** opens the editor.
* **★** (top-left of the image) toggles favourite.
* **✕** (top-right) deletes that style's preview, with a confirmation.
* Hovering a card shows its full clause along the bottom of the window, and the
  tooltip carries everything else: family, axis, closing medium, the clause, its
  avoid terms, both tag lists, how many previews it has, whether it is a
  favourite, where it came from, and any old names it still answers to.

---

## 8. Previews and the gallery

A preview is an image you generated, stored against a style so the catalog shows
you what that style looks like **on your model**. Up to 8 images per style; one
of them is the cover.

Three ways to save one:

1. **Save** on the panel — files the newest generated image.
2. **auto_gallery** — `first` or `every`, saves without you touching anything.
3. **Neons Gallery Capture** — a node, for workflows you run headlessly.

Images are stored as 512 px JPEGs, so a full catalog of previews is tens of
megabytes, not gigabytes.

Managing them:

* Click a thumbnail in the shot strip to promote it to cover.
* **✕** on a thumbnail deletes that one image.
* **✕** on a catalog card deletes all previews for that style.
* ⋯ → **Delete all shots for this style**, same thing from the node.
* Toolbar → **Delete previews** for a whole family, or the whole catalog.

---

## 9. Filling the gallery: crawl

This is the workflow the crawl switch exists for: generate a preview for every
style in the catalog, unattended.

**Set up:**

1. Build a simple workflow — Neons Style Explorer → CLIP Text Encode → KSampler
   → VAE Decode → Save Image. Keep the prompt generic and identical for every
   style, so the previews are comparable: `a woman standing in a city street`
   works well. A fixed sampler seed makes the comparison cleaner still.
2. On the node, set:
   * **crawl** → on
   * **crawl_source** → which list to walk (`main`, `extra` or `custom`)
   * **crawl_missing_only** → on (skips anything already covered, re-checked at
     every step)
   * **auto_gallery** → `every`
3. Park the **style** dropdown on the entry you want to start from. Crawl begins
   there, not at the top of the list.
4. Set the batch count to how many styles you want to cover and queue.

[screenshot: the node configured for a crawl run — crawl on, roll_scope on
missing preview, auto_gallery on every]

**What happens:** the style dropdown advances one entry per queued prompt, so a
batch of 200 covers 200 different styles. Each finished image is filed under the
style that produced it. The browser footer counts up as it goes.

**Details worth knowing:**

* While crawl is on, every dice is inert — the extra style slots, the format and
  the finish dice all resolve to nothing, and the Roll button is disabled.
* The walk follows `roll_scope`. `missing preview` is the one you want for
  filling gaps, because it skips everything already covered; `family` covers one
  family at a time.
* If the chosen scope turns out to be empty — `has preview` on an empty gallery,
  or `missing preview` once everything is covered — crawl walks the **whole
  catalog** rather than standing still. A stalled walk would give every queued
  prompt the same style and file the entire batch under one entry, which is
  worse than the wrong scope.
* Stepping happens when a prompt is **queued**, not when it finishes — the same
  moment ComfyUI advances a seed. Cancelling a queued run therefore leaves the
  dropdown moved on, exactly as a seed would be. To resume, set the dropdown
  back to the last style that actually generated.
* The walk wraps at the end rather than stopping.
* ⋯ → **restart crawl from the top** if you want to begin again.

---

## 10. Catalogs

A catalog is a named set of previews — one per model, or per project. "my Krea
2" holds what Krea 2 renders; another holds SDXL.

[screenshot: the catalog picker open, showing two or three named catalogs with
their preview counts]

Each catalog owns its **preview gallery**, its **favourites** and its
**recently used** list. Everything else is shared: the 1284 style texts, your
edits, your custom entries. A style prefix reads the same whichever model
rendered it, so it would be tedious to rewrite one per catalog.

* **+ New catalog** in the browser toolbar, or ⋯ → **New catalog…** on the node.
  Name it whatever you like.
* Switch with the **Catalog** dropdown, or from the node's ⋯ menu — the active
  one is marked.
* The picker shows how many styles have a preview in each, so you can see at a
  glance which model is under-covered.
* Each catalog records the prompt(s) its previews were generated with — see the
  prompt bar in section 7.
* **⋯ → Rename** to rename, **Delete** to remove. Deleting leaves the image
  files on disk by default, so a mis-click is recoverable; a second menu item
  deletes the images too.

Your original catalog is called **Default** and its files stay exactly where
they always were. Switching catalogs never copies or moves anything.

---

## 11. Favourites and recents

**Favourites** — click ★ on a card or on the panel. Filter the browser by
★ Favourites, and set `roll_scope` to `favourites` so the dice stays inside your
shortlist.

**Recently used** — every run records the style it used, including dice rolls,
keeping the last 24. Filter by Recently used, or roll within `roll_scope:
recent` to explore around what you have been working with.

Both are per catalog. Clear either from Import / export.

---

## 12. Writing and editing styles

**Edit** on the panel or a card opens the editor.

[screenshot: the editor open on an existing style]

Fields: name, family, axis, closing medium, the style clause, avoid terms, and
booru tags.

**The name is editable.** Rename anything, shipped or imported or your own —
useful for the Extra family, whose names are derived from their first
descriptor. The entry keeps its identity: its previews stay attached, and the
old name lives on as an alias so saved workflows still resolve. A name already
in use is refused.

**Tags are free text.** The autocomplete list is a suggestion, not a limit —
type any tag you like, comma separated, and it is saved exactly as typed. The
dialog keeps its keystrokes to itself, so ComfyUI's canvas shortcuts cannot
swallow what you type.
Parentheses are escaped for you when the prompt is built.

**Families are open too.** Pick one of the nine, or choose *+ add a new family…*
and name your own. A new family is a real family everywhere: it appears in the
browser's family filter, in `roll_scope: family`, and it sorts after the shipped
ones. Custom entries get a bracket tag derived from the family name, so
"Liquid Metal" produces `[Liquid][Custom] Your Style`.

A style created from the node's ⋯ menu is **selected on that node as soon as it
saves**, so the next queue renders it — no trip through the catalog to find it.
The same happens if you rename a custom style while the node is on it, and if
you create one from the browser while it was opened from a node.

Two rules keep the catalog consistent:

* **Describe only the rendering.** No subject, no composition, no instructions.
* **End with a comma, not a full stop.** The clause is a prompt fragment that
  hands over to whatever you typed, so it closes `…anime style image,` — a full
  stop reads as the end of a thought and weakens what follows. When the style
  sits last in the prompt the handover comma is trimmed, since there is nothing
  to hand over to.
* **Close with the medium**, and use the family's convention — everything in the
  anime family ends `anime style image`, photography ends `photograph style
  image`, and so on.

The opening word matches the craft, and the linter enforces the pairing against
each entry's medium:

| the work | the word |
| --- | --- |
| oil, watercolour, ink, acrylic | painting |
| pencil, pen, crayon, charcoal, chalk, technical | drawing |
| camera, film, instant | capture |
| etching, lithograph, screenprint, woodcut | print |
| anime, manga, webtoon | art (animation for sakuga and impact frames) |
| comic, graphic novel | comic / comic art |
| cartoon, cel, stop motion | animation |
| poster, flyer | poster |
| collage, photomontage, zine | collage |
| textile, ceramic, wax, carving | work |
| CGI, 3D, game art, pixel art, vector, generative | **rendering** |

**Rendering** is kept for work a computer makes — CGI, 3D, game engines, pixel
art, vector graphics and generative systems. Nothing painted, drawn,
photographed, printed or made by hand uses it.

The written clauses open by naming the process and then carry on in commas —
`Plein-air rendering, fast wet-into-wet strokes, ... oil painting style image.`
There is no colon after the opening phrase; the whole clause is one comma list,
which is how prompt parsers read it and how the imported entries already read.
The linter rejects a colon followed by a space.

A clause also never names the **frame's shape or size** — no ratios, no
*widescreen*, no *tall framing*, no *square frame*. Your workflow's latent or
image node decides the canvas, and a style that argues with it only makes the
result worse. The format entries name the artefact and describe the rendering:
*Composed as a phone wallpaper, subject placed off the middle so the centre
stays calm…* — you set the shape, the style handles the look. The linter
rejects ratio and framing language, narrowly enough that a proportion
(*two-head-tall bodies*) or a texture (*vertical scanlines*) still passes.

Changing a custom style's family rebuilds its bracket tag — move one to
"Figurine" and `[Material][Custom] Tiny Thing` becomes `[Figurine][Custom] Tiny
Thing`. The old name is kept as an alias, so saved workflows and existing
gallery images still find it.

**Import / export → Manage my families…** lists every family with its counts.
Yours can be renamed (all their styles are re-tagged) or deleted. Deleting never
deletes styles: they move to **Lonely**, the holding family for styles with
nowhere else to be. The nine shipped families are listed but locked.

Editing a shipped style writes a **local override**; the shipped file is never
touched, and **Revert** restores the original. **New style** writes to your own
custom file. Deleting a style hides it rather than destroying it — **Restore
deleted** in the toolbar brings any of them back.

---

## 13. Import and export

**Import / export** in the toolbar:

* **Export this catalog (previews + names)…** — packs the active catalog into a
  zip. Chrome and Edge ask where to save it; other browsers put it in the
  download folder. Progress is reported on the node's status line as it packs,
  and the finished size and filename when it lands. Packs the: every preview image, the style each belongs to, the prompts recorded
  against the catalog, and any custom or edited styles the previews depend on.
  Hand that file to someone else and they get your gallery.
* **Import a shared catalog…** — unpacks someone's bundle into a **new**
  catalog and switches to it. Nothing you already have is touched: your own
  catalogs, previews and styles stay exactly as they were.

* **Export custom styles + overrides** — a JSON file of your own work, for
  backup or for sharing (styles only, no images).
* **Import a style pack…** — merge someone else's pack in.
* **Clear recently-used list**, **Clear all favourites**.
* **Delete gallery images for the current style**.

Exports contain your styles only, never the shipped catalog, so a pack stays
small and readable.

---

## 14. Where your files live

Everything of yours is under the node's folder:

```
ComfyUI-NeonsStyleExplorer/
├─ previews/                 Default catalog's images + manifest.json
├─ user/
│  ├─ custom.json            your own styles
│  ├─ overrides.json         your edits to shipped styles
│  ├─ hidden.json            styles you deleted (restorable)
│  ├─ favourites.json        Default catalog's favourites
│  ├─ recents.json           Default catalog's recents
│  ├─ catalogs.json          the catalog list + which is active
│  └─ catalogs/<name>/       each named catalog: previews, favourites, recents
└─ styles/, data/            the shipped catalog — never written to
```

Back up `user/` and `previews/` and you have backed up everything that is yours.
Neither is touched by an update.

---

## 15. Troubleshooting

**Revert does nothing after editing a style.** Fixed in 2.2.0 — an override is
keyed by the style's shipped name, and after a rename the browser only knew the
new one, so Revert matched nothing and said nothing. It now finds the override
under either name, and reports a failure instead of closing silently.

**A switch or dropdown comes back wrong after a refresh.** Workflows saved
before 2.1.6 store widget values by position, so a version that added a widget
shifts everything after it. From 2.1.6 the node also saves them by name, which
is immune to that — set the widget once more and save the workflow, and it will
survive every refresh after that.

**A new control does nothing, or says the server has not loaded this version.**
Restart ComfyUI itself. Refreshing the browser updates the interface but not the
server's routes, so new features fail until the process restarts.

**The node's panel is blank or the layout looks wrong.**
Hard-refresh the browser (Ctrl/Cmd + Shift + R). The front-end files are cached
aggressively after an update.

**A preview did not save.**
The node now says why, in a line across the top of the preview image: *saved to
<style>*, or *not saved — auto_gallery is off*, *…this style already has a
preview* (that is `first` doing its job), *image not found on disk*, or
*restart ComfyUI…*. The same text goes to the browser console, so an unattended
crawl leaves a trail you can read afterwards.

**Nothing rolls.**
If `roll_scope` is `favourites` or `recent` and the list is empty, the dice falls
back to the full catalog rather than doing nothing. If it is `missing preview`
and you have covered everything, there is nothing left to roll.

**The dropdown moved on its own.**
Crawl is on. It advances one entry per queued run. Turn it off to stop.

**A style I deleted is gone.**
It is hidden, not destroyed — **Restore deleted** in the toolbar.

**The prompt has two mediums in it.**
It should not; only the leading style contributes one. If you see it, the
`debug` output shows exactly which entries contributed what — worth an issue
report.

---

## 16. The Extra family

The 1,596 entries tagged **[Extra]** come from ThetaCursed's Krea 2 style
collection, imported under its MIT licence (see `THIRD-PARTY-NOTICES.md`). They
read differently from the rest on purpose: each is a flat descriptor list rather
than a written clause, and its booru tags are those same descriptors rather than
vocabulary tags.

They behave like any other style — stack them, roll them, crawl them, give them
previews. Two practical notes:

* **Filter them out when you want only the written catalog.** Pick any other
  family, or use the source filter. Extra sits last in the family list, after
  Experimental & Material and above your own families.
* **They are not offered as a home for your own styles.** The editor's family
  list leaves imported packs out, so a style you write never joins one.
* **Their medium is generic.** An Extra style used alone closes with `style
  image`; stacked behind a written style, that style's medium closes the prompt
  as usual, so the single-medium rule still holds.

## 17. The LoRA node

**Neons LoRA Explorer** loads a LoRA and keeps a preview gallery beside it. The
list comes from ComfyUI's own `loras` folder, so whatever you have installed is
what appears.

### Folders are the grouping

```
loras/krea 2/film_grain.safetensors            gallery "krea 2"
loras/krea 2/portraits/soft_light.safetensors  gallery "krea 2", family "portraits"
loras/loose_one.safetensors                    gallery "Unsorted"
```

The top-level folder is a **gallery** and a folder inside it is a **family**.
Put your Krea 2 LoRAs in a folder called `krea 2` and that is the gallery's
name — no configuration anywhere.

**Each gallery keeps its own previews.** The same LoRA filed under two
checkpoint folders has two separate sets of images, which is the point: you can
see how it behaves on each model rather than one pile of mixed results.

### Using it

* **Gallery** opens the browser: search, filter by gallery, family, favourites
  or preview state, then click a card to load that LoRA. Its banner fades away
  as you scroll into the grid and returns at the top.
* Each card carries a **✕** at the top right to delete that LoRA's previews, and
  a **★** at the top left to favourite it — the same corners as the style
  browser.
* **Trigger words** sit under the preview. Press **Edit**, type the words that
  LoRA wants in the prompt, press Enter. They show on every card in the browser
  and come out of the node's **triggers** output, so they can go straight into
  your prompt.
* **Save** files the newest generated image against the current LoRA, in that
  LoRA's gallery. Saving is manual here — there is no crawl and no
  auto-populate.
* **★** favourites a LoRA, and the browser can filter to just those.
* Each thumbnail in the strip has a **✕** to delete that image, and clicking one
  makes it the cover. **⋯** deletes every image for the current LoRA.
* **Rescan** in the browser re-reads the folder after you add LoRAs, without
  restarting ComfyUI.
* **The browser remembers how you left it** — search text, gallery, family, the
  previews/favourites filter and your place in the grid all come back next time
  you open it, and survive a Rescan. A gallery that no longer exists on disk
  falls back to *All galleries*. Kept in your browser, per browser profile.

The preview follows the node's **width**: drag the node wider and the square
preview grows with it, up to 420px. The node holds itself at the size its
content needs — there is nothing below the buttons, so it cannot be stretched
into empty space, and it cannot creep longer on repeated drags.

Previews live in `user/loras/<gallery>/` and trigger words in
`user/loras/triggers.json`. Nothing is ever written to your loras folder.

## 18. Reference tables

### Widgets

| Widget | Values | Default |
| --- | --- | --- |
| prompt | text | empty |
| quality | text | empty |
| negative | text | empty |
| style | None, 🎲 Random, the written catalog | None |
| extra_style | None, 🎲 Random, the imported pack | None |
| custom_style | None, 🎲 Random, your own styles | None |
| format | None, 🎲 Random, 97 formats | None |
| finish | None, 🎲 Random, 51 finishes | None |
| output_format | natural, danbooru, natural + danbooru | natural |
| style_position | start, end | start |
| include_style_negative | on / off | on |
| style_weight | 1.0 – 5.0 | 1.0 |
| tag_separator | comma+space, comma, space | comma+space |
| crawl | on / off | off |
| roll_scope | all, family, favourites, recent, has preview, missing preview | all |
| roll_seed | 0 – 4294967295 | 54321 |
| auto_gallery | off, first, every | off |

### Families

| Family | Entries |
| --- | --- |
| Photography & Film | 249 |
| Traditional Painting | 208 |
| Anime & Manga | 164 |
| Design & Aesthetics | 150 |
| 3D & Games | 148 |
| Illustration | 122 |
| Comics & Print | 83 |
| Experimental & Material | 79 |
| Western Animation | 68 |
| Extra (imported) | 1596 |

3015 entries total: 2867 styles, 97 formats, 51 finishes. Of those, 1419 are written for this catalog and 1596 come from the imported Extra family. `STYLES.md` lists
every one.

### Keyboard

| Key | Does |
| --- | --- |
| `/` | Focus the browser's search box |
| `Escape` | Close the browser |
