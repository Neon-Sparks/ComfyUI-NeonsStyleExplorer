# Pre-release audit

Run before publishing 1.17.2. Everything here is reproducible with the tools in
`tools/`; nothing was judged by eye alone.

## What was checked

| Area | How |
| --- | --- |
| Python errors | `python3 -m py_compile` on all 18 modules; AST walk for bare excepts, mutable default arguments, risky calls (`eval`, `exec`, `os.system`, `pickle`), unused imports |
| Web errors | `tools/check_web.mjs` — undefined calls, imports that name a missing export |
| Dead code | `tools/audit_web.mjs` — exports no module imports and the file never uses |
| Injection | `tools/audit_web.mjs` — catalog or user text interpolated into markup without escaping |
| Filesystem | every `os.path.join` reachable from a route, traced to its input |
| Routes | `tools/route_probe.py` — 38 routes registered, duplicate method+path pairs |
| Behaviour | 50 tests, `tools/lint.py` (0 errors over 3015 entries), `tools/crawl_probe.py` |

## Findings

### Fixed: arbitrary file read through the save routes (the significant one)

`POST /neons_style/gallery/save` and `/gallery/save_run` take a folder and a
filename from the browser and join them onto ComfyUI's output directory. Joined
naively, `{"subfolder": "../../..", "filename": "etc/passwd"}` escapes that
directory: any readable file on the machine could be stored as a "preview" and
then served back through `/neons_style/shot`.

Both routes now resolve the path and refuse anything that does not sit inside
the output folder. Verified against `../../..`, `..` and a plain filename, on
both routes.

Related, already sound: `/neons_style/shot` slugs its key and will only serve a
file that the manifest lists for that entry, so it cannot be steered elsewhere.

### Fixed: markup injection through a catalog name

The catalog picker built its `<option>` list as an HTML string with the
catalog's name interpolated raw, so a catalog named with a tag would have been
parsed as markup. It now builds options through the DOM API. Every other place
that puts user text in markup — prompts, families, styles — already escaped it.

### Fixed: a hand-edited catalog id could point at another directory

Catalog ids become directory names. They are generated as slugs, but
`user/catalogs.json` is editable and is read back on every call, so ids are now
slugged again wherever they are turned into a path, including deletion.

### Fixed: any page in the browser could call the write routes

ComfyUI listens on localhost, which every other page in the same browser can
also reach. The traversal fix stopped those routes reading arbitrary files, but
they could still be *called* — a page could quietly delete previews, rename
styles or wipe a catalog.

All 24 POST routes now refuse a request whose `Origin` header names a different
host: a browser always attaches that header to a cross-site POST, so such a
request did not come from the ComfyUI interface. Requests with no `Origin` — the
extension's own fetches, curl, a script — are unaffected. Verified: a POST from
`evil.example` is refused with 403, the same POST from the page succeeds, and
one with no Origin succeeds.

The GET routes are read-only and a cross-site page cannot read their replies, so
they are left open.

### Reviewed: the catalog bundle (added after the first audit pass)

Importing a zip means reading names that came from someone else's machine, so
nothing in an archive is trusted as a path: entries must sit directly under
`previews/`, each name is reduced to a slug with an image suffix, the resolved
destination is compared against the catalog's own folder, and the archive is
refused if it holds more than 20,000 files, expands past 512 MB, or expands
more than 200 times its stored size. Tested with an archive carrying
`previews/../../../../tmp/...` and `../../../tmp/...` entries plus an `.exe`:
nothing was written and no file appeared outside the catalog.

### Fixed: dead code

Three exports nothing used: `loadFavourites`, `pushRecent` (both superseded by
the catalog payload carrying favourites and recents) and `queueCompose` (left
over from the removed prompt readout). Removed.

### Noted, not changed

* **Errors name paths.** A failed save reports the filename it could not find.
  Useful when a workflow saves elsewhere, and the reader is a page that can
  already list the output folder.
* **`tools/` ships in the repository** — the source packs, probes and harnesses.
  Deliberate: it is what makes the catalog auditable and contributions
  possible. `.comfyignore` keeps it out of the published archive.
* **No network calls, no telemetry, no subprocesses, no `eval`.** The only
  outbound traffic is the browser talking to ComfyUI's own server.
* **User data stays local** under `user/` and `previews/`, and `.gitignore`
  keeps both out of git.

## Standing checks

`bash tools/preflight.sh` before every push: nothing private tracked, no build
junk, the catalog matching its source packs, lint, web check and tests passing,
and the release metadata filled in.

---

## Audit, 2.4.5

Ran over the whole package: every Python module, the six web modules, all
routes, and the interactions between the features added since 2.2.

### Bugs found

* **`random_roll` could file an image under the previous run's style.** The
  browser records each queued prompt's style so a saved image is paired
  correctly. With the dice on, the style does not exist yet — the node rolls it
  when it runs — and `effectiveStyle` falls back to the last style used, so the
  record named the *previous* one. The browser now stays silent for a random
  run and leaves the record to the node, which knows what it rolled. Covered by
  `tools/harness/queue_record_random.mjs`.
