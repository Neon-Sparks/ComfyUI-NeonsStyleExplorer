import { app } from "../../scripts/app.js";
import { ensureCss } from "./css.js";
import { menu, openCatalog, openEditor } from "./catalog_ui.js";
import {
    RANDOM,
    composeRemote,
    deleteShot,
    deleteStyleShots,
    isFavourite,
    entryOf,
    keyOf,
    loadGallery,
    rollRemote,
    saveShot,
    setCover,
    createCatalogSet,
    loadCatalog,
    loadCrawl,
    namesOf,
    slotFor,
    sourceNames,
    patchPreview,
    saveRun,
    useCatalogSet,
    shotUrl,
    shotsOf,
    starStyle,
    state,
} from "./api.js";

const PANEL_MIN = 210;   // preview + shot strip + buttons; no readout any more
const TEXT_MIN = 52;
const GAP = 6;
const STRIP_H = 36;   // one row of shot thumbnails, always reserved
const THUMB_MIN = 130;
const THUMB_MAX = 620;

const BASE_TEXT = { prompt: 108, quality: 58, negative: 74 };

export function widget(node, name) {
    return node.widgets?.find((w) => w.name === name);
}

export function value(node, name, fallback = "") {
    const found = widget(node, name);
    return found ? found.value : fallback;
}

/**
 * The style this node is really working with. When the dropdown is on the dice
 * entry that is whatever the last execution rolled, which is what the preview,
 * the Save button and auto-gallery all have to follow.
 */
/**
 * Crawl mode state for a node: the ordered pool it walks and where it is.
 * Kept on the node so several nodes can crawl independently.
 */
export const STYLE_SLOTS = ["style", "extra_style", "custom_style"];

/**
 * The slot currently in use.
 *
 * Only one style dropdown is active at a time: choosing in one switches the
 * others off, so there is never any doubt about which list the arrows step,
 * which entry the preview shows, or what a run will compose.
 */
export function activeSlot(node) {
    for (const field of STYLE_SLOTS) {
        const held = value(node, field, "None");
        if (held && held !== "None") return field;
    }
    return "style";
}

/** Switch the other style slots off when one is chosen. */
export function claimSlot(node, field) {
    for (const other of STYLE_SLOTS) {
        if (other === field) continue;
        const found = widget(node, other);
        if (found && found.value && found.value !== "None") found.value = "None";
    }
}

/** Which source the active slot draws from. */
export function sourceOf(node) {
    const field = activeSlot(node);
    if (field === "extra_style") return "extra";
    if (field === "custom_style") return "custom";
    return "main";
}

/** The dropdown crawl is walking: main, extra or custom. */
export function crawlField(node) {
    const source = String(value(node, "crawl_source", "main"));
    if (source === "extra") return { source, field: "extra_style" };
    if (source === "custom") return { source, field: "custom_style" };
    return { source, field: "style" };
}

export function crawlState(node) {
    if (!node._nsCrawl) node._nsCrawl = { names: [], scope: "", family: "" };
    return node._nsCrawl;
}

/**
 * Fetch the list of styles the current scope allows. It does NOT track a
 * position: the walk's position is always the style dropdown itself (see
 * hopStyle). A separate counter was the cause of a crawl skipping entries —
 * anything that refreshed the list re-seeded the counter mid-batch and the walk
 * jumped.
 */
export async function syncCrawl(node, { restart = false } = {}) {
    const crawl = crawlState(node);
    if (!value(node, "crawl", false)) {
        refresh(node);
        return crawl;
    }
    const scope = String(value(node, "roll_scope", "all"));
    const current = value(node, crawlField(node).field, "None");
    const anchor = current === RANDOM || current === "None" ? node._nsLastStyle || "" : current;
    const family = entryOf(anchor)?.family || "";
    const { source } = crawlField(node);
    if (!crawl.names.length || crawl.scope !== scope || crawl.family !== family || crawl.source !== source) {
        crawl.names = await loadCrawl(scope, scope === "family" ? family : "", source);
        crawl.scope = scope;
        crawl.family = family;
        crawl.source = source;
    }
    if (!crawl.names.length) {
        // an empty scope must never freeze the walk: standing still pins a whole
        // batch to one style
        crawl.names = namesOf("style");
        console.warn(
            `Neons Style Explorer: the '${scope}' scope is empty, so crawl is walking the whole catalog`
        );
    }
    // Only ever move the dropdown deliberately — on a restart, or when it is not
    // yet on a real style. Moving it on a refresh would lose your place.
    const pool = crawlPool(node);
    if (pool.length && (restart || !anchor)) setValue(node, crawlField(node).field, pool[0]);
    refresh(node);
    return crawl;
}

