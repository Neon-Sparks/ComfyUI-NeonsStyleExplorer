/**
 * Neons Style Explorer 2 — the node's panel.
 *
 * The node keeps its style selection in one text widget ("styles"). This adds
 * a fixed-height panel under the widgets: a preview of the current style, what
 * the last run actually used, and buttons to browse, roll and save a preview.
 * The panel never changes height, so the node sizes the same way in both of
 * ComfyUI's node interfaces.
 */
import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { ensureCss } from "./v2_css.js";
import { MOD_KINDS, NODE_TYPES, formatPicks, h, loadCatalog, onChange, parsePicks, previewUrl,
    resolve, savePreview, store, tint } from "./v2_api.js";
import { openBrowser } from "./v2_browser.js";

const PANEL_H = 136;
const SETTINGS = ["prompt", "prompt_prefix", "negative", "styles", "strength", "output_as", "style_position", "roll_seed",
    ...MOD_KINDS];
const runs = new Map();          // prompt id -> { ids, auto, image }

function widgetOf(node, name) {
    return node.widgets?.find((entry) => entry.name === name);
}

/** The node's current settings, as the compose route and the browser want them. */
export function settingsOf(node) {
    const out = {};
    for (const name of SETTINGS) out[name] = widgetOf(node, name)?.value;
    return out;
}

function setStyles(node, text) {
    const box = widgetOf(node, "styles");
    if (!box) return;
    box.value = text;
    if (box.inputEl && box.inputEl.value !== text) box.inputEl.value = text;
    box.callback?.(text);
    node._ns2Ran = null;
    refresh(node);
    node.setDirtyCanvas?.(true, true);
}

function say(node, text) {
    node._ns2Say = text || "";
    refresh(node);
    if (text) {
        clearTimeout(node._ns2SayTimer);
        node._ns2SayTimer = setTimeout(() => {
            node._ns2Say = "";
            refresh(node);
        }, 4000);
    }
}

/** The style a saved preview belongs to: what the last run used, else the first named pick. */
function targetOf(node) {
    const ran = node._ns2Ran?.ids?.[0];
    if (ran && store.byId.has(ran)) return store.byId.get(ran);
    for (const pick of parsePicks(widgetOf(node, "styles")?.value)) {
        const found = resolve(pick.token);
        if (found) return found;
    }
    return null;
}

export function refresh(node) {
    const panel = node._ns2Panel;
    if (!panel) return;
    const picks = parsePicks(widgetOf(node, "styles")?.value);
    const named = picks.map((pick) => (pick.token.startsWith("@") ? null : resolve(pick.token)));
    const shown = targetOf(node);
    const ran = node._ns2Ran;

    let title = "No style: prompt only";
    if (picks.length) {
        title = picks.map((pick, index) => {
            const label = pick.token.startsWith("@") ? `dice ${pick.token}`
                : (named[index]?.name || `${pick.token} (not found)`);
            return Math.abs(pick.weight - 1) > 0.001 ? `${label} ×${pick.weight}` : label;
        }).join("  +  ");
    }
    const lines = [];
    if (ran?.names && picks.some((pick) => pick.token.startsWith("@"))) {
        lines.push(`Last run used: ${ran.names}`);
    } else if (shown) {
        lines.push([shown.catName, shown.sub].filter(Boolean).join(" › "));
        lines.push(shown.lead);
    } else if (!store.styles.length) {
        lines.push("Loading the catalog…");
    } else if (!picks.length) {
        lines.push(`${store.styles.length.toLocaleString()} styles. Press Browse to pick one.`);
    }
    const mods = MOD_KINDS.map((kind) => widgetOf(node, kind)?.value)
        .filter((value) => value && value !== "None");
    if (mods.length) lines.push(`+ ${mods.join(", ")}`);

    panel.title.textContent = title;
    panel.sub.textContent = lines.filter(Boolean).join("\n");
    panel.note.textContent = node._ns2Say || ran?.notes || "";

    const url = shown ? previewUrl(shown.id, 256) : "";
    panel.thumb.style.background = shown ? tint(shown) : "var(--ns2-panel)";
    if (url) {
        if (panel.img.getAttribute("src") !== url) panel.img.src = url;
        panel.img.style.display = "block";
        panel.ph.textContent = "";
    } else {
        panel.img.style.display = "none";
        panel.img.removeAttribute("src");
        panel.ph.textContent = shown ? "No preview yet" : (picks.length ? "" : "Browse styles");
    }
    panel.save.disabled = !shown || !store.latestImage;
    panel.save.title = !shown ? "Pick a style first"
        : (store.latestImage ? `Use the newest generated image as the preview for ${shown.name}`
            : "Generate an image first");
}

function browse(node) {
    openBrowser({
        value: widgetOf(node, "styles")?.value || "",
        settings: () => settingsOf(node),
        apply: (text) => setStyles(node, text),
    });
}

function roll(node) {
    if (!store.styles.length) {
        say(node, "The catalog is still loading.");
        return;
    }
    const current = targetOf(node);
    let pool = store.styles;
    // stay in the same category when one is already chosen: a roll is a
    // variation, not a change of subject
    if (current) pool = store.styles.filter((style) => style.cat === current.cat && style.id !== current.id);
    if (!pool.length) pool = store.styles;
    setStyles(node, pool[Math.floor(Math.random() * pool.length)].name);
}

