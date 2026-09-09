# Dev harnesses

Neither ships with the node (`.comfyignore`), and neither needs ComfyUI running.

**`crawl_walk.mjs`** — the regression test for the walk itself. It asserts that
a full lap from a chosen start visits every entry exactly once (a stored
position counter used to drift and skip entries), that a pool resync landing
mid-walk moves nothing, and that "only missing previews" skips covered styles.
Copy the current `web/*.js` into `ext/web/` and run `node crawl_walk.mjs`.

**`crawl_steps.mjs`** — imports `web/panel.js` against stub `scripts/app.js` and
`scripts/api.js`, then drives `syncCrawl` and `advanceCrawl` over a fake node.
It answers "does the style dropdown actually advance per queued prompt", which
is the difference between a crawl that fills the catalog and one that files every
image under a single style. Run it from this directory:

    node crawl_steps.mjs        # normal: steps through the pool
    EMPTY=1 node crawl_steps.mjs  # empty scope: must still step, via fallback

To point it at the current web files, copy them next to it or symlink `ext/web`.

**`../crawl_probe.py`** and **`../route_probe.py`** — stand up a real aiohttp app
carrying the node's routes with a stub PromptServer, so the HTTP layer and the
per-prompt style records can be tested end to end:

    python3 tools/route_probe.py
    MODE=every STEPS=4 python3 tools/crawl_probe.py

Both need `aiohttp` (and `crawl_probe.py` needs Pillow + numpy), which ComfyUI
already provides; in a bare checkout use a venv.