/**
 * The ordered list the walk steps through right now: the scope's styles, minus
 * the ones that already have a preview when "only missing previews" is on. It
 * is recomputed at every step, so previews saved during the run drop out of the
 * walk as they are made.
 */
function crawlPool(node) {
    const crawl = crawlState(node);
    // While crawling, the source is whatever crawl_source says — never the
    // active slot. Deriving it from the slot meant that if the fetched list was
    // not ready, the fallback came from the wrong source and a main-catalog
    // name was written into the extra slot, which cannot hold it.
    const source = value(node, "crawl", false) ? crawlField(node).source : sourceOf(node);
    const base = crawl.names.length && crawl.source === source
        ? crawl.names
        : sourceNames(source);
    const scope = String(value(node, "roll_scope", "all"));
    // stepping by hand honours the scope too: set roll_scope to "has preview"
    // and the arrows walk only the entries that have one
    if (!value(node, "crawl", false) && (scope === "has preview" || scope === "missing preview")) {
        const want = scope === "has preview";
        const filtered = base.filter((name) => Boolean(shotsOf(name)) === want);
        if (filtered.length) return filtered;
    }
    if (!value(node, "crawl_missing_only", false)) return base;
    const missing = base.filter((name) => !shotsOf(name));
    return missing.length ? missing : base;   // all covered: keep moving
}

/**
 * Step the style dropdown by one, in either direction.
 *
 * The position is derived from whatever the dropdown currently holds, never
 * from a stored index, so nothing can drift: refreshing the pool, changing the
 * scope, arrowing by hand or picking a style in the browser all just move the
 * starting point of the next step. If the current style is not in the pool (it
 * has a preview and the walk is missing-only), the step lands on the nearest
 * pool entry in that direction.
 */
export function hopStyle(node, direction) {
    const pool = crawlPool(node);
    if (!pool.length) return;
    const all = namesOf("style");
    // crawling: the slot crawl_source names. Otherwise: whichever slot is in
    // use, so the arrows always step the list you are actually looking at.
    const field = value(node, "crawl", false) ? crawlField(node).field : activeSlot(node);
    const currentValue = value(node, field, "None");
    const current = currentValue === RANDOM || currentValue === "None"
        ? effectiveStyle(node) : currentValue;
    const at = pool.indexOf(current);
    let next;
    if (at >= 0) {
        next = pool[(at + direction + pool.length) % pool.length];
    } else {
        const position = all.indexOf(current);
        if (position < 0) {
            next = pool[direction > 0 ? 0 : pool.length - 1];
        } else if (direction > 0) {
            next = pool.find((name) => all.indexOf(name) > position) ?? pool[0];
        } else {
            const before = pool.filter((name) => all.indexOf(name) < position);
            next = before[before.length - 1] ?? pool[pool.length - 1];
        }
    }
    // Route by the entry itself: a name can only live in the slot that carries
    // its source, so this cannot put a value where it will be reset to None.
    if (next) setValue(node, slotFor(next), next);
}

/**
 * Called once per QUEUED prompt — the moment ComfyUI advances a seed with
 * control_after_generate — which is what makes a batch of N runs cover N
 * styles rather than repeating one.
 */
export async function advanceCrawl(node) {
    if (!value(node, "crawl", false)) return;
    const crawl = crawlState(node);
    const source = crawlField(node).source;
    // Wait for the right list before stepping. Firing the fetch and hopping
    // immediately meant the first step of a run could walk the wrong source.
    if (!crawl.names.length || crawl.source !== source) {
        try {
            await syncCrawl(node);
        } catch (err) {
            console.warn("Neons Style Explorer: could not load the crawl list", err);
        }
    }
    hopStyle(node, 1);
}

export function effectiveStyle(node) {
    const picked = value(node, activeSlot(node), "None");
    if (picked === RANDOM) return node._nsLastStyle || "";
    return picked && picked !== "None" ? picked : (node._nsLastStyle || "");
}

