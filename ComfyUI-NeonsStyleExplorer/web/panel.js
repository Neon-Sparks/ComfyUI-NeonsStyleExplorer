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
    saveRun,
    useCatalogSet,
    shotUrl,
    shotsOf,
    starStyle,
    state,
} from "./api.js";

const PANEL_MIN = 300;
const TEXT_MIN = 52;
const GAP = 6;
const OUT_MIN = 96;
const OUT_MAX = 200;
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
export function crawlState(node) {
    if (!node._nsCrawl) node._nsCrawl = { names: [], index: 0, scope: "", family: "" };
    return node._nsCrawl;
}

/**
 * Refetch the walk whenever the switch, the scope or the family changes.
 *
 * The walk always starts wherever the style dropdown already is, so you can
 * park on the entry you want to populate from and switch crawl on there. If the
 * current style is not itself in the scope (say it has a preview and the scope
 * is "missing preview"), the walk starts at the first entry of the scope that
 * comes after it in catalog order. Pass restart:true to jump to the top.
 */
export async function syncCrawl(node, { restart = false } = {}) {
    const crawl = crawlState(node);
    if (!value(node, "crawl", false)) {
        refresh(node);
        return crawl;
    }
    const scope = String(value(node, "roll_scope", "all"));
    const current = value(node, "style", "None");
    const anchor = current === RANDOM || current === "None" ? node._nsLastStyle || "" : current;
    const family = entryOf(anchor)?.family || "";
    if (!crawl.names.length || crawl.scope !== scope || crawl.family !== family) {
        crawl.names = await loadCrawl(scope, scope === "family" ? family : "");
        crawl.scope = scope;
        crawl.family = family;
    }
    if (!crawl.names.length) {
        refresh(node);
        return crawl;
    }
    crawl.index = restart ? 0 : startIndex(crawl.names, anchor);
    // only move the dropdown when it is not already sitting on a real style
    if (restart || !anchor || anchor !== crawl.names[crawl.index]) {
        setValue(node, "style", crawl.names[crawl.index]);
    }
    refresh(node);
    return crawl;
}

/** Where in the walk a given style sits, or the next scope entry after it. */
function startIndex(names, anchor) {
    if (!anchor) return 0;
    const at = names.indexOf(anchor);
    if (at >= 0) return at;
    const all = namesOf("style");
    const position = all.indexOf(anchor);
    if (position < 0) return 0;
    const next = names.findIndex((name) => all.indexOf(name) >= position);
    return next >= 0 ? next : 0;
}

/**
 * Step to the next style in the crawl. Called once per QUEUED prompt (not per
 * execution), which is what makes a batch of N runs cover N styles — the same
 * moment ComfyUI advances a seed with control_after_generate.
 */
export function advanceCrawl(node) {
    if (!value(node, "crawl", false)) return;
    const crawl = crawlState(node);
    if (!crawl.names.length) return;
    crawl.index = (crawl.index + 1) % crawl.names.length;
    const next = crawl.names[crawl.index];
    const widgetRef = widget(node, "style");
    if (!widgetRef) return;
    widgetRef.value = next;
    widgetRef.callback?.(next);
    refresh(node);
    queueCompose(node);
    node.setDirtyCanvas?.(true, true);
}

export function effectiveStyle(node) {
    const picked = value(node, "style", "None");
    if (picked === RANDOM) return node._nsLastStyle || "";
    return picked && picked !== "None" ? picked : "";
}