* (Fixed in 2.4.4) Two images saved in the same millisecond shared a filename.

### Dead code removed

* `store.py`: eight names imported and never used.
* `__init__.py`: `FAMILY_ORDER` and `delete_custom` imports.
* `gallery.py`: `read_log()`, orphaned with its route.
* Two routes nothing called — `POST /neons_style/custom/delete` (the editor
  deletes through `style/hide`) and `GET /neons_style/gallery/log`. 50 routes
  down to 48; a delete route with no caller is only attack surface.
* `web/main.js`, `web/panel.js`: option lists and combo syncing for `style_2`
  and `style_3`, widgets retired in 1.16.

### Checked and clean

* 31 POST routes, every one behind the Origin guard; none registered raw.
* No `eval`, `exec`, `subprocess`, `pickle`, bare `except`, or mutable default
  arguments anywhere in the package.
* No unused JavaScript exports; no unescaped user data interpolated into markup.
* The export filename is slugged, so a catalog named with CRLF cannot inject a
  response header.
* Interaction matrix: random + family scope, random + crawl, medium off with no
  style, medium off with a format only, medium off under weighting, and source
  separation between main and extra — all correct.

---

## Audit, 2.9.3 — the registry flag

The registry scan flagged v2.6.5 and v2.6.6 with one MEDIUM finding. Read at
https://comfy-security.nynxz.com/?node=neons-style-explorer it says:

| field | value |
| --- | --- |
| scanner | `yara_scan` |
| issue type | `python_network_operations` |
| confidence | 90% |
| location | `web/main.js:267` |
| matched | `$socket4` |
| flagged line | `const original = app.queuePrompt?.bind(app);` |
| MITRE | T1041 Exfiltration Over C2 Channel, T1048 |

**It is a false positive, and an understandable one.** A YARA rule written to
catch Python socket code — `sock.bind(...)` — matched the same method name in
JavaScript, where it means `Function.prototype.bind` and binds a function's
`this`. The line wraps ComfyUI's own `queuePrompt` so the extension can learn
the id of the prompt just queued; nothing is sent anywhere by it.

Rather than argue with a scanner, the line is gone: the wrapper now calls
through with the live `this`, which does the same job. A function named
`listen()` — another string that rule family looks for — is now
`watchExecution()`. Neither name appears in the package any more, including in
comments.

### Re-checked at the same time

* 41 POST routes, every one behind the Origin guard; none registered raw.
* 20 GET routes, all read-only.
* No handler takes a browser-supplied path without containing it. Traversal
  attempts — `../../../../etc/passwd`, `..\..\windows\win.ini`, `/etc/passwd`,
  `sub/../../secret.jpg` — all resolve to nothing in both the style and asset
  galleries.
* The new `size` parameter is allow-listed to 256 and 384; anything else,
  including a path, falls back to the original file, so a crafted URL cannot
  fill the disk with renders.
* No `eval`, `exec`, `subprocess`, `os.system`, `pickle`, `__import__`,
  `ctypes` or `base64` decoding anywhere in the shipped code.
* No HTTP client of any kind: no `requests`, `urllib.request`, `http.client`,
  `aiohttp.ClientSession`, no websockets. Nothing leaves the machine.
* Everything written stays under the package's own `user/` folder, which as of
  2.9.0 includes the default catalog's previews.

---

## Audit, 2.10.0 — a second pass, by attack rather than by reading

`python tools/security_probe.py` stands the 41 POST and 20 GET routes up on a
real aiohttp app and tries to misuse them. It works on a throwaway copy of the
package, because some of what it sends is destructive on purpose.

### Found and fixed

* **An empty request deleted every preview.** `POST /neons_style/gallery/delete_family`
  read a missing `family` as "every family". The Origin guard keeps other
  sites out, but nothing destructive should be the default: the route now
  needs `"all": true` to do that. Found when the probe's malformed-body check
  emptied its own test gallery.
* **Asset names were taken on trust.** `/neons_lora/save`, `/text`,
  `/favourite` and the `/neons_model/` equivalents filed data under whatever
  name the request gave, and passed it to ComfyUI's path lookup to fingerprint
  the file. They now refuse a name ComfyUI does not list. Clearing text and
  un-starring stay possible for a file that has since been removed.
* **A non-object JSON body raised.** `[1, 2]` or `"text"` reached `.get()` and
  came back as a 500 with a traceback. It is now treated as an empty request.
* **`data-file` attributes were built from manifest filenames unescaped**, in
  the node panel and the asset explorer. Those names are generated by the
  server and sanitised on bundle import, so this was not reachable, but a
  hand-edited manifest should not be able to break out of an attribute. The
  explorer's escaper also did not cover quotes; it does now.
* Previews are served with `X-Content-Type-Options: nosniff`.

### Checked and sound

* All 41 POST routes refuse another site's `Origin`, and an opaque `null`
  origin; the page's own is accepted.
