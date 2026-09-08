# Changelog

## 1.6.1 — menus open where you clicked

* **Popup menus appeared in the top-left corner.** The helper read `clientX`
  from whatever it was handed, and a call site passing the button element rather
  than the event gave it `undefined` — the position came out `NaN` and the menu
  fell back to the corner of the screen. It now takes either an element or an
  event, and anchors to the button that opened it: the menu sits just above the
  ⋯, right edges aligned, dropping below only when there is no room above.

## 1.6.0 — named catalogs

* **Several named catalogs, one per model or project.** Name one "my Krea 2",
  another for a different model, and each keeps its own preview gallery, its own
  favourites and its own recently-used list. Switching is instant and nothing is
  copied or moved.
  * **Catalog** picker, **+ New catalog** and a rename/delete menu sit in the
    browser toolbar; the node's ⋯ menu lists the catalogs with the active one
    marked and can create one without opening the browser.
  * The picker shows how many styles have a preview in each catalog.
  * Deleting a catalog leaves its image files on disk by default, so a mis-click
    is recoverable; a second menu item deletes the images too.
* **The style texts are shared by every catalog** — your edits, your custom
  entries and the 1284 hand-written prefixes are the same everywhere, because a
  style prefix is worth the same whichever model rendered it. Only the images
  and the per-catalog shortlists are separate.
* **Existing installs are untouched.** The catalog you already have keeps its
  files exactly where they were (`previews/`, `user/favourites.json`,
  `user/recents.json`) and is listed as *Default*; new catalogs live under
  `user/catalogs/<id>/`.
* New routes: `GET /neons_style/catalogs` and
  `POST /neons_style/catalogs/{create,select,rename,delete}`.
* Two new tests cover catalog isolation (previews, favourites and recents split
  while the style texts stay shared) and unique ids for repeated names
  (43 tests).

## 1.5.2 — previews land on the right style when crawling

* Run records are capped at 512 prompts rather than 64, and the prompt text
  stored with a record is truncated at 2000 characters. Records are consumed as
  each prompt finishes, so the map normally holds one entry; the cap only
  applies when nothing is consuming them.

* **Crawl + a queue of several runs filed previews under the wrong styles.**
  Crawl advances the style dropdown as each prompt is *queued*, so by the time
  run 1 finishes the widget is already several styles ahead. The dice never had
  this problem because the panel learns the rolled name from the execution
  message itself, which is why random matched and crawl did not.
* **The pairing is now made server side and cannot drift.** Every run records
  the style it actually composed with, keyed by the prompt id ComfyUI is
  executing (`runs.py`, capped at 64 prompts, node id from `UNIQUE_ID`).
  Auto-gallery posts the finished prompt's images to
  `POST /neons_style/gallery/save_run` and the server files them under *its*
  record of that prompt. No widget is read at any point. A client that cannot
  name the prompt still gets the right answer, because the newest record is the
  run that just finished. The previous browser-side pairing stays as a fallback
  for an older backend.
* **The Save button uses the same record**, so saving by hand after a crawl run
  files the image under the style that produced it rather than the one now
  showing in the dropdown.
* Two new tests: records stay correct while the dropdown moves past them, and
  the record store evicts oldest-first (41 tests).

## 1.5.1 — crawl starts where you are

* **Crawl begins at the selected style.** Park the dropdown on the entry you
  want to populate from and switch crawl on: the walk starts there instead of at
  the top of the list. If the selected style is not in the scope — it has a
  preview and the scope is *missing preview*, say — the walk starts at the first
  entry of the scope that follows it in catalog order. The node menu's **restart
  crawl from the top** still jumps to the beginning.
* **Removed the crawl counter.** It advanced when a prompt was queued, so
  cancelling a run left the number moved on and looking wrong, and the style
  dropdown already shows where the walk is.

## 1.5.0 — crawl through

