# Changelog

## 2.0.1 — green CI

* **The test workflow failed on a clean runner.** Two preview tests write a real
  JPEG, so they import Pillow — which ComfyUI ships and the node therefore does
  not declare, leaving the GitHub runner without it. CI now installs Pillow and
  numpy before the build, and those two tests skip cleanly rather than error
  when Pillow is absent, so a bare checkout still passes. Nothing in the node
  changed.

## 2.0.0 — the LoRA node

The second node arrives properly, and the style browser gains a filter for your
own work. Everything from 1.19.1 onwards is collected here.

**Neons LoRA Explorer**

* Loads a LoRA and keeps a **preview gallery** beside it, grouped by your own
  folders: a top-level folder is a gallery, a folder inside it a family, loose
  files land in Unsorted. Each gallery keeps its own images, so the same LoRA
  under two checkpoint folders has two separate sets.
* **Trigger words** per LoRA, edited under the preview, shown on every card in
  the browser, and available as the node's fourth output — `model`, `clip`,
  `lora_name`, `triggers` — so the words travel with the LoRA into your prompt.
  Stored in `user/loras/triggers.json`.
* **The browser remembers how you left it.** Search text, gallery, family, the
  previews/favourites filter and your place in the grid are restored when you
  reopen it, and survive a Rescan rebuilding the dropdowns; a gallery that has
  since left the disk falls back to all galleries. Checked by
  `tools/harness/lora_view.mjs`.
* **Browser**: search, filter by gallery, family, favourites or preview state,
  ✕ on a card to delete its previews, ★ to favourite, Rescan to re-read the
  folder without restarting. A banner at the top fades out as you scroll into
  the grid.
* **The panel sizes itself.** It had borrowed the style node's markup, whose
  heights are set in pixels by that node's layout code — which this node does
  not run, so the preview collapsed to nothing. It now reports its height
  through both `computeSize` and `computeLayoutSize`, sizes the square preview
  from the node's width, and holds the node at its content size on every draw
  pass so it can be neither stretched into empty space nor crept longer.
* Saving is manual: no crawl, no auto-populate. Nothing is ever written to your
  loras folder.

**Style catalog**

* **★ My styles** in the family filter — everything you wrote or edited,
  wherever you filed it, in one place.

**Docs and checks**

* Manual sections renumbered and the LoRA node documented in both the README and
  the manual (section 17).
* New harnesses: `tools/harness/lora_resize.mjs`, `lora_clamp.mjs`,
  `lora_hold.mjs` — layout maths checked without a browser.
* 57 tests, 49 routes, 0 lint errors.

## 1.21.4 — the clamp now actually holds

* **The node could still be dragged longer.** Two reasons, both mine. The clamp
  lived in `onResize`, which the current ComfyUI frontend does not always route
  a corner drag through; and the panel reported its height through
  `computeSize`, which that frontend ignores for DOM widgets in favour of
  `computeLayoutSize`. The panel now reports its height both ways, and the size
  is held on **every draw pass** rather than only at resize — a stretch snaps
  back on the next frame.
* Saved workflows carrying a size from an earlier version are re-fitted on load.
* `tools/harness/lora_hold.mjs` stretches a node behind the clamp's back and
  checks the draw pass pulls it in and then leaves it alone.

## 1.21.3 — the LoRA node holds its size

* **It could still be dragged into dead space.** 1.21.2 stopped the node
  growing on its own but left a manual drag free to stretch it, which only
  added emptiness below the buttons — the panel is a square preview and three
  rows, so there is nothing for extra height to show. Both dimensions are now
  clamped while you drag: the width to the range the preview can use (300 to
  466), the height to exactly what that width needs.
* `tools/harness/lora_clamp.mjs` checks the clamp against oversized, undersized
  and repeated drags, including that re-applying the node's own size changes
  nothing.

## 1.21.2 — the LoRA node stops growing

* **Resizing made the node longer every time.** The panel took its height from
  the node's height, but litegraph sizes a node from its widgets — so each
  layout pass handed the slack back and the node crept about six pixels longer
  on every drag. The panel is now sized from the node's **width**: the square
  preview grows as you widen the node, up to 420px, and the height follows once
  and settles. `tools/harness/lora_resize.mjs` runs twelve layout passes of both
  the old and the new maths, showing the creep and its absence.
* **The buttons no longer sit below the frame.** The node's height now includes
  the margin under the button row.

## 1.21.1 — card corners the right way round

* The LoRA cards now carry **✕ at the top right and ★ at the top left**, the
  same arrangement as the style browser, so the two galleries read alike.

## 1.21.0 — LoRA gallery polish