export function setValue(node, name, next) {
    const found = widget(node, name);
    if (!found) return;
    found.value = next;
    if (STYLE_SLOTS.includes(name) && next && next !== "None") claimSlot(node, name);
    found.callback?.(next);
    refresh(node);
    node.setDirtyCanvas?.(true, true);
}

/* --------------------------------------------------------------- layout */

const FLEX = new Set(["ns_panel", "prompt", "quality", "negative"]);

function fixedHeight(node, w, width) {
    if (!w || w.hidden || FLEX.has(w.name)) return 0;
    if (typeof w.computedHeight === "number") return w.computedHeight;
    if (typeof w.computeSize === "function") {
        const size = w.computeSize(width);
        if (Array.isArray(size) && size[1]) return size[1] + 4;
    }
    return (window.LiteGraph?.NODE_WIDGET_HEIGHT || 20) + 4;
}

function apply(node, name, height, width) {
    const w = widget(node, name);
    if (!w) return;
    w.computedHeight = height;
    w.computeSize = () => [width, height];
    w.computeLayoutSize = () => ({ minHeight: height, maxHeight: height, minWidth: 140 });
    const host = w.inputEl || w.element;
    const box = host && (host.tagName === "TEXTAREA" ? host : host.querySelector?.("textarea"));
    if (box) {
        // reserve a couple of pixels so the next widget can never overlap
        box.style.height = `${Math.max(TEXT_MIN - 8, height - 14)}px`;
        box.style.minHeight = "0";
        box.style.maxHeight = "none";
        box.style.boxSizing = "border-box";
        box.style.overflowY = "auto";
    }
}

function rowHeight(el, fallback) {
    if (!el) return fallback;
    const measured = el.offsetHeight || el.getBoundingClientRect().height;
    return measured > 4 ? Math.ceil(measured) : fallback;
}

/**
 * Layout contract: the three text boxes keep a fixed height, everything below
 * them belongs to the panel, and inside the panel the preview takes what it can
 * while the composed-prompt box absorbs the remainder.
 *
 * The panel's own height is taken from `last_y` — the y litegraph recorded for
 * that widget on the previous draw — instead of a sum of estimated widget
 * heights. Estimating was what left a dead strip at the bottom: every small
 * error in the estimate of the fourteen widgets above became blank canvas.
 */
export function layout(node) {
    if (!node || node._nsLaying) return;
    node._nsLaying = true;
    try {
        const panel = node._nsPanel;
        const width = Math.max(node.size?.[0] || 430, 320);
        const height = node.size?.[1] || 0;

        const barH = rowHeight(panel?.querySelector(".ns-bar"), 30);
        const strip = panel?.querySelector(".ns-shots");
        // The strip's row is reserved whether or not it holds thumbnails. It
        // used to take no space until the first preview arrived, and then the
        // panel grew mid-session and pushed the buttons out of the node.
        const stripH = STRIP_H + GAP;
        const shell = barH + stripH + GAP * 3;
        const minPanel = THUMB_MIN + shell;

        const promptH = BASE_TEXT.prompt;
        const qualityH = BASE_TEXT.quality;
        const negativeH = BASE_TEXT.negative;

        apply(node, "prompt", promptH, width);
        apply(node, "quality", qualityH, width);
        apply(node, "negative", negativeH, width);

        // preferred: measured start of the panel; fallback: arithmetic estimate
        const panelWidget = widget(node, "ns_panel");
        let top = typeof panelWidget?.last_y === "number" && panelWidget.last_y > 40
            ? panelWidget.last_y
            : null;
        if (top === null) {
            let fixed = 0;
            for (const w of node.widgets || []) fixed += fixedHeight(node, w, width);
            const chrome = (window.LiteGraph?.NODE_TITLE_HEIGHT || 30) + 12;
            const slots = Math.max(node.inputs?.length || 0, node.outputs?.length || 0) * 20;
            top = chrome + slots + fixed + promptH + qualityH + negativeH;
        }
        node._nsPanelTop = top;
        node._nsIdealHeight = top + Math.max(THUMB_MIN, Math.min(width - 26, 400)) + shell + 6;

        let panelH = height - top - 6;
        if (panelH < minPanel) {
            panelH = minPanel;
            if (!node._nsGrowing) {
                node._nsGrowing = true;
                node.setSize?.([width, top + panelH + 6]);
                node._nsGrowing = false;
            }
        }

        // The panel is now just the preview, the shot strip and the buttons:
        // the square preview takes what it can (its ceiling is the node width)
        // and anything left over is handed back by shrinking the node.
        const inner = Math.max(THUMB_MIN, panelH - shell);
        const side = Math.min(THUMB_MAX, Math.max(THUMB_MIN, Math.min(width - 26, inner)));
        const used = side + shell;
        if (used + 4 < panelH && !node._nsGrowing) {
            panelH = used;
            node._nsGrowing = true;
            node.setSize?.([width, top + panelH + 6]);
            node._nsGrowing = false;
        }

        apply(node, "ns_panel", panelH, width);

        if (panel) {
            panel.style.height = `${panelH}px`;
            const stage = panel.querySelector(".ns-stage");
            const thumb = panel.querySelector(".ns-thumb");
            if (stage) stage.style.height = `${side}px`;
            if (thumb) {
                thumb.style.width = `${side}px`;
                thumb.style.height = `${side}px`;
            }
        }
        node.setDirtyCanvas?.(true, true);
    } finally {
        node._nsLaying = false;
    }
}

