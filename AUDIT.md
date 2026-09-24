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