* **New `crawl` switch.** Turn it on and the node stops rolling and walks the
  main style dropdown instead, one entry per queued run, so a batch of N runs
  covers N styles in order. Point `auto_gallery` at `every` and queue a big
  batch to fill the gallery unattended.
  * The set it walks is `roll_scope`, so **missing preview** crawls exactly the
    styles that still have no image, **family** stays inside one family, and
    **favourites** walks your shortlist.
  * Stepping happens once per *queued* prompt — the same moment ComfyUI advances
    a seed with control_after_generate — which is what makes a batch cover a
    range rather than repeating one style N times.
  * While crawl is on, every dice is inert: the extra style slots and the format
    and finish dice resolve to nothing, and a dice left in the main slot falls
    back to the head of the walk, so a run is never styleless. The panel's Roll
    button is disabled and says why.
  * Turning it on mid-list resumes from whatever the dropdown is showing rather
    than jumping to the top. The node menu gains **restart crawl from the top**.
  * The panel chip reads `crawl 37/412`, and the debug output carries a
    `crawl:` line.
* `roll()` and crawl now share one scope filter (`catalog.scope_pool`), so the
  dice and the walk can never disagree about what a scope contains.
* Three new tests cover the walk order, scope narrowing, and that crawl really
  does suppress every dice (39 tests).

## 1.4.3 — correct under parallel execution

* **Previews were filed under the wrong style when more than one run executed at
  once.** Every piece of pairing state was a single global slot: the latest
  images, the node's last rolled style, and an `execution_success` handler that
  married whichever values happened to be current. With prompts in flight in
  parallel the last one to report won, so prompt B's image was saved under
  prompt C's style. Each prompt is now tracked by its own `prompt_id`: the
  `executed` event records that prompt's images and, for every Neons node, the
  style, auto-gallery mode and prompt text that node reported for that same run.
  Auto-gallery saves strictly from that record, so an image can only ever be
  filed under the style that produced it, no matter what the dropdown shows by
  the time it finishes. Interrupted and errored prompts drop their record.
* **User files are now safe against concurrent writes.** The gallery manifest,
  favourites and recents are all read-modify-write, so two runs finishing
  together could each write the state they had read and silently lose one
  update. Manifest mutations hold a lock for the whole load-mutate-save span,
  favourites and recents likewise, and every atomic write uses a per-thread
  scratch file instead of a shared `.tmp`.
* New test runs sixteen threads at favourites and recents at once and asserts
  nothing is lost (36 tests).

## 1.4.2 — fixes the 1.4.1 load error

* **`ReferenceError: stripHtml is not defined`.** The 1.4.1 edit that rewrote the
  shot strip added the call and dropped the function, so panel.js threw as soon
  as a node with previews rendered and ComfyUI aborted the workflow load. The
  function is back.
* **New build check: `tools/check_web.mjs`.** `node --check` only validates
  syntax and happily accepts a call to a function that does not exist, which is
  exactly how this shipped. The checker strips comments and string bodies, then
  reports any identifier that is called but never declared or imported, and any
  named import that its source module does not export. It is wired into
  `tools/build_all.sh` and reports the five UI modules clean.

## 1.4.1 — catalog card fixes

* **Cards with a preview could not be selected.** An `<img>` is draggable by
  default, so pressing on the thumbnail started a native image drag and the
  click never fired. Preview images are now out of hit-testing entirely
  (`pointer-events: none`, dragging disabled) and the card takes the click.
* **The star and delete-preview buttons were never wired.** They were added to
  the card in one edit and the handlers in another that matched a different
  element name, so both existed only on paper: clicking where the star should be
  just selected the style, and there was no way to unfavourite from the browser.
  Both are real buttons now, always visible (dimmed until hover), with an
  explicit **Use** button beside Edit so selecting is unambiguous.
* **The shot strip's delete cross was invisible.** It sat outside the tile and
  the strip's own `overflow-x` clipped it. It now sits inside the thumbnail.
* Import/export menu gains **Clear all favourites**.

## 1.4.0 — favourites and recents, gallery deletion fixes

