# Security policy

## Reporting a vulnerability

Report privately, not in a public issue.

* **GitHub** — [open a private security advisory](https://github.com/Neon-Sparks/ComfyUI-NeonsStyleExplorer/security/advisories/new)
  on this repository. That is the preferred route: it is private, it keeps the
  discussion with the code, and it can issue a CVE if one is warranted.
* If advisories are unavailable to you, open a public issue saying only that you
  have a security report and how to reach you. Send no details in the open.

Please include what you can: the version, how to reproduce it, and what an
attacker gains. A proof of concept helps, even a rough one.

**What to expect.** This is a single-maintainer project, so I will not promise
hours. I aim to acknowledge a report within 72 hours, tell you whether it is in
scope within a week, and fix a confirmed issue in the next release. You will be
credited in the changelog unless you would rather not be.

## Supported versions

The latest release is the supported one. Fixes go into a new version rather than
back into older ones — this is a ComfyUI extension, and updating is a folder
replacement.

| Version | Supported |
| --- | --- |
| 2.4.x | yes |
| 2.3.x and earlier | no — update |

## What this extension actually does

Useful context for judging a report. Verified for every release; the detail is
in [AUDIT.md](AUDIT.md).

* **No outbound network access.** The package imports no HTTP client — no
  `requests`, no `urllib.request`, no `socket`, no `httpx`. The only `urllib`
  import is `urllib.parse.urlparse`, used to compare a request's Origin header
  against the ComfyUI host. Nothing is sent anywhere, and no telemetry of any
  kind is collected.
* **No dynamic code.** No `eval`, no `exec`, no `compile`, no `pickle`, no
  `subprocess`, no `os.system`, no shelling out.
* **It writes only inside its own folder.** Everything it saves lives under the
  package's `user/` directory: your overrides, custom styles, hidden styles,
  favourites, recents, named catalogs, preview images and LoRA trigger words.
  Shipped catalog files are never written.
* **It reads** its own catalog, ComfyUI's `loras` folder listing, and image
  files inside ComfyUI's output directory when you save a preview.
* **Every POST route checks the Origin header** against the ComfyUI host and
  returns 403 otherwise, so a page in another tab cannot drive it. GET routes
  are read-only.
* **Browser-supplied paths are contained.** Any path arriving from the browser
  is resolved and checked to be inside the output folder before it is opened.

## In scope

* Reading or writing a file outside the package's `user/` folder and ComfyUI's
  output directory.
* Any route that acts on a cross-site request, or a way past the Origin check.
* Path traversal through a style name, catalog name, LoRA name, preview
  filename, or an imported bundle.
* A crafted catalog bundle (`.zip`) that escapes its destination, exhausts
  memory or disk, or writes anything other than images and its manifest.
* Code execution through any input the node accepts.
* Stored cross-site scripting in the browser interface — a style name, family,
  catalog name or trigger word that executes rather than displays.

## Out of scope

* Anything requiring an attacker who already runs code on the machine, or who
  already has write access to your ComfyUI folder.
* Exposing your ComfyUI instance to the internet without authentication. ComfyUI
  is not built to be internet-facing; this extension inherits that.
* Deprecation warnings from ComfyUI's frontend about legacy APIs. This extension
  imports only `scripts/app.js` and `scripts/api.js`; those warnings come from
  another extension.
* The content of the style catalog. A clause producing an image you dislike is a
  bug report, not a security report.

## If you are reviewing this for a registry

[AUDIT.md](AUDIT.md) opens with a data-flow statement written for exactly that
purpose, and records what each audit checked and found.