export function setValue(node, name, next) {
    const found = widget(node, name);
    if (!found) return;
    found.value = next;
    found.callback?.(next);
    refresh(node);
    queueCompose(node);
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
        const stripH = strip && strip.children.length ? rowHeight(strip, 36) + GAP : 0;
        const shell = barH + stripH + GAP * 3;
        const minPanel = THUMB_MIN + OUT_MIN + shell;

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
        node._nsIdealHeight = top + Math.max(THUMB_MIN, Math.min(width - 26, 400)) + OUT_MIN + shell + 6;

        let panelH = height - top - 6;
        if (panelH < minPanel) {
            panelH = minPanel;
            if (!node._nsGrowing) {
                node._nsGrowing = true;
                node.setSize?.([width, top + panelH + 6]);
                node._nsGrowing = false;
            }
        }

        // split the panel: the preview takes what it can (it is square, so its
        // ceiling is the node width), the prompt box gets a bounded share, and
        // any height beyond that is handed back by shrinking the node — that is
        // what stopped the prompt box growing forever on a vertical drag.
        const inner = Math.max(THUMB_MIN + OUT_MIN, panelH - shell);
        const side = Math.min(THUMB_MAX, Math.max(THUMB_MIN, Math.min(width - 26, inner - OUT_MIN)));
        const outH = Math.min(OUT_MAX, Math.max(OUT_MIN, inner - side));
        const used = side + outH + shell;
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
            const out = panel.querySelector(".ns-out");
            if (stage) stage.style.height = `${side}px`;
            if (thumb) {
                thumb.style.width = `${side}px`;
                thumb.style.height = `${side}px`;
            }
            if (out) out.style.height = `${outH}px`;
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
    await loadGallery();
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
        onPick: (name) => setValue(node, field, name),
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
          <div class="ns-none">Click to browse styles</div>
          <div class="ns-chip"></div>
          <div class="ns-name"></div>
        </div>
      </div>
      <div class="ns-shots"></div>
      <div class="ns-bar">
        <button type="button" class="roll key">Roll</button>
        <button type="button" class="browse">Catalog</button>
        <button type="button" class="save">Save</button>
        <button type="button" class="edit">Edit</button>
        <button type="button" class="fav icon" title="Favourite">&#9734;</button>
        <button type="button" class="more icon" title="More">&#8943;</button>
      </div>
      <div class="ns-out">
        <header>
          <span class="mode"></span><span class="len"></span><span class="sp"></span>
          <button type="button" class="copy">Copy</button>
        </header>
        <pre></pre>
      </div>
    `;

    panel.querySelector(".ns-thumb").onclick = () => browse(node, "style", "style");
    panel.querySelector(".roll").onclick = () => rollStyle(node, "style");
    panel.querySelector(".browse").onclick = () => browse(node, "style", "style");
    panel.querySelector(".save").onclick = () => saveLatest(node);
    panel.querySelector(".edit").onclick = () => {
        const name = effectiveStyle(node);
        if (!name) return;
        openEditor({ name, onSaved: () => refresh(node) });
    };
    panel.querySelector(".fav").onclick = async () => {
        const name = effectiveStyle(node);
        if (!name) return;
        await starStyle(name);
        refresh(node);
    };
    panel.querySelector(".copy").onclick = async () => {
        const text = node._nsComposed?.positive || "";
        if (text) await navigator.clipboard?.writeText(text);
    };
    panel.querySelector(".more").onclick = (ev) => {
        const name = effectiveStyle(node);
        const shots = name ? shotsOf(name) : null;
        menu(ev, [
            ...catalogMenu(node),
            { label: "Browse formats", run: () => browse(node, "format", "format") },
            { label: "Browse finishes", run: () => browse(node, "finish", "finish") },
            "-",
            { label: "Roll style 2", run: () => rollStyle(node, "style_2") },
            { label: "Roll style 3", run: () => rollStyle(node, "style_3") },
            "-",
            { label: "New custom style", run: () => openEditor({ create: true, onSaved: () => refresh(node) }) },
            { label: "Clear styles", run: () => ["style", "style_2", "style_3", "format", "finish"].forEach((f) => setValue(node, f, "None")) },
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

function paint(node, data) {
    node._nsComposed = data;
    const panel = node._nsPanel;
    if (!panel) return;
    const pre = panel.querySelector(".ns-out pre");
    const mode = panel.querySelector(".mode");
    const len = panel.querySelector(".len");
    const positive = data?.positive || "";
    const negative = data?.negative || "";
    pre.textContent = positive || "(add a prompt or pick a style)";
    if (negative) {
        const span = document.createElement("span");
        span.className = "neg";
        span.textContent = `negative: ${negative}`;
        pre.appendChild(span);
    }
    const rolled = value(node, "style", "None") === RANDOM && node._nsLastStyle;
    mode.textContent = `${value(node, "output_format", "natural")} · style ${value(node, "style_position", "start")}`
        + (rolled ? " · last roll" : "");
    len.textContent = positive ? `${positive.length} chars` : "";
}

export function queueCompose(node) {
    clearTimeout(node._nsTimer);
    node._nsTimer = setTimeout(() => composeNow(node), 170);
}

export async function composeNow(node) {
    const data = await composeRemote({
        prompt: value(node, "prompt", ""),
        quality: value(node, "quality", ""),
        negative: value(node, "negative", ""),
        styles: ["style", "style_2", "style_3"]
            .map((field) => (field === "style" ? effectiveStyle(node) || value(node, field, "None") : value(node, field, "None")))
            .filter((name) => name && name !== "None"),
        format: value(node, "format", "None"),
        finish: value(node, "finish", "None"),
        output_format: value(node, "output_format", "natural"),
        style_position: value(node, "style_position", "start"),
        style_mix: value(node, "style_mix", "blended with"),
        tag_separator: value(node, "tag_separator", "comma+space"),
        style_weight: Number(value(node, "style_weight", 1.5)) || 1,
        include_style_negative: Boolean(value(node, "include_style_negative", true)),
        roll_scope: value(node, "roll_scope", "all"),
    });
    if (data) paint(node, data);
}

export { saveLatest, rollStyle };