* Neither save route can read outside ComfyUI's output folder: `..`, `../..`,
  a backslash variant, an absolute path and a traversal inside the filename
  all fail.
* The three `/shot` routes answer 404 to traversal in `key`, `gallery` or
  `file`.
* Bundle import: unchanged since the 1.17 review and still covered by
  `test_hostile_bundle_writes_nothing_outside_the_catalog`.
* Still no `eval`, `exec`, `subprocess`, `pickle` or HTTP client anywhere in
  the shipped code. LoRAs load with `safe_load=True`.

### Known and left as it is

* **The Origin check compares host names, not ports.** A page served from
  another port on the same machine — another local web app — passes it. That
  is deliberate: a development proxy in front of ComfyUI sits on a different
  port, and matching ports would lock it out. Anything already running on
  your own machine is inside the trust boundary ComfyUI itself draws.
* **A request with no `Origin` header is accepted.** Browsers always send one
  on a cross-site POST, so this only admits scripts and tools running locally.
* **If ComfyUI is started with `--listen`, anyone who can reach it can call
  these routes**, as they can call ComfyUI's own. This package adds no login
  and is not meant to face a network you do not trust.

## Audit, 2.11.0 — the Style Roller

One new node, one new route, two new files read from disk.

| Surface | What it can reach | How it is held |
| --- | --- | --- |
| `POST /neons_roller/roll` | the word list, read-only | behind the same Origin guard as every POST; writes nothing; `count` clamped to 50, `seed` to 0..2^32-1, text boxes cut at 4,000 characters, unknown dropdown values fall back to their defaults |
| `data/roller_words.txt` | shipped, never written at run time | fixed path |
| `user/roller_words.txt` | the user's own terms | fixed path, never taken from a request; over 2 MB ignored; at most 20,000 lines; control characters stripped; each term cut at 80 characters |

* A term is only ever text. It is never used as a path, a pattern or markup:
  `never_include` is escaped before it is matched, the node's display box is a
  textarea set through `.value`, and brackets in a term are escaped so they
  cannot be read as prompt emphasis.
* `tools/security_probe.py` attacks the route: a count of a billion, wrong
  types in every field, a 200,000-character pinned word, file paths in every
  field, and 5,000 pattern-shaped words in `never_include` (answered in well
  under two seconds — the words are escaped, so none of them is a pattern).
* Residuals are unchanged from 2.10.0: the Origin check compares host names
  only, and a request with no Origin is accepted.

## Audit, 3.0.0 — Style Explorer 2

Two new nodes, eleven new routes, one new user folder (`user/v2/`).

| Surface | What it can reach | How it is held |
| --- | --- | --- |
| `GET /neons_style2/catalog`, `/state` | the shipped styles; the user's favourites, collections and preview list | read-only |
| `GET /neons_style2/preview` | one preview image | the file name is a slug of a style id the catalog knows; an unknown id is a 404 before any path is built; served as `image/jpeg` with `nosniff` |
| `POST /neons_style2/preview/save` | reads one image, writes one preview | source held to ComfyUI's output, temp and input folders by the same containment check the original save routes use; the folder type is one of three fixed words; over 64 MB refused; decoded and re-encoded by Pillow, so what is stored is always a JPEG this code wrote; target is `user/v2/previews/<slug>.jpg` |
| `POST /neons_style2/compose` | nothing on disk | text in, text out; inputs cut to fixed lengths |
| `POST /neons_style2/favourite`, `/collection`, `/recents/clear` | `user/v2/state.json` | ids must resolve to a real style; collection names are keys inside one JSON file and never paths; 60 collections of 2,000 styles at most |
| `POST /neons_style2/custom/save`, `/delete` | `user/v2/custom.json` | every field cleaned to plain text and cut to length; a name cannot contain the characters the styles box gives meaning to; a shipped style cannot be shadowed or deleted |

* The browser builds every element with `textContent`; no style, collection or
  search text is ever parsed as HTML.
* The styles box is parsed, not evaluated. An unknown name is skipped and
  reported; a dice scope is matched against category ids, sub names and the
  user's collection names and falls back to the whole catalog.
* A damaged `state.json` or `custom.json` reads as empty. (Found by test: a
  non-list `favourites` value raised; fixed before release.)
* The preview carry-over from the original gallery copies files into
  `user/v2/previews` and changes nothing in the original gallery; the source
  name is reduced to a base name before it is joined to the gallery folder.
* `tools/security_probe.py` attacks these routes: path escapes in every field
  of preview/save, traversal ids on the preview GET, a 100,000-character own
  style, deleting a shipped style, collection names shaped like paths, and
  compose with wrong types throughout.
* The roller's "save as style" adds no route of its own. It posts the recipe to
  `/neons_style2/custom/save` and the image to `/neons_style2/preview/save`,
  so a saved roll goes through the same cleaning, limits (60 words of 100
  characters) and path containment as any other own style. Its "always write
  every word" flag is only honoured as a real JSON `true` on a user's own style.