/**
 * Snap the node to the real bottom of the panel: `last_y` for where it starts
 * plus the element's own `offsetHeight` for how tall the browser actually made
 * it. That covers the case where the frontend clamps our requested height —
 * whatever it decided, the node ends exactly there.
 */
export function fitToContent(node, quiet = false) {
    if (!node || node._nsFitting) return;
    node._nsFitting = true;
    try {
        layout(node);
        const panel = node._nsPanel;
        const panelWidget = widget(node, "ns_panel");
        let bottom = node._nsIdealHeight || 0;
        if (panel && typeof panelWidget?.last_y === "number" && panelWidget.last_y > 40) {
            const real = panel.offsetHeight || panelWidget.computedHeight || 0;
            if (real > 40) bottom = panelWidget.last_y + real + 6;
        }
        bottom = Math.round(bottom);
        if (bottom < 200) return;
        const current = node.size?.[1] || 0;
        if (Math.abs(current - bottom) <= 3) return;
        if (quiet && node._nsLastFit === bottom) return; // do not oscillate
        node._nsLastFit = bottom;
        node._nsGrowing = true;
        node.setSize?.([node.size?.[0] || 430, bottom]);
        node._nsGrowing = false;
        layout(node);
    } finally {
        node._nsFitting = false;
    }
}

/** Called from the node's draw loop: keeps the fit true as things change. */
export function keepFitted(node) {
    const now = performance.now();
    if (node._nsFitAt && now - node._nsFitAt < 250) return;
    node._nsFitAt = now;
    const panel = node._nsPanel;
    const panelWidget = widget(node, "ns_panel");
    if (!panel || typeof panelWidget?.last_y !== "number" || panelWidget.last_y <= 40) return;
    const real = panel.offsetHeight || 0;
    if (real <= 40) return;
    const bottom = Math.round(panelWidget.last_y + real + 6);
    if (Math.abs((node.size?.[1] || 0) - bottom) > 3) fitToContent(node, true);
}

/* -------------------------------------------------------------- preview */

/** One tile per saved shot: click to make it the cover, cross to delete it. */
function stripHtml(record, name) {
    if (!record || !record.count) return "";
    return record.shots
        .map(
            (shot) => `<span class="ns-shot${shot.file === record.cover ? " on" : ""}">
                 <button type="button" class="pick" data-file="${shot.file}" title="Use as cover">
                   <img loading="lazy" draggable="false" src="${shotUrl(name, shot.file)}" alt="">
                 </button>
                 <button type="button" class="drop" data-file="${shot.file}" title="Delete this preview">&#10005;</button>
               </span>`
        )
        .join("");
}

/**
 * A short line under the buttons: what auto-gallery just did, or why it did
 * nothing. Auto-saving used to fail in complete silence, which is indefensible
 * during an unattended crawl — you find out hours later that the catalog is
 * empty.
 */
export function say(node, text, bad = false) {
    const panel = node?._nsPanel;
    const note = panel?.querySelector(".ns-say");
    if (!note) return;
    note.textContent = text || "";
    note.classList.toggle("bad", Boolean(bad));
    note.style.display = text ? "block" : "none";
    clearTimeout(node._nsSayTimer);
    if (text) {
        node._nsSayTimer = setTimeout(() => {
            note.textContent = "";
            note.style.display = "none";
        }, 6000);
    }
}

