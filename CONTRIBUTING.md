# Contributing

Thanks for looking. Bug reports, catalog corrections and new styles are all
welcome — and a good bug report is worth more than most patches.

## Reporting a bug

Include the version (bottom of `pyproject.toml`), what you did, what happened,
and what you expected. Two things help more than anything else:

* **Whether you restarted ComfyUI.** A browser refresh loads the new interface
  but not the node's HTTP routes. If the catalog browser shows a red strip
  saying it is using the bundled snapshot, that is the whole bug.
* **The browser console.** Most interface problems announce themselves there,
  prefixed `Neons Style Explorer:`.

Security issues go through [SECURITY.md](SECURITY.md), not the issue tracker.

## Before you open a pull request

Run the build chain. It rebuilds the catalog from source, lints it, regenerates
the index and the docs, checks the web layer and runs the tests:

```bash
bash tools/build_all.sh
```

Then the pre-push check, which also looks for private files, an uncommitted
tree, and release metadata:

```bash
bash tools/preflight.sh     # must print: preflight: ready to push
```

Both must be clean. CI runs the same build on every push and pull request.

## Which files to edit

**The catalog is generated.** Never edit `styles/*.json` by hand — they are
built from `tools/written/*.json`, and your change will be overwritten on the
next build. Edit the source pack, then run `bash tools/build_all.sh`.

| Want to change | Edit |
| --- | --- |
| a style's clause, tags or family | `tools/written/*.json` |
| the tag vocabulary | `data/tags.txt` |
| node behaviour | `nodes.py`, `compose.py`, `catalog.py` |
| the interface | `web/*.js` |
| routes | `__init__.py` |
| the writing rules | `tools/lint.py` |

`STYLES.md`, `web/style_index.js` and `examples/*.json` are generated too. Let
the build write them; do not edit them directly.

## House rules for a style clause

The linter enforces these, so a build failure will tell you which one you have
tripped. They exist because they measurably change what the model produces.

* **A style prefix only.** Describe how the picture is rendered — light,
  surface, line, palette, process. Never what is in it. No subjects, no poses,
  no "a woman standing".
* **No instructions.** No "do not add", no "the style governs the whole image".
* **Close with the medium**, matching the family: `anime style image`,
  `photograph style image`, `oil painting style image`.
* **Open by naming the process, then commas.** `Plein-air painting, fast
  wet-into-wet strokes, … oil painting style image,` — no colon after the
  opening phrase.
* **Use the word the craft uses.** Paint is *painting*; pencil, pen, crayon and
  chalk are *drawing*; a camera *captures*; prints are *prints*. **Rendering**
  is reserved for CGI, 3D, game art, vector and generative work. The linter
  checks the opening word against the entry's medium.
* **Never name a frame size.** No ratios, no *widescreen*, no *tall framing* —
  the workflow sets the canvas, and a clause that argues with it makes the
  result worse.
* **End with a comma, not a full stop.** The clause hands over to whatever the
  user typed.
* **British spelling** — colour, grey, centre.
* **380 characters maximum**, and every booru tag must exist in `data/tags.txt`.

Imported packs (the `[Extra]` family) are exempt from the writing rules and the
tag vocabulary — their structure is still checked. Do not apply house rules to
them retrospectively; they are somebody else's work, kept as it was.

## Adding styles

Add entries to an existing pack in `tools/written/`, or create a new numbered
one. Each entry needs a name, family, axis, medium, clause (`nl`), tags, and
optional negative tags:

```json
{
  "name": "[Paint] Gouache Poster",
  "family": "Traditional Painting",
  "axis": "style",
  "medium": "painting style image",
  "nl": "Gouache painting, flat opaque colour blocks, chalky matte surface, crisp poster edges, painting style image,",
  "tags": ["flat_color", "poster", "traditional_media"],
  "tags_negative": ["photorealistic"],
  "written": true
}
```

Then `bash tools/build_all.sh`. A duplicate name or id fails the lint, as does a
tag outside the vocabulary.

Merging a duplicate? Keep the old name as an alias rather than deleting it —
saved workflows and existing previews still refer to it.

## Changing the interface

* `tools/check_web.mjs` walks every import and call in `web/` and fails on an
  undefined function or a bad import. It runs inside `build_all.sh`.
* `tools/audit_web.mjs` reports unused exports and user data interpolated into
  markup without escaping. Both should stay at zero.
* Bump the version string in `web/css.js` whenever you change the stylesheet, or
  browsers keep the old one.
* Layout maths belongs in `tools/harness/*.mjs` — small node scripts that prove
  a sizing rule without a browser. Add one rather than eyeballing a fix.

## Two traps worth knowing

* **Widget values are stored by position.** Adding or reordering a widget shifts
  every saved value after it. The node also writes a copy keyed by name, and
  `web/main.js` carries a table of historical layouts; add an entry there when
  you change the widget list.
* **Stored settings are permanent.** The browser remembers its filters in
  `localStorage`. Never reuse a stored value for a different meaning — give the
  new thing a new token. Doing otherwise once made the catalog open empty.

## Commits and pull requests

* One change per pull request, with a title that names the cause rather than the
  symptom.
* Add a `CHANGELOG.md` entry under a new version heading, and bump `version` in
  `pyproject.toml` — `preflight.sh` refuses a version with no entry. Pushing a
  version already on the registry fails the publish.
* Say what you tested. "Ran the build chain" is enough for a catalog change; for
  behaviour, say what you clicked.

## Licence and third-party work

MIT, as in [LICENSE](LICENSE). Contributions are accepted under the same terms.
Do not add material from another project without checking its licence and
recording it in `THIRD-PARTY-NOTICES.md` — that is how the `[Extra]` family is
handled.

## A note for Windows contributors

Working copies get CRLF while the repository keeps LF. That is expected. If git
reports every line of a file as changed, it is a line-ending difference, not
your edit.
