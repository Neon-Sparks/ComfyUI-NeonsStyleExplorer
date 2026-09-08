import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { NODE_TYPES, RANDOM, loadCatalog, loadCatalogSets, loadGallery, namesOf, saveRun, shotsOf, state } from "./api.js";
import { advanceCrawl, attachPanel, composeNow, effectiveStyle, fitToContent, keepFitted, layout, queueCompose, refresh, rollStyle, saveImage, saveLatest, syncCrawl, value, widget } from "./panel.js";

function syncCombo(node, field, axis) {
    const w = widget(node, field);
    if (!w) return;
    const values = ["None", RANDOM, ...namesOf(axis)];
    w.options = w.options || {};
    w.options.values = values;
    if (!values.includes(w.value)) w.value = "None";
}

function syncCombos(node) {
    syncCombo(node, "style", "style");
    syncCombo(node, "style_2", "style");
    syncCombo(node, "style_3", "style");
    syncCombo(node, "format", "format");
    syncCombo(node, "finish", "finish");
}

function hook(node) {
    for (const w of node.widgets || []) {
        if (w._nsHooked || w.name === "ns_panel") continue;
        w._nsHooked = true;
        const original = w.callback;
        w.callback = function (...args) {
            const result = original?.apply(this, args);
            if (w.name === "style") refresh(node);
            // the crawl set depends on the switch and on the scope
            if (w.name === "crawl" || w.name === "roll_scope") {
                syncCrawl(node);
            }
            queueCompose(node);
            return result;
        };
        if (w.name === "crawl") {
            // ComfyUI calls afterQueued once per QUEUED prompt, which is how
            // control_after_generate advances a seed across a batch. Stepping
            // here means queueing N runs walks N styles; stepping on execution
            // would give every run in the batch the same one.
            const afterQueued = w.afterQueued;
            w.afterQueued = function (...args) {
                const result = afterQueued?.apply(this, args);
                advanceCrawl(node);
                return result;
            };
        }
        const el = w.inputEl;
        if (el && !el._nsInput) {
            el._nsInput = true;
            el.addEventListener("input", () => queueCompose(node));
        }
    }
}

function setup(node) {
    attachPanel(node);
    syncCombos(node);
    hook(node);
    if (value(node, "crawl", false)) syncCrawl(node);
    refresh(node);
    layout(node);
    queueCompose(node);
    // widget positions only exist after a draw pass; snap the node then
    requestAnimationFrame(() => requestAnimationFrame(() => fitToContent(node)));
}

const MAX_TRACKED_RUNS = 32;

/** The bookkeeping for one queued prompt, created on first sight. */
function runFor(promptId) {
    const key = String(promptId || "");
    let run = state.runs.get(key);
    if (!run) {
        run = { images: [], nodes: new Map() };
        state.runs.set(key, run);
        // a prompt that errors out never reports success; do not leak its record
        while (state.runs.size > MAX_TRACKED_RUNS) {
            state.runs.delete(state.runs.keys().next().value);
        }
    }
    return run;
}

/**
 * Save this prompt's images against this prompt's styles. Everything comes from
 * the run record rather than the node's current widgets, because by the time a
 * parallel run finishes the dropdown may already be showing another style.
 */
async function autoGallery(promptId) {
    const run = state.runs.get(String(promptId || ""));
    const images = run?.images?.length ? run.images : state.lastImages;
    if (!images.length) return;

    // The server knows which style each prompt actually composed with. Crawl
    // moves the dropdown at QUEUE time, so the widget is already ahead of the
    // run that just finished; only the server's record is safe to trust.
    const result = await saveRun(promptId, images);
    if (result?.ok) {
        state.runs.delete(String(promptId || ""));
        await loadGallery();
        for (const node of app.graph?._nodes || []) {
            if (NODE_TYPES.has(node.comfyClass || node.type)) refresh(node);
        }
        return;
    }

    // Fallback for an older backend: pair from this prompt's own report.
    await loadGallery();
    for (const node of app.graph?._nodes || []) {
        if (!NODE_TYPES.has(node.comfyClass || node.type)) continue;
        const record = run?.nodes.get(String(node.id));
        if (run && !record) continue;
        const mode = String(record?.mode ?? value(node, "auto_gallery", "off"));
        if (mode === "off") continue;
        const name = record?.style || effectiveStyle(node);
        if (!name) continue;
        if (mode === "first" && shotsOf(name)) continue;
        await saveImage({
            node,
            style: name,
            image: images[0],
            prompt: record?.prompt ?? value(node, "prompt", ""),
            silent: true,
        });
    }
    if (promptId) state.runs.delete(String(promptId));
}