/**
 * Put a freshly written style straight onto the node, ready to render.
 *
 * The dropdowns are built from the catalog that was loaded when the node was
 * created, so a brand-new style is not in their option lists yet — they have to
 * be refreshed here or the assignment is silently rejected as an unknown value.
 */
export async function adoptStyle(node, name) {
    if (!name) return;
    await loadCatalog();
    const all = namesOf("style");
    const mine = all.filter((entry) => (entryOf(entry)?.source || "shipped") === "custom");
    const lists = {
        style: ["None", RANDOM, ...all],
        style_2: ["None", RANDOM, ...all],
        style_3: ["None", RANDOM, ...all],
        custom_style: ["None", RANDOM, ...mine],
    };
    for (const [field, values] of Object.entries(lists)) {
        const found = widget(node, field);
        if (!found) continue;
        found.options = found.options || {};
        found.options.values = values;
    }
    // into whichever slot carries this style's source
    setValue(node, slotFor(name), name);
    await loadGallery();
    refresh(node);
    say(node, `selected ${name}`);
}

/** Redraw every Neons node that has a panel attached. */
function refreshAll() {
    for (const other of app.graph?._nodes || []) {
        if (other?._nsPanel) refresh(other);
    }
}

/** Catalog switching without leaving the node. */
function catalogMenu(node) {
    const { active, items, name } = state.catalogs;
    if (!items.length) return [];
    const entries = items.map((item) => ({
        label: `${item.id === active ? "• " : "   "}${item.name}${item.shots ? ` (${item.shots})` : ""}`,
        run: async () => {
            await useCatalogSet(item.id);
            refreshAll();
            refresh(node);
        },
    }));
    return [
        { label: `Catalog: ${name}`, disabled: true },
        ...entries,
        {
            label: "New catalog…",
            run: async () => {
                const label = prompt("Name the new catalog (for example: my Krea 2)", "");
                if (label === null || !label.trim()) return;
                await createCatalogSet(label.trim());
                await loadCatalog();
                await loadGallery();
                refresh(node);
            },
        },
        "-",
    ];
}

/**
 * Page through the catalog one style at a time, so you can flip through
 * previews on the node and stop on the one you want. This walks the whole style
 * list in catalog order and wraps at both ends; the shot strip below the
 * preview is what chooses between several images of the SAME style.
 */
export function refresh(node) {
    const panel = node._nsPanel;
    if (!panel) return;
    const picked = value(node, "style", "None");
    const rolled = picked === RANDOM;
    const name = effectiveStyle(node);
    const entry = entryOf(name);
    const shots = name ? shotsOf(name) : null;

    const img = panel.querySelector(".ns-thumb img");
    const none = panel.querySelector(".ns-none");
    const label = panel.querySelector(".ns-name");
    const chip = panel.querySelector(".ns-chip");
    const strip = panel.querySelector(".ns-shots");

    // the arrows are a manual version of one crawl step, so they follow the same
    // pool and stay usable while crawl is on
    const onlyMissing = Boolean(value(node, "crawl_missing_only", false));
    for (const arrow of panel.querySelectorAll(".ns-arrow")) {
        arrow.style.display = "flex";
        arrow.disabled = false;
        arrow.title = (arrow.classList.contains("prev") ? "Previous" : "Next")
            + (onlyMissing ? " style without a preview" : " style");
    }

    const crawling = Boolean(value(node, "crawl", false));
    label.textContent = rolled && name ? `rolled: ${name}` : (name || "");
    chip.textContent = rolled ? "random" : (entry ? entry.family.replace(" & ", "/") : "");
    chip.style.display = chip.textContent ? "block" : "none";

    // the dice is inert while crawling; say so rather than letting it look broken
    const rollButton = panel.querySelector(".roll");
    if (rollButton) {
        rollButton.disabled = crawling;
        rollButton.title = crawling
            ? "Crawl is on — the dice is disabled while it walks the list"
            : "Roll a random style";
    }

    if (shots) {
        img.src = shotUrl(name, shots.cover);
        img.style.display = "block";
        none.style.display = "none";
    } else {
        img.removeAttribute("src");
        img.style.display = "none";
        none.style.display = "flex";
        none.textContent = !name
            ? (rolled ? "A random style is rolled on the next run" : "Click to browse styles")
            : "No preview yet — generate, then Save";
    }

    strip.innerHTML = shots ? stripHtml(shots, name) : "";
    strip.querySelectorAll(".pick").forEach((button) => {
        button.onclick = async (ev) => {
            ev.preventDefault();
            await setCover(keyOf(name), button.dataset.file);
            await loadGallery();
            refresh(node);
        };
    });
    strip.querySelectorAll(".drop").forEach((button) => {
        button.onclick = async (ev) => {
            ev.preventDefault();
            await deleteShot(keyOf(name), button.dataset.file);
            await loadGallery();
            refresh(node);
        };
    });

    const star = panel.querySelector(".fav");
    if (star) {
        const on = Boolean(name) && isFavourite(name);
        star.innerHTML = on ? "&#9733;" : "&#9734;";
        star.classList.toggle("on", on);
    }
}