### Added
* **Favourites.** Star any entry from the catalog card or the node's toolbar
  star. The browser gains a *Favourites* filter, and `roll_scope` gains
  **favourites** so the dice can stay inside your own shortlist. Stored in
  `user/favourites.json`.
* **Recently used.** Every run records the style it actually used — including
  dice rolls — into `user/recents.json` (last 24). Filter by *Recently used* in
  the browser, roll within `roll_scope: recent`, and clear the list from the
  Import/export menu.
* **Per-preview delete.** Each thumbnail in the node's shot strip now has a
  delete cross (hover to reveal), and each catalog card has a delete-preview
  button on the image, alongside a star.
* The catalog footer now reports preview coverage and favourite count
  ("312 of 1284 have previews · 8 favourites").

### Fixed
* **Restore all did nothing.** The helper called the route without a body, and a
  bodyless call is a GET while the route is POST-only — so it 405'd silently and
  reported zero. Restoring one at a time worked because those calls carried a
  body.
* **Deleting previews with All families selected.** The wipe button demanded a
  family and refused otherwise. It now reads *Delete all previews* when no
  family is chosen (with a confirm that names the count) and *Delete <family>
  previews* when one is, and the backend treats an empty family as every family.

## 1.3.0 — new banner, duplicates merged

* **New catalog banner** (the inked beach illustration), shown full width at the
  top of the browser and scrolling away under the sticky toolbar.
* **66 duplicate entries folded into 63 keepers**, with every old name kept as a
  search alias, so nothing you had selected stops resolving. Cross-family twins
  (`[3D][v2] Woodcut` into `[Print] Woodcut`, `[Design][v2] Bauhaus` into
  `[Aesthetic] Bauhaus`, `[3D][v2] Claymation` into `[Object] Claymation`),
  same-look pairs (`Low Poly` x3, `PS1` x3, cross-processing x3, Polaroid,
  wet plate, Tri-X, expired film, paparazzi, toy camera, platinum, halation,
  Kodachrome, large format, watercolour, gouache, thangka, gongbi, letterpress,
  synthwave, maximalism, tropical modernism, cel shading, screentone, chibi,
  gekiga and more) and `[Painting] Abstract Expressionism (2)` renamed to
  `[Painting] Abstract Expressionism`.
* Near neighbours were deliberately left alone — 1980s vs 1990s anime, packshot
  vs lifestyle product, Marvel vs DC house style, oblique vs nadir aerial.
* `tools/merge_duplicates.py` records the merge table and edits both the catalog
  and the written packs, so a rebuild keeps the merge. Two new tests assert the
  old names still resolve and that no duplicate base names remain.

## 1.2.0 — Tier B and C additions, restore button fixed

### Added
* **135 more hand-written entries (1350 total).**
  * **35 painting traditions and techniques**: Rinpa gold screen, Yamato-e,
    sosaku hanga, Warli, Gond, Pattachitra, Kalighat, Tingatinga, Inuit
    stonecut, Northwest Coast formline, Maori kowhaiwhai, zellige, Otomi,
    Huichol yarn, retablo, Fayum, grisaille, trompe-l'oeil, vanitas, camera
    obscura, plein air, verdaccio, silverpoint, Suprematism, Vorticism,
    Precisionism, Regionalism, Divisionism, Les Nabis, Rayonism, metaphysical,
    lyrical abstraction, hard-edge, batik painting, Mithila.
  * **40 photographic processes and vernacular capture**: bromoil, gum
    bichromate, kallitype, carbon transfer, emulsion lift, chemigram,
    solarisation, Petzval swirl, prism refraction, freelensing, thermal, night
    vision, schlieren, microscopy, satellite, Kirlian, real estate, hotel
    brochure, on-model e-commerce, flat lay, bodycam, dashcam, 480p webcam,
    video-call grid, action cam, arena wide, sodium vapour, fluorescent office,
    hospital LED, firelight, moonlight, aurora, Milky Way, storm chase, arctic
    flat light, heat haze, ring flash, hard palm shadow, bounce flash,
    available-light restaurant.
  * **30 for 3D and games**: N64 filtering, Saturn flat shading, Dreamcast,
    Amiga copper, DOS VGA, vector arcade, isometric CRPG, raymarch, fractal
    flame, LiDAR point cloud, photoscan error, kitbash greeble, destruction,
    fluid, cloth, particles, motion-graphics abstract, inflatable, gummy,
    knitted and felt shaders, fur groom, car turntable, medical viz, data viz,
    white model, section diorama, wargame miniature, terrain, papercraft toy.
  * **30 studio-signature animation and comics looks**, written as technique
    descriptions: effects-heavy anime, soft realism, kinetic action, graphic
    montage, VTuber model art, transformation sequence, eyecatch, title card,
    soft romance, chibi emote sheet, compressed broadcast rip, tankobon print;
    angular action, grotesque TV, flat folk, gross-out close-up, late-night
    lo-fi, preschool vector, pixilation, Zagreb modernist, Estonian puppet,
    bouncing-ball sing-along; krackle energy, fumetti, Bonelli, silent
    sequential, webcomic flat, sci-fi digest, Sunday broadsheet, mini-comic.