* **Delete a preview from inside the gallery.** Every card has a ✕ and a ★ in
  its top corners, with a confirmation that says how many images will go.
* **A banner at the top of the LoRA gallery**, which fades out as you scroll
  into the grid and returns when you scroll back — the list matters more than
  the picture once you are reading it.
* **The node's preview resizes with the node.** A DOM widget is told its height
  in advance, so dragging the corner now feeds the new figure back: the panel
  fills from where it sits down to the node's bottom edge and the square preview
  grows with it.

## 1.20.0 — trigger words, a working LoRA preview, My styles

* **The LoRA node had no preview.** Its panel borrowed the style node's markup,
  whose heights are set in pixels by that node's layout code — which the LoRA
  node does not run, so the preview collapsed to nothing. The LoRA panel now
  sizes itself.
* **Trigger words per LoRA.** Edit them under the preview, see them on every
  card in the browser and in each card's tooltip, and take them out of the
  node's new **triggers** output straight into a prompt. Stored in
  `user/loras/triggers.json`; whitespace is tidied and an empty value clears
  them.
* **★ My styles** in the style browser's family filter: everything you wrote or
  edited, wherever you filed it, in one place.

## 1.19.1 — two bugs

* **A new style could inherit a renamed one's images.** Gallery images are filed
  under an entry's id, and an id is derived from the name when the entry is
  created and then kept for life — which is right, because a rename must not
  orphan the previews. But renaming frees the name, and the next style given
  that name generated the same id, so the two entries shared a gallery. New ids
  are now checked against every id in use and suffixed when they collide.
  Existing entries keep their ids, so nothing already saved moves.
* **The LoRA browser stacked every card in one place.** Its grid reused the
  style browser's, which positions cards absolutely because it virtualises a
  list of thousands. The LoRA browser draws every card, so it now uses a flowing
  grid of its own.
* **Saving a LoRA preview now repaints an open browser**, and the confirmation
  says which gallery it went to and how many images that LoRA has.

## 1.19.0 — the LoRA node

* **New node: Neons LoRA Explorer.** Model and clip in, model and clip out,
  plus the LoRA's name as a string — a LoRA loader with a gallery attached.
* **Your folders are the grouping.** The list comes from ComfyUI's `loras`
  folder: the top-level folder is a gallery and a folder inside it is a family,
  so `loras/krea 2/portraits/soft.safetensors` is the *portraits* family of the
  *krea 2* gallery. Loose files sit in *Unsorted*. Windows separators are
  handled.
* **A gallery per model folder.** The same LoRA filed under two checkpoints
  keeps two separate sets of previews, so you can see how it behaves on each.
* **Browser** with search and filters for gallery, family, favourites and
  preview state; click a card to load that LoRA.
* **Save** files the newest generated image against the current LoRA, in its own
  gallery. Manual only — no crawl, no auto-populate, as asked.
* **Favourite** a LoRA, promote any thumbnail to cover, delete a single image or
  every image for a LoRA, and rescan the folder without restarting ComfyUI.
* Previews live under `user/loras/<gallery>/`; nothing is written to your loras
  folder. The save route has the same containment check as the style node's, so
  a crafted path cannot read outside ComfyUI's output folder.

## 1.18.1 — the export actually saves, and says so

* **Export did nothing visible and could fail silently.** It was a plain
  download link, which bypasses the helper that knows the server's base path
  and reports nothing when the request 404s — the browser just says the file
  was not available. The bundle is now fetched properly, so a failure is
  reported on the node's status line, including *restart ComfyUI* when the
  server has not loaded the route yet.
* **Choose where it goes.** Chrome and Edge open a save dialog; other browsers
  fall back to the download folder as before. Cancelling the dialog is reported
  as cancelled rather than looking like a failure.
* **Progress while it packs**, then the filename and size when it finishes.

## 1.18.0 — share a whole catalog

* **Export this catalog (previews + names)…** in the Import/export menu packs
  the active catalog into a zip: every preview image, the style each one
  belongs to, the prompts recorded against the catalog, and any custom or
  edited styles those previews depend on, so they resolve on the other
  machine.
* **Import a shared catalog…** unpacks a bundle into a **new** catalog and
  switches to it. Nothing already on your machine is touched.
* Reading someone else's archive is the risky direction, so nothing in one is
  used as a path: entries must sit directly under `previews/`, every name is
  reduced to a slug with an image suffix, the resolved destination is checked
  against the catalog's own folder, and an archive is refused if it holds more
  than 20,000 files, expands past 512 MB, or expands more than 200 times its
  stored size. Two tests cover the round trip and a hostile archive.

## 1.17.4 — the node stops resizing when the first preview arrives