/**
 * Store one image against one style. Both arguments are passed in explicitly:
 * with several prompts running at once the caller knows which style produced
 * which image, and the node's current widgets do not.
 */
export async function saveImage({ node, style, image, prompt = "", silent = false }) {
    if (!style || !image) return false;
    const result = await saveShot({
        style,
        filename: image.filename,
        subfolder: image.subfolder || "",
        type: image.type || "output",
        prompt,
        make_cover: true,
    });
    if (result?.ok && result.key && result.record) patchPreview(result.key, result.record);
    else await loadGallery();
    if (node) refresh(node);
    if (!result?.ok && !silent) alert(result?.error || "Could not save that image.");
    return Boolean(result?.ok);
}

async function saveLatest(node, silent = false) {
    // Ask the server first: it knows which style produced the newest image,
    // which is not necessarily the one the dropdown shows (crawl moves it on).
    if (state.lastImages.length) {
        const result = await saveRun(state.lastPromptId, state.lastImages, {
            force: true,
            node: String(node.id),
        });
        if (result?.ok && result.saved?.length) {
            await loadGallery();
            refresh(node);
            return true;
        }
    }
    const name = effectiveStyle(node);
    if (!name) {
        if (!silent) {
            alert(value(node, "style", "None") === RANDOM
                ? "Nothing rolled yet — run the graph once, then Save."
                : "Pick a style first.");
        }
        return false;
    }
    const image = state.lastImages[0];
    if (!image) {
        if (!silent) alert("Generate an image first, then Save stores the latest result.");
        return false;
    }
    return saveImage({ node, style: name, image, prompt: value(node, "prompt", ""), silent });
}

async function rollStyle(node, field = "style") {
    const data = await rollRemote({
        axis: field === "format" ? "format" : field === "finish" ? "finish" : "style",
        scope: value(node, "roll_scope", "all"),
        family: entryOf(value(node, "style", "None"))?.family,
        exclude: [value(node, field, "None")],
    });
    if (data?.name) setValue(node, field, data.name);
}

function browse(node, axis, field) {
    openCatalog({
        axis,
        current: value(node, field, "None"),
        // a style goes to the slot that carries its source, not to whichever
        // slot opened the browser
        onPick: (name) => setValue(node, axis === "style" ? slotFor(name) : field, name),
    });
}