### Fixed
* **The Restore deleted button was invisible when you needed it.** It hid
  itself whenever the hidden count was zero and only counted on open, so it
  never appeared after deleting a style in the same session and could not be
  discovered at all otherwise. It is always visible now, highlights when
  something is hidden, says so when nothing is, and refreshes its count the
  moment a style is deleted from the editor.

## 1.1.0 — Tier A additions, single-medium fix, restore deleted styles

### Added
* **115 new hand-written entries (1215 total).** The four categories the gap
  scan showed were structurally thin:
  * **30 finishes** (21 → 51): bloom, chromatic aberration, lens dirt, veiling
    flare, vignette, anamorphic streak, shallow/deep focus, frozen motion, slow
    shutter, heavy grain, clean digital, crushed blacks, lifted matte, high and
    low key, moire, dot gain, uncoated paper, foil stamp, emboss, dust and
    scratches, JPEG artefacts, upscale mush, colour banding, screen door, ultra
    and minimal detail, unfinished edges, wet sheen.
  * **30 formats** (65 → 95): mood board, colour script, animatic frame, film
    strip, zine spread, wanted poster, lobby card, VHS sleeve, arcade side art,
    cassette J-card, sleeve back, playing card, banknote, stamp, matchbox, seed
    packet, crate label, museum label, ticket, boarding pass, business card,
    letterhead, menu, deck cover, store screenshot, podcast cover, email hero,
    banner set, newspaper and tabloid front pages.
  * **25 materials** (27 → 52): encaustic, suminagashi, ebru, gelli print,
    shibori, batik, tie-dye, macrame, beadwork, wire, LED matrix, e-ink,
    chalkboard, latte art, sugar glass, ice and soap carving, tape art, sticker
    bomb, crystal growth, lenticular, thermochromic, CNC toolpath, 3D-print
    layers, scanner drag.
  * **30 modern aesthetics**: barbiecore, brat green, mob wife, tomato girl,
    blokecore, cluttercore, indie sleaze, tumblr 2014, seapunk, cybergrunge,
    acid house and jungle flyers, skeuomorphic UI, Frutiger Metro, brutalist
    web, deconstructivism, parametricism, tiki, shabby chic, gorpcore,
    techwear, clowncore, decora, fairy kei, lolita, gyaru, regencycore, Soviet
    modernism, Ulm rationalism, anti-design.
* **Restore deleted styles.** Deleting a shipped style hides it; the catalog
  toolbar now has a *Restore deleted (n)* button that lists what is hidden and
  restores one or all of them. New routes `GET /neons_style/hidden` and
  `POST /neons_style/style/restore_all`; hidden names keep their original case.