* **The shot strip now reserves its row from the start.** It took no space
  until a style had a saved image, so the moment the first preview landed the
  panel grew by a row and pushed the button bar out of the node until something
  forced a resize. The row is there whether or not it holds thumbnails, so the
  panel's height is the same before and after a save.

## 1.17.3 — the write routes only answer their own page

* Every POST route now refuses a request whose `Origin` header names a
  different host. ComfyUI listens on localhost and every other page in the same
  browser can reach it, so before this a page you had open could have called
  these routes — deleting previews, renaming styles, wiping a catalog. A
  browser always attaches `Origin` to a cross-site POST, so that is the signal
  used; requests with no `Origin` (the extension itself, curl, a script) are
  unaffected, and the read-only GET routes are untouched since a cross-site
  page cannot read their replies.
* Verified in `tools/route_probe.py`: a POST claiming `evil.example` is refused
  with 403, the same POST from the interface succeeds, and one with no Origin
  succeeds.

## 1.17.2 — pre-release audit

Full pass over the code before publishing; findings and method are in
`AUDIT.md`.

* **Fixed an arbitrary file read.** The two save routes joined a folder and a
  filename from the browser onto ComfyUI's output directory without checking
  the result stayed inside it, so a crafted request could have read any
  readable file on the machine and stored it as a preview. Both routes now
  resolve the path and refuse anything outside that folder.
* **Fixed markup injection through a catalog name.** The catalog picker built
  its options as an HTML string with the name interpolated raw; it now builds
  them through the DOM API.
* **Fixed a path built from a hand-editable id.** Catalog ids become directory
  names and are read back from an editable file, so they are slugged again
  wherever they are turned into a path.
* **Removed dead code**: `loadFavourites`, `pushRecent` and `queueCompose`.
* Added `tools/audit_web.mjs` (unused exports, unescaped user data in markup)
  and shipped the probes as `tools/route_probe.py` and `tools/crawl_probe.py`.
* Clean: no bare excepts, no mutable default arguments, no `eval`/`exec`/
  subprocesses, no network calls, no duplicate routes, 0 lint errors over 3015
  entries, 50 tests passing.

## 1.17.1 — the roll controls go back above the panel

* `roll_scope`, `roll_seed` and its control sit directly above the preview panel
  again, at the bottom of the widget list. Litegraph places a DOM widget by the
  height it is told in advance, and anything drawn after one inherits every
  error in that figure — three separate attempts to measure it correctly all
  left the controls hanging below the node. Keeping them above the panel avoids
  the problem rather than fighting it.
* Removed the widget reordering and the trailing-height measurement that existed
  only to support it.

## 1.17.0 — the prompt readout is gone

* **Removed the composed-prompt box from the panel.** Wire the node's
  `positive` output into a Preview Text node instead: it shows the same thing,
  updates the same way, and costs the node no height. The one thing worth
  keeping moved to the ⋯ menu as **Copy the composed prompt**, which composes on
  demand and reports how many characters it copied.
* **This is what kept the roll controls hanging below the node.** The readout
  was a variable-height block inside a DOM widget, and litegraph has to be told
  how tall that widget is before it can place anything after it. With it gone
  the panel is a preview, a shot strip and a button row: its minimum drops from
  316px to 220px, and the controls beneath it have room.
* **No more composing on every keystroke.** The readout was the only thing that
  needed it, so what used to be a server round trip per typed character now
  happens only when the composed text is actually wanted.

## 1.16.2 — crawling the imported pack stays in the imported pack

* **A crawl with `crawl_source: extra` reverted to the main catalog after the
  first step.** Two faults behind it. `advanceCrawl` fired the request for the
  style list and stepped immediately without waiting, so an early step ran
  before the list arrived; and the fallback used while waiting was chosen by
  whichever slot was active rather than by `crawl_source`, so it handed back
  main-catalog names. Those names were then written into `extra_style`, which
  cannot hold them, and the slot blanked — looking like the crawl had jumped
  back to main.
  * The step now waits for the right list before moving.
  * The fallback follows `crawl_source`, not the active slot.
  * Every hop routes by the entry itself, so a name can only ever land in the
    slot that carries its source.
* **The roll controls still hung below the node.** The height now measures the
  true bottom of the widgets drawn after the panel — using litegraph's own
  positions once it has drawn, and an estimate before that — rather than
  assuming the panel is last.
* The slot harness covers the crawl case: four steps over the imported source
  with the list not preloaded, all staying in `extra_style`.

## 1.16.1 — three fixes to 1.16.0

* **Picking a style from the browser could make the preview vanish.** Each
  dropdown now carries one source, but the browser still put every choice into
  the main slot — so an `[Extra]` entry landed in a list that does not contain
  it, showed until the next refresh, and was then reset to *None*. A pick now
  goes to the slot that carries its source, which is also why the preview
  seemed to disappear when stepping with the arrows afterwards.