let listening = false;
function listen() {
    if (listening) return;
    listening = true;
    api.addEventListener("executed", ({ detail }) => {
        const run = runFor(detail?.prompt_id);
        if (detail?.prompt_id) state.lastPromptId = String(detail.prompt_id);
        const images = detail?.output?.images;
        if (Array.isArray(images) && images.length) {
            const clean = images.filter((image) => image?.filename);
            run.images.push(...clean);
            state.lastImages = clean; // the manual Save button means "the newest image"
        }
        // a Neons node reports the style it actually used for THIS prompt
        const style = detail?.output?.ns_style?.[0];
        if (style && detail?.node != null) {
            run.nodes.set(String(detail.node), {
                style,
                mode: detail.output.ns_auto_gallery?.[0] ?? "off",
                prompt: detail.output.ns_prompt?.[0] ?? "",
            });
        }
    });
    api.addEventListener("execution_success", ({ detail }) => autoGallery(detail?.prompt_id));
    api.addEventListener("execution_error", ({ detail }) => {
        if (detail?.prompt_id) state.runs.delete(String(detail.prompt_id));
    });
    api.addEventListener("execution_interrupted", ({ detail }) => {
        if (detail?.prompt_id) state.runs.delete(String(detail.prompt_id));
    });
}

app.registerExtension({
    name: "Neons.StyleExplorer",

    async setup() {
        await loadCatalog();
        await loadCatalogSets();
        await loadGallery();
        listen();
        for (const node of app.graph?._nodes || []) {
            if (!NODE_TYPES.has(node.comfyClass || node.type)) continue;
            syncCombos(node);
            refresh(node);
            layout(node);
        }
    },

    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (!NODE_TYPES.has(nodeData.name)) return;

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const result = onNodeCreated?.apply(this, arguments);
            if (!this._nsSized) {
                this._nsSized = true;
                this.setSize?.([Math.max(this.size?.[0] || 0, 430), Math.max(this.size?.[1] || 0, 760)]);
            }
            setup(this);
            return result;
        };

        const onConfigure = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function () {
            const result = onConfigure?.apply(this, arguments);
            setup(this);
            return result;
        };

        const onDrawForeground = nodeType.prototype.onDrawForeground;
        nodeType.prototype.onDrawForeground = function (...args) {
            const result = onDrawForeground?.apply(this, args);
            // widget positions are only known after a draw; correct the fit here
            if (!this.flags?.collapsed) keepFitted(this);
            return result;
        };

        const onDblClick = nodeType.prototype.onDblClick;
        nodeType.prototype.onDblClick = function (...args) {
            const result = onDblClick?.apply(this, args);
            fitToContent(this);
            return result;
        };

        const onResize = nodeType.prototype.onResize;
        nodeType.prototype.onResize = function (size) {
            const result = onResize?.apply(this, arguments);
            if (size) {
                size[0] = Math.max(size[0], 360);
                size[1] = Math.max(size[1], 620);
            }
            layout(this);
            return result;
        };

        const onExecuted = nodeType.prototype.onExecuted;
        nodeType.prototype.onExecuted = function (message) {
            const result = onExecuted?.apply(this, arguments);
            const rolled = message?.ns_style?.[0];
            if (rolled && rolled !== this._nsLastStyle) {
                this._nsLastStyle = rolled;
                // the dice resolved: point the preview, Save and auto-gallery at it
                loadGallery().then(() => refresh(this));
            }
            composeNow(this);
            return result;
        };

        const getExtraMenuOptions = nodeType.prototype.getExtraMenuOptions;
        nodeType.prototype.getExtraMenuOptions = function (canvas, options) {
            getExtraMenuOptions?.apply(this, arguments);
            options.push(
                { content: "Neons: roll a random style", callback: () => rollStyle(this, "style") },
                { content: "Neons: restart crawl from the top", callback: () => syncCrawl(this, { restart: true }) },
                { content: "Neons: save last image to gallery", callback: () => saveLatest(this) },
                {
                    content: "Neons: refresh catalog",
                    callback: async () => {
                        await loadCatalog();
                        await loadGallery();
                        syncCombos(this);
                        refresh(this);
                        composeNow(this);
                    },
                },
                { content: "Neons: fit node to content", callback: () => fitToContent(this) }
            );
        };
    },
});
