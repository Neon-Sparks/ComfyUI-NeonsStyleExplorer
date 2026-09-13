<!--
Thanks for the patch. CONTRIBUTING.md has the house rules for style clauses and
the build chain; the short version is below.
-->

## What this changes

<!-- One or two sentences. Name the cause, not just the symptom. -->

## Why

<!-- The bug it fixes, or the gap it fills. Link an issue if there is one. -->

## Type of change

- [ ] Bug fix
- [ ] New styles or catalog corrections
- [ ] Node behaviour
- [ ] Interface
- [ ] Documentation
- [ ] Build, tests or tooling

## How I tested it

<!--
For a catalog change, "ran the build chain" is enough.
For behaviour, say what you clicked and what you saw.
-->

## Checks

- [ ] `bash tools/build_all.sh` — catalog rebuilt, lint clean, tests pass
- [ ] `bash tools/preflight.sh` — prints `preflight: ready to push`
- [ ] Edited `tools/written/*.json`, not the generated `styles/*.json`
- [ ] `CHANGELOG.md` entry added and `version` bumped in `pyproject.toml`

## If you touched the catalog

- [ ] Clause is a style prefix only — no subject, no instructions
- [ ] Opens by naming the process, commas after it, no colon
- [ ] Uses the craft's own word — painting, drawing, capture, print; rendering
      only for CGI, 3D, game art, vector and generative work
- [ ] Closes with the family's medium, and ends with a comma
- [ ] Names no frame size or aspect ratio
- [ ] British spelling, 380 characters or fewer, tags from `data/tags.txt`
- [ ] A merged duplicate keeps its old name as an alias

## If you touched the interface

- [ ] `tools/check_web.mjs` and `tools/audit_web.mjs` both clean
- [ ] Version string in `web/css.js` bumped if the stylesheet changed
- [ ] Widget list unchanged — or a layout entry added in `web/main.js`
- [ ] No stored `localStorage` value reused for a new meaning

## Anything reviewers should look at closely

<!-- Guesses you made, a trade-off you took, a corner you could not test. -->