* **The roll controls hung out of the bottom of the node.** They sit below the
  panel now, and the node's measured height stopped at the panel. Their height
  is included.
* **Saved values could load misaligned** — a `style_weight` of 0.00 against a
  minimum of 1. Two causes, both fixed: one of the historical layouts I listed
  never existed (it mixed `custom_style` into a release that predates it), so
  the matcher could pick it; the layouts now come from this repository's own
  history. And whatever the match decides, every value is checked against its
  widget before it is applied — a combo must hold one of its options, a number
  must be inside its range — and anything impossible falls back to the default
  with a note in the console.
* The arrows honour `roll_scope`: with *has preview* selected they step only
  entries that have one, instead of walking through hundreds of empty styles.
* Added `tools/harness/slot_routing.mjs`, which checks a pick lands in the right
  slot, survives an option-list sync, and switches the other slots off.

## 1.16.0 — one style slot at a time

* **Only one style dropdown is active.** Choosing an entry in any of the three
  switches the others to *None*, and *None* is how you switch a slot off. The
  preview window, the Save button, auto-gallery and the composed prompt all
  follow whichever slot is in use — the whole catalog still shows in the
  browser regardless.
* **The arrows know which list to walk.** They step the active slot, or the slot
  `crawl_source` names while a crawl is running. Previously they always assumed
  the main one.
* **`style_2` and `style_3` are gone**, along with `style_mix` which only
  existed to join them.
* **`roll_scope`, `roll_seed` and its control moved to the bottom** of the node,
  below the prompt readout.
* **Defaults changed**: `style_weight` is 1.0 (no emphasis) and `roll_seed` is
  54321.
* **Saved workflows are remapped by name, not position.** This release removes
  two widgets and moves three, so position-based loading would have shifted
  every value after them. Past layouts are listed by name, and because two of
  them hold the same number of values as the current one, each candidate is
  scored on how many of its combo widgets receive a value that is actually one
  of their options — the right layout scores 11-12 against 2-4 for a wrong one.
  A workflow that used `style_2` while the main slot was empty keeps that style.
  An unrecognised layout says so in the console rather than loading crooked.
* Added `tools/harness/layout_migration.mjs`, which exercises the scorer against
  value arrays shaped like real saves.
* **The test suite no longer reads or writes a real installation's data.** Any
  `user/*.json` present is moved aside for the run and restored afterwards, and
  files the run creates are removed. One test's leftovers had been deciding
  another test's result, which showed up as an intermittent failure.

## 1.15.0 — split dropdowns, and populate runs stop getting slower

* **The manifest is no longer refetched after every saved preview.** This is the
  real cost of a long populate run: each save re-downloaded the record of every
  preview already made — 24 KB at a hundred, 243 KB at a thousand, 739 KB at
  three thousand — and redrew on it, so the run got heavier the further it went.
  A save now returns its own updated record and the browser splices that in. The
  full manifest is fetched only when a response cannot say what changed.
* **One source per dropdown.** The main `style`, `style_2` and `style_3` slots
  carry the written catalog (1,273 options instead of 2,869); the imported pack
  has its own **extra_style** slot; your own entries keep **custom_style**.
* **New `crawl_source`** — `main`, `extra` or `custom` — chooses which of those
  lists a crawl walks, and the walk drives that slot, leaving the others alone.
  The preview arrows follow the same list.
* The panel falls through to the dedicated slots when the main one is empty, so
  a crawl over the imported pack still drives the preview, Save and auto-gallery.
* **Workflows saved before any of these slots existed still load.** The
  migration is generalised: a file short by N values gets the N newest slots
  spliced back in at their own positions before litegraph applies them by index.
* New test asserts the three sources are disjoint, cover the whole axis between
  them, and that a crawl over one never wanders into another.

## 1.14.2 — startup and redraw

* **1.6 MB is no longer parsed on every page load.** `web/style_index.js` is a
  bundled catalog snapshot, imported eagerly so the dropdowns had something
  before the server answered. It is now loaded only if `/neons_style/catalog`
  cannot be reached — an old backend behind a refreshed front end, or a restart
  in progress — and says so in the console when it happens. A node created
  before the catalog arrives keeps the option list its definition supplied
  rather than being emptied.
* **New previews patch the grid instead of rebuilding it.** A gallery change
  used to drop every mounted card and remake it; now only the cards whose
  preview actually changed are repainted. The full rebuild is kept for the one
  case that needs it — filtering by *has preview* or *missing preview*, where a
  style that just gained one has to leave the grid.