async function save(node) {
    const style = targetOf(node);
    if (!style) return;
    const reply = await savePreview(style.id, store.latestImage);
    say(node, reply.ok ? `Preview saved for ${style.name}.` : (reply.error || "Could not save."));
}

function attach(node) {
    if (node._ns2Panel) return;
    ensureCss();
    const img = h("img", { alt: "", draggable: false });
    const ph = h("div", { class: "ns2-ph" });
    const thumb = h("div", { class: "ns2-thumb", title: "Browse styles", onclick: () => browse(node) },
        img, ph);
    const title = h("div", { class: "ns2-title" });
    const sub = h("div", { class: "ns2-sub", style: "white-space:pre-line" });
    const note = h("div", { class: "ns2-note" });
    const saveButton = h("button", { text: "Save preview", onclick: () => save(node) });
    const buttons = h("div", { class: "ns2-buttons" },
        h("button", { class: "key", text: "Browse", title: "Open the style browser",
            onclick: () => browse(node) }),
        h("button", { text: "Roll", onclick: () => roll(node),
            title: "Pick another style at random, from the same category when one is chosen" }),
        saveButton,
        h("button", { text: "Clear", title: "Remove the style", onclick: () => setStyles(node, "") }));
    const element = h("div", { class: "ns2 ns2-panel" }, thumb,
        h("div", { class: "ns2-info" }, title, sub, note, buttons));
    // the canvas should still pan and zoom when the pointer is over the panel
    element.addEventListener("wheel", (event) => app.canvas?.processMouseWheel?.(event), { passive: true });

    const widget = node.addDOMWidget("ns2_panel", "ns2_panel", element, {
        serialize: false,
        getMinHeight: () => PANEL_H,
        getMaxHeight: () => PANEL_H,
    });
    widget.serialize = false;
    widget.computeSize = () => [node.size?.[0] || 380, PANEL_H];
    node._ns2Panel = { element, thumb, img, ph, title, sub, note, save: saveButton };

    const box = widgetOf(node, "styles");
    if (box) {
        const previous = box.callback;
        box.callback = function (...args) {
            const result = previous?.apply(this, args);
            node._ns2Ran = null;
            refresh(node);
            return result;
        };
    }
    for (const kind of MOD_KINDS) {
        const mod = widgetOf(node, kind);
        if (!mod) continue;
        const previous = mod.callback;
        mod.callback = function (...args) {
            const result = previous?.apply(this, args);
            refresh(node);
            return result;
        };
    }
    // room for a few lines of prompt above the panel
    node.setSize?.([Math.max(node.size?.[0] || 0, 400), Math.max(node.size?.[1] || 0, 740)]);
    refresh(node);
    loadCatalog().catch(() => say(node, "Could not load the style catalog. Restart ComfyUI."));
}

function eachNode(visit) {
    for (const node of app.graph?._nodes || []) {
        if (NODE_TYPES.has(node.comfyClass || node.type)) visit(node);
    }
}

async function finishRun(promptId) {
    const run = runs.get(promptId);
    runs.delete(promptId);
    if (!run?.ids?.length || !run.image || !run.auto || run.auto === "off") return;
    await savePreview(run.ids[0], run.image, run.auto === "if missing");
}

app.registerExtension({
    name: "Neons.StyleExplorer2",
    async setup() {
        onChange(() => eachNode(refresh));
        api.addEventListener("executed", ({ detail }) => {
            const output = detail?.output;
            if (!output) return;
            const run = runs.get(detail.prompt_id) || {};
            if (output.ns2_style_ids) {
                run.ids = output.ns2_style_ids[0] || [];
                run.auto = output.ns2_auto?.[0] || "off";
            }
            const image = (output.images || []).find((entry) => entry?.filename);
            if (image) {
                run.image = image;
                store.latestImage = image;
                eachNode(refresh);
            }
            runs.set(detail.prompt_id, run);
            // a queue that is never drained must not grow without limit
            if (runs.size > 50) runs.delete(runs.keys().next().value);
        });
        api.addEventListener("execution_success", ({ detail }) => finishRun(detail?.prompt_id));
        api.addEventListener("execution_error", ({ detail }) => runs.delete(detail?.prompt_id));
        api.addEventListener("execution_interrupted", ({ detail }) => runs.delete(detail?.prompt_id));
    },
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (!NODE_TYPES.has(nodeData.name)) return;

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const result = onNodeCreated?.apply(this, arguments);
            attach(this);
            return result;
        };

        const onConfigure = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function () {
            const result = onConfigure?.apply(this, arguments);
            this._ns2Ran = null;
            refresh(this);
            return result;
        };

        const onExecuted = nodeType.prototype.onExecuted;
        nodeType.prototype.onExecuted = function (message) {
            const result = onExecuted?.apply(this, arguments);
            this._ns2Ran = {
                ids: message?.ns2_style_ids?.[0] || [],
                names: message?.ns2_style_names?.[0] || "",
                notes: message?.ns2_notes?.[0] || "",
            };
            refresh(this);
            return result;
        };
    },
});

export { formatPicks };