### Fixed
* **Only one medium is emitted now.** Stacking a format or finish onto a style
  used to end the prompt with that entry's medium — an anime style plus a
  magazine-cover format plus a natural-skin finish closed with "photograph
  style image" twice. The leading style's medium closes the chain and the
  others are stripped; a format or finish used alone still keeps its own.

### Changed
* `tools/import_source.py` rebuilds from the current catalog plus the packs in
  `tools/written/`, and appends any pack entry that is not in the catalog yet,
  so new looks are added by dropping a record into a pack.

## 1.0.1 — the dice now links up

* **`roll_scope` has/missing preview compared unlike keys.** Entry ids use dots
  (`anime.khyleri_v2`) while the gallery slugs them (`anime_khyleri_v2`), so the
  filter saw every style as missing a preview. Both sides are normalised now.
* **The rolled style was not wired to the panel or the gallery.** With the dice
  selected, the preview box, the Save button and `auto_gallery` all looked at the
  literal dice entry, so nothing could be saved and the thumbnail never changed.
  One `effectiveStyle()` resolver now feeds the preview, Save, Edit, the ⋯ menu
  and auto-gallery from the style the last execution actually rolled.
* The panel refreshes the moment a run reports its roll, showing that style's
  thumbnail and `rolled: <name>` caption.
* The live composed prompt mirrors the last roll (marked `· last roll`) instead
  of rolling its own separate style, which is why the panel text and the debug
  output disagreed.
* `roll_scope: family` takes its family from whichever style slot holds a
  concrete style, since slot 1 may be the dice.

## 1.0.0 — first release

A ground-up rebuild. None of the code is shared with the earlier Krea2 styler;
only the style *names* and the idea tables were carried over as source material.

### The catalog
* **1100 entries, every clause hand-written**, across nine families —
  165 anime & manga, 226 photography & film, 153 traditional painting,
  125 3D & games, 123 illustration, 117 design & aesthetics,
  113 comics & print, 51 western animation, 27 experimental & material.
* Three axes: **style** (1014), **format** (65), **finish** (21).
* Every entry closes with its medium — `anime style image`,
  `photograph style image`, `cgi style image`, `print style image`, and 20 more.
* Old `[Clio]` entries are relabelled `[v2]`; the old names still resolve as
  search aliases.
* Every tag is validated against `data/tags.txt`; the linter enforces the
  wording rules and reports coverage.

### Prompting
* A style entry is a style prefix and nothing else — no scope paragraph, no
  "do not add", no statements about picture content. The linter blocks
  instruction language from creeping back in.
* `output_format`: natural | danbooru | natural + danbooru.
* `style_position`: style clause at the start or the end of the prompt.
* Separate **quality** box, always kept at the very front.
* `style_weight` slider 1.0–5.0 — `(clause:weight)` in natural mode,
  `(tag:weight)` on the primary style's tags in booru modes. Parens inside
  booru tags are escaped.
* `🎲 Random` in every style dropdown with `roll_scope`
  (all / family / has preview / missing preview) and a seeded `roll_seed`
  carrying ComfyUI's control-after-generate widget.

### The node
* Layout measured from litegraph's own `last_y` plus the panel's real
  `offsetHeight`, not from estimated widget heights — no dead strip at the
  bottom, and it self-corrects from the draw loop.
* Preview scales with the node on both axes; the prompt readout is bounded
  (96–200px) and surplus height shrinks the node instead of stretching a box.
* Panel body is click-through, so the node still drags from anywhere.
* Buttons: Roll, Catalog, Save, Edit, and a ⋯ menu.

### Gallery and catalog browser
* Gallery ships empty; **Save** stores the last generated image as the style's
  preview, up to eight shots each, click a thumbnail to set the cover,
  `auto_gallery` for automatic capture. Keyed on stable ids.
* Full-screen browser with the banner scrolling away under a sticky toolbar and
  a virtualised grid — only visible cards mount.
* Search over name, alias, family and tags; filter by axis, family, source and
  preview state; inline editor; JSON import/export of style packs.