* Restored the footer's preview-coverage readout, which a later edit had
  reverted to the old hand-written count, and it now updates as previews arrive.

## 1.14.1 — the interface stops carrying the whole catalog around

Two measured fixes for the lag that arrived with the Extra import.

* **The catalog payload is an index again, not the whole text.** Every catalog
  load moved 1.94 MB, of which 1.79 MB was `by_name` — all 3015 entries with
  their full clauses — and eighteen code paths reload it (opening the browser or
  the editor, saving a style, switching catalogs, renaming a family, adopting a
  new style). The payload now carries what filtering and labelling need and is
  **1.34 MB**; the clause and avoid terms come from a new
  `GET /neons_style/entry` one entry at a time, cached client-side and
  invalidated on edit. The three places that read the long text — the editor,
  the footer clause on hover, the card tooltip — fetch it when they need it.
* **An unchanged gallery no longer rebuilds the grid.** The ten-second poll
  fetched the manifest and fired the redraw event regardless, so an idle open
  browser rebuilt its cards six times a minute. There is now a cheap
  `GET /neons_style/gallery/signature` (a stat of the manifest, not a walk of
  it); the poll compares it and does nothing when it matches, and `loadGallery`
  only announces a change when the manifest really differs.
* Two new tests: the payload stays under 1.6 MB and keeps the clause out of the
  index while the full text stays one lookup away, and the signature is stable
  while idle but moves when the manifest changes.

## 1.14.0 — rename anything, richer hovers, a browser that remembers

* **Styles can be renamed**, not just re-tagged. The Name field in the editor is
  editable for every entry — shipped, imported or your own — which matters for
  the Extra family, whose names are only as good as their first descriptor.
  * The entry keeps its **id**, so its gallery images stay attached.
  * The **old name becomes an alias**, so saved workflows and existing previews
    still resolve to it.
  * A name already in use is **refused**, checked against the effective catalog
    rather than the shipped files — a name can be claimed by another entry's
    rename, which a shipped-only check missed.
* **Informative tooltips.** A card's hover now lists family, axis, closing
  medium, the clause, avoid terms, both tag lists, preview count, favourite
  state, provenance, aliases, and what the buttons do. Every toolbar control and
  panel button has a tooltip explaining what it actually does.
* **The browser remembers your view**: axis, family, filter, source, search
  text, preview size and scroll position, restored next time you open it.

## 1.13.2 — Extra sits where it belongs

* **Extra was grouped under *— my families —***, because the browser treats
  anything outside the shipped family list as user-made and Extra had not been
  added to that list. It now sits last among the shipped families, directly
  after Experimental & Material and above the divider, and sorts there
  everywhere else too.
* **The editor no longer offers imported families** when you write a style —
  your own entries should not join someone else's pack. They remain fully
  available in the browser's family filter.

## 1.13.1 — the browser fills in while you watch

* **Previews saved during a crawl now appear in the open catalog.** The browser
  read the gallery once when it opened and never heard about later saves, so
  images only showed up after closing and reopening it. Every gallery refresh
  now announces itself and the open grid redraws — coalesced, so a burst of
  saves is one redraw, and the scroll position is preserved.
* A save made outside this page — the capture node, a second browser tab —
  produces no event here, so the open browser also polls once every ten seconds,
  and not at all while the tab is in the background.

## 1.13.0 — the Extra family

* **1,596 imported styles under `[Extra]`**, from ThetaCursed's Krea 2 style
  collection, used under its MIT licence. The catalog goes from 1419 to **3015
  entries** (2867 styles).
* **`tools/import_pack.py`** does the conversion, and can be re-run against any
  future export: it derives a name for each record (the text after `Style:` when
  there is one, otherwise the leading descriptor), capitalises the clause and
  closes it with a medium so stacking still emits exactly one, turns the
  descriptors into tags for the booru output modes, and records the pack's
  provenance on every entry.
* **The linter now distinguishes imported families from written ones.** Imported
  entries are checked for structure — name, axis, closing medium, duplicates,
  length — but not against the house writing rules or the booru vocabulary,
  which exist for clauses written here. The summary reports the two groups
  separately, so "hand-written" keeps meaning what it says: 1419 of 1419.
* `THIRD-PARTY-NOTICES.md` carries the upstream MIT notice. The upstream
  repository was offline at import time, so its exact copyright line and URL
  should be copied in when it is back.

## 1.12.0 — two techniques the catalog was missing

* **[Photo] Intentional Camera Movement** — the camera swept through a slow
  exposure, forms drawn into streaks. Distinct from the existing motion blur,
  long exposure and zoom-burst entries, which all keep the camera still.