export function attachPanel(node) {
    if (node._nsPanel) return;
    ensureCss();
    const panel = document.createElement("div");
    panel.className = "ns-panel";
    panel.innerHTML = `
      <div class="ns-stage">
        <div class="ns-thumb">
          <img alt="style preview">
          <div class="ns-none" title="No preview saved for this style yet — generate one and it will be filed here">Click to browse styles</div>
          <button type="button" class="ns-arrow prev" title="Previous style">&#10094;</button>
          <button type="button" class="ns-arrow next" title="Next style">&#10095;</button>
          <div class="ns-chip"></div>
          <div class="ns-name"></div>
          <div class="ns-say"></div>
        </div>
      </div>
      <div class="ns-shots"></div>
      <div class="ns-bar">
        <button type="button" class="roll key">Roll</button>
        <button type="button" class="browse" title="Open the catalog browser: search, filter by family, see previews">Catalog</button>
        <button type="button" class="save" title="File the newest generated image under the style that produced it (not necessarily the one showing now)">Save</button>
        <button type="button" class="edit" title="Edit this style: rename it, change its clause, family, medium or tags">Edit</button>
        <button type="button" class="fav icon" title="Add or remove this style from favourites (roll_scope can then stay inside them)">&#9734;</button>
        <button type="button" class="more icon" title="Catalogs, format and finish browsing, extra style slots, new style, delete previews">&#8943;</button>
      </div>
    `;

    panel.querySelector(".ns-thumb").onclick = (ev) => {
        if (ev.target.closest(".ns-arrow")) return;  // arrows page the previews
        browse(node, "style", "style");
    };
    panel.querySelector(".prev").onclick = (ev) => {
        ev.stopPropagation();
        hopStyle(node, -1);
    };
    panel.querySelector(".next").onclick = (ev) => {
        ev.stopPropagation();
        hopStyle(node, 1);
    };
    panel.querySelector(".roll").onclick = () => rollStyle(node, "style");
    panel.querySelector(".browse").onclick = () => browse(node, "style", "style");
    panel.querySelector(".save").onclick = () => saveLatest(node);
    panel.querySelector(".edit").onclick = () => {
        const name = effectiveStyle(node);
        if (!name) return;
        openEditor({
            name,
            onSaved: (saved) => (saved && saved !== name ? adoptStyle(node, saved) : refresh(node)),
        });
    };
    panel.querySelector(".fav").onclick = async () => {
        const name = effectiveStyle(node);
        if (!name) return;
        await starStyle(name);
        refresh(node);
    };

    panel.querySelector(".more").onclick = (ev) => {
        const name = effectiveStyle(node);
        const shots = name ? shotsOf(name) : null;
        menu(ev, [
            ...catalogMenu(node),
            {
                label: "Copy the composed prompt",
                run: async () => {
                    const composed = await composeNow(node);
                    const text = composed?.positive || "";
                    if (!text) return say(node, "nothing to copy yet", true);
                    try {
                        await navigator.clipboard.writeText(text);
                        say(node, `copied ${text.length} characters`);
                    } catch (err) {
                        say(node, "the browser refused clipboard access", true);
                    }
                },
            },
            { label: "Browse formats", run: () => browse(node, "format", "format") },
            { label: "Browse finishes", run: () => browse(node, "finish", "finish") },
            "-",
            {
                label: "New custom style",
                run: () => openEditor({
                    create: true,
                    // straight onto the node when it saves, so the next queue
                    // renders it without a trip through the catalog
                    onSaved: (saved) => adoptStyle(node, saved),
                }),
            },
            { label: "Clear styles", run: () => ["style", "custom_style", "extra_style", "format", "finish"].forEach((f) => setValue(node, f, "None")) },
            "-",
            {
                label: "Delete this shot", bad: true, disabled: !shots,
                run: async () => {
                    await deleteShot(keyOf(name), shots.cover);
                    await loadGallery();
                    refresh(node);
                },
            },
            {
                label: "Delete all shots for this style", bad: true, disabled: !shots,
                run: async () => {
                    if (!confirm(`Delete every gallery image for ${name}?`)) return;
                    await deleteStyleShots(name);
                    await loadGallery();
                    refresh(node);
                },
            },
        ]);
    };

    const w = node.addDOMWidget("ns_panel", "panel", panel, { serialize: false });
    w.computeSize = () => [node.size?.[0] || 420, PANEL_MIN];
    node._nsPanel = panel;
}

/* --------------------------------------------------------- live compose */

export async function composeNow(node) {
    const data = await composeRemote({
        prompt: value(node, "prompt", ""),
        quality: value(node, "quality", ""),
        negative: value(node, "negative", ""),
        styles: ["style", "custom_style", "extra_style"]
            .map((field) => (field === "style" ? effectiveStyle(node) || value(node, field, "None") : value(node, field, "None")))
            .filter((name) => name && name !== "None"),
        format: value(node, "format", "None"),
        finish: value(node, "finish", "None"),
        output_format: value(node, "output_format", "natural"),
        style_position: value(node, "style_position", "start"),
        tag_separator: value(node, "tag_separator", "comma+space"),
        style_weight: Number(value(node, "style_weight", 1.0)) || 1,
        include_style_negative: Boolean(value(node, "include_style_negative", true)),
        roll_scope: value(node, "roll_scope", "all"),
    });
    // Nothing to paint any more — the readout is gone, since the node's
    // `positive` output can go straight into a Preview Text node. The composed
    // text is kept for the menu's copy action.
    if (data) node._nsComposed = data;
    return data;
}

export { saveLatest, rollStyle };