* **[Experimental] Pixel Sorting** — rows reordered by brightness into ribbon
  bands. Distinct from Glitch Art and Glitch Datamosh, which corrupt rather than
  sort.

Both came out of a coverage check against a public collection of Krea prompt
strings: of 5,849 distinct descriptors in it, these two were the only techniques
with nothing equivalent in the catalog. Nothing was imported — that collection
is someone else's work and holds keyword strings rather than style clauses;
these two entries are written here like every other.

## 1.11.2 — typing in dialogs is nobody else's business

* **Keystrokes were escaping the style editor.** A dialog opened over the node
  sits inside ComfyUI's canvas, which binds its own shortcuts, so letters typed
  into a field could be taken as canvas commands instead — worst in the tag
  boxes, where it looked like the field would not accept free text. Both dialogs
  now stop key events at their own edge (without touching default behaviour, so
  typing types), and Escape closes the dialog rather than the browser behind it.
* **The browser's `/` shortcut no longer steals focus while you are typing.** It
  fired from any field, so a slash in a tag or a clause jumped the cursor to the
  search box.
* The web checker now recognises every parameter of a declared function, not
  just the first — it was reporting a real function as undefined.
* Added `tools/preflight.sh`, the publish check: nothing private tracked, no
  build junk, the catalog matching its source packs, lint, web check and tests
  passing, and the release metadata filled in.
* Tests now delete the user files they create instead of writing empty ones
  back, so a checkout stays spotless after a test run.

## 1.11.1 — a new style lands on the node

* Creating a style from the node's **⋯ → New custom style** now selects it on
  that node the moment it saves, ready to render a preview. Renaming a custom
  style the node is currently on follows the rename, and creating one from the
  browser hands it back when the browser was opened from a node.
* The style dropdowns are rebuilt as part of that: their option lists come from
  the catalog loaded when the node was created, so without a refresh the new
  name would have been rejected as an unknown value.

## 1.11.0 — families you can actually manage

* **See all your own families at once.** The browser's family filter now groups
  shipped families first, then yours under a *— my families —* heading, and
  selecting that heading shows every style in any family you made.
* **Editing a family re-tags the style.** Moving a custom style to another
  family left its old bracket tag in the name — `[Material][Custom]` on a style
  now in Figurine. The name is rebuilt on save, and the old one is kept as an
  alias so saved workflows and existing gallery images still resolve.
* **Manage my families…** in the Import/export menu: every family with its
  counts, rename and delete for the ones you added, and the shipped nine listed
  but locked — renaming those would orphan a thousand entries.
* **Deleting a family never deletes styles.** They move to **Lonely**, a holding
  family for styles with nowhere else to be, and are re-tagged to match.
* Removed a duplicate `GET /neons_style/families` route: two handlers were
  registered on the same path and the older one silently shadowed the new one.
  The route probe now reports duplicate method+path pairs so that cannot recur.

## 1.10.0 — your own tags, your own families, your own slot

* **Booru tags are free text.** The editor was refusing to save any tag outside
  the 247-tag suggestion list, which made it impossible to write the tag you
  actually wanted — while the backend had always accepted anything. The list is
  now a suggestion: type what you like, it is stored verbatim, escaped properly
  in booru output, and unlisted tags are noted in the console rather than
  blocked.
* **New family from the editor.** The Family dropdown gains *+ add a new
  family…* with a name field. A custom family works everywhere the shipped nine
  do: the browser's family filter, `roll_scope: family`, the family ordering
  (yours sort after the shipped ones), and the bracket tag on custom names.
* **New `custom_style` slot**, directly below `style_3`, listing only your own
  entries. It composes as a fourth style, and its contents come from the live
  catalog rather than the node definition, so a style written in the editor
  shows up without restarting ComfyUI.
  * **Workflows saved before this version still load correctly.** Litegraph
    applies widget values by index, so inserting a slot mid-list would have
    shifted every widget after it by one. The extension detects a workflow with
    one value too few and splices the new slot's default in at the right place
    before the values are applied, logging when it does.
* New test covers the whole path: a custom family, tags outside the vocabulary,
  the slot composing beside a catalog style, and the escaping in booru output.

## 1.9.1 — preview size control

* **Preview size** dropdown at the left of the prompt bar: 25%, 50%, 75%, 100%,
  125%, 150%, 200%, 250%, 300%. The grid re-columns to suit and the choice is
  remembered between sessions.
* Below 60% the cards drop their text block and the grid becomes a pure
  thumbnail wall, with the style name on hover — at those sizes the label was
  taller than the picture.
* Cards still fill the row, but no longer stretch far past the size asked for;
  on a wide window 300% was landing nearer 400%.

## 1.9.0 — 133 new hand-written styles

The catalog goes from 1284 to **1417 entries**, every new clause written by hand
in the house voice and linted clean. Gaps were chosen by dumping the existing
1136 style names per family and running every candidate through a similarity
check against names, aliases and clause text, so nothing here duplicates or
near-duplicates what was already there.

* **Abstract & generative (20)** — the widest gap in the catalog, which had
  about ten abstract entries for a field the size of painting. Plotter pen work,
  cellular automata, reaction-diffusion, flow fields, Voronoi, Truchet tiling,
  noise contours, strange attractors, harmonographs, plus concrete art, nested
  square studies, neo-concrete folds, tachisme, white relief, monochrome fields,
  hard-edge shaped panels, rule-system wall drawings, decalcomania, frottage and
  décollage.
* **World painting traditions (22)** — sfumato, orphism, Bay Area figurative,
  quadratura, sinopia, pronkstilleven, bodegón, capriccio, Dutch marine, and the
  traditions the catalog had no representation for at all: Cuzco school,
  Ethiopian church painting, Kerala mural, Pahari miniature, amate bark,
  rosemaling, Ndebele wall geometry, Fraktur, gyotaku, sgraffito, verre
  églomisé, Khokhloma and Delftware.
* **Photographic processes and optics (25)** — ambrotype, salted paper, dye
  transfer, Cibachrome, lumen, solargraph, photogram, chronophotography,
  slit-scan, swing-lens panorama, zoom-burst, star trails, microfiche,
  copy-stand, strip camera, cloud chamber, high-speed strobe, trail camera,
  endoscope, cinewhoop, plus two-strip Technicolor, kinescope, rear projection,
  day-for-night and hand-cranked silent film.
* **Print processes (11)** — end-grain wood engraving, chiaroscuro woodcut,
  pochoir, collagraph, monotype, katazome, ink-wash comic tone, duotone pulp,
  rotogravure, blue-line pencil pages and patent drawing.
* **Animation techniques (13)** — xerographic cel line, scratch-on-film,
  paint-on-glass, pinscreen, squigglevision, multiplane depth, cutout engraving
  collage, motion comic, and for anime: Kanada-school effects, smear-frame
  sakuga, missile-swarm trails, copy-book toner and OVA airbrush.
* **Design & aesthetics (12)** — cassette futurism, neumorphism, Swiss punk, new
  wave typography, Googie, metabolism, CD-ROM clipart, MS Paint bitmap, bento
  grid, grandmillennial chintz, glitchcore and angelcore.
* **3D & games (10)** — Gaussian splat artifacts, PSX horror lo-fi, Mode 7,
  billboard sprites, machinima capture, avatar platform shots, blocky sandbox,
  Source-era shooter, metaballs and displacement terrain.
* **Illustration & material (20)** — alchemical emblems, marginalia grotesques,
  blackwork tattoo, van murals, pinstriping, Chicano fine-line, ferrofluid,
  pyrography, papier-mâché, scrimshaw, coffee wash, pavement chalk, kirigami,
  string art, rangoli, anthotype, rust transfer, cymatic plates, culture plates
  and hydro-dipping.

Fifteen candidates were dropped rather than written: eight already exist on the
**format** axis (fruit crate label, matchbox label, seed packet, wanted poster,
playbill, tarot card, storyboard panel, tattoo flash), and the rest were too
close to existing entries to justify a second version.

## 1.8.0 — the crawl stops skipping entries, and can target the gaps

* **A crawl skipped many catalog entries.** The walk kept its position in a
  counter that lived apart from the style dropdown, so anything refreshing the
  list of styles — a scope change, or the background resync added in 1.7.3 —
  re-seeded that counter mid-batch and the walk jumped. **The position is now
  the dropdown itself**: every step is derived from the style currently
  selected, so nothing can drift. A full lap from any starting entry visits
  every style exactly once, verified over a 12-entry walk including a resync
  landing mid-walk.
* **New switch: `crawl_missing_only`.** Walk only the styles that have no
  preview yet. The list is re-checked at each step, so entries drop out as their
  previews are made, and when everything is covered the walk keeps moving
  instead of stalling. `roll_scope` still narrows the set (a family, favourites,
  and so on) and this filters it further.
* **The preview arrows work during a crawl again.** 1.7.1 disabled them on the
  grounds that crawl owned the dropdown; now that the dropdown *is* the
  position, arrowing by hand simply moves where the next step starts. They
  follow the same list, so with missing-only on they skip covered styles too.
* Added `tools/harness/crawl_walk.mjs`, the regression test for all three of
  those behaviours.
* The catalog tests no longer assume which catalog was left active by whatever
  ran before them — one of them failed intermittently for exactly that reason.

## 1.7.4 — auto-gallery says what it did

* **Auto-saving failed silently.** If the server declined to file an image, the
  browser dropped the result on the floor: no message, no console line, nothing
  — and during an unattended crawl you discover it hours later. Every outcome is
  now reported in a line across the top of the node's preview, and repeated to
  the console: *saved to <style>*, or the reason it was not — auto_gallery off,
  `first` skipping a style that already has a preview, no style recorded for the
  prompt, the image missing from disk, or a server that needs restarting.
* The save route returns a `skipped` list with a reason per node alongside
  `saved`, and its error strings now name the actual problem (including the full
  path when an image is not where the client said it was).

## 1.7.3 — a crawl can no longer stall on one style

* **Only the first image of a crawl reached the catalog.** If crawl could not
  build its list of styles to walk, `advanceCrawl` returned early and the style
  dropdown never moved — so every queued prompt composed the same style, and the
  whole batch piled onto that one entry (or was skipped outright under
  `auto_gallery: first`). Two things produce an empty list: a `roll_scope` that
  genuinely has nothing in it (`has preview` on an empty gallery, `missing
  preview` once everything is covered) and a crawl request that does not answer.
* Crawl now falls back to walking the **whole catalog** whenever its list comes
  back empty, from both `syncCrawl` and `advanceCrawl`, logging why. Standing
  still is the one behaviour it must never have.
* Added two dev harnesses, neither shipped: `tools/harness/crawl_steps.mjs`
  imports `web/panel.js` against stub ComfyUI modules and asserts the dropdown
  advances per queued prompt (it reproduces this bug with `EMPTY=1`), and
  `tools/crawl_probe.py` drives a real aiohttp app through a four-style crawl,
  checking each image is filed under its own style and that a repeated report
  neither double-files nor steals another prompt's record.

## 1.7.2 — failures say what to do about them

* Every request now records its HTTP status on failure, and the UI turns it into
  a sentence worth reading: a 404 or 405 reports **restart ComfyUI — the running
  server has not loaded this version**, which is the real cause when a browser
  refresh has picked up the new interface but the server is still running the
  old routes. Other cases report the status and point at the ComfyUI console.
* README and manual now say plainly that installing or updating needs a full
  ComfyUI restart, not just a browser refresh.

## 1.7.1 — fixes both of 1.7.0's new bits

* **Add prompt did nothing.** It was built on `window.prompt`, and a browser
  silently suppresses dialogs once a page has opened a few of them — the call
  returns null and the click looks dead. The bar now has an inline field: click
  **Add prompt**, type, press Enter (Escape cancels). It also reports "saved" or
  "could not save" instead of failing quietly, and Delete prompt does the same.
  The server side was fine throughout — verified end to end over real HTTP,
  including a legacy index file and a named catalog.
* **The preview arrows never appeared.** They were gated on a style having two
  or more saved images, and a crawl saves exactly one per style, so the
  condition was almost never true. They now step through the **catalog** one
  style at a time — which is what makes them useful for flipping through
  previews and stopping on one — are always visible, wrap at both ends, and grey
  out while crawl is on since crawl is driving the dropdown. Choosing between
  several images of the same style stays with the shot strip underneath.
* Added `route_probe.py` (dev only, not shipped): stands up a real aiohttp app
  with the node's routes and a stub PromptServer, so an HTTP-level bug can be
  reproduced without running ComfyUI.

## 1.7.0 — catalogs record the prompt they were generated with

* **Prompt bar in the browser**, directly under the search and filter row:
  *Prompt used for generating catalog*, the saved prompts, **Add prompt** and
  **Delete prompt**. Click a prompt to select it, then delete removes that one.
  Whitespace is tidied, duplicates are ignored, up to 12 per catalog and 800
  characters each.
* Prompts are stored **per catalog** alongside its name, so "my Krea 2" and an
  SDXL catalog each say how they were made. Saved in `user/catalogs.json`.
* New route: `POST /neons_style/catalogs/prompt` (add, or `delete: true`).
* The web checker gained a documented limitation and a workaround: its string
  stripping is not a lexer, so a literal quote inside a regex character class
  desynchronises it — write those as `\u0022` / `\u0027`. It found the problem
  by flagging two functions that plainly did exist.

## 1.6.2 — page through previews from the node

* **Arrows on the panel preview.** A style with more than one saved image now
  shows ‹ › arrows over the preview (on hover) and a `2 / 5` counter. They page
  through that style's images and the one you land on becomes the cover, so
  choosing takes one click and no confirmation. The arrows stay hidden when
  there is only one image, and clicking the image itself still opens the
  browser.

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
