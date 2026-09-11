import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { NODE_TYPES, RANDOM, entryOf, lastErrorText, loadCatalog, loadCatalogSets, loadGallery, namesOf, patchPreview, recordRun, saveRun, shotsOf, sourceNames, state } from "./api.js";
import { STYLE_SLOTS, activeSlot, advanceCrawl, attachPanel, claimSlot, say, composeNow, effectiveStyle, fitToContent, keepFitted, layout, refresh, rollStyle, saveImage, saveLatest, syncCrawl, value, widget } from "./panel.js";

function syncCombo(node, field, axis) {
    const w = widget(node, field);
    if (!w) return;
    // the main style slots carry the written catalog only; imported and custom
    // entries live in their own dropdowns
    const known = axis === "style" ? sourceNames("main") : namesOf(axis);
    // nothing loaded yet: leave the list the node definition supplied
    if (!known.length) return;
    const values = ["None", RANDOM, ...known];
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
    syncSlot(node, "extra_style", "extra");
    syncSlot(node, "custom_style", "custom");
}

/** A dropdown that carries one source's names, refreshed from the live catalog. */
function syncSlot(node, field, source) {
    const w = widget(node, field);
    if (!w || !(state.catalog.styles || []).length) return;
    const values = ["None", RANDOM, ...sourceNames(source)];
    w.options = w.options || {};
    w.options.values = values;
    if (!values.includes(w.value)) w.value = "None";
}

/**
 * Remember what a saved workflow asked for, by widget name.
 *
 * On a browser refresh the graph is restored before the catalog has been
 * fetched, so the dropdowns still hold the short list the node definition
 * shipped with. Judging a saved style against that list condemns it, which is
 * how a refresh used to reset everyone's settings. The values are held here and
 * applied once the real lists exist.
 */
const SKIP_WIDGETS = new Set(["ns_panel"]);

/** Every widget value this node owns, keyed by name. */
function namedValues(node) {
    const out = {};
    for (const w of node?.widgets || []) {
        if (!w?.name || SKIP_WIDGETS.has(w.name) || w.options?.serialize === false) continue;
        out[w.name] = w.value;
    }
    return out;
}

function stashSaved(node, live, values) {
    if (!Array.isArray(values)) return;
    node._nsSaved = node._nsSaved || {};
    live.forEach((w, index) => {
        if (index < values.length) node._nsSaved[w.name] = values[index];
    });
}

/** Put those values back, now that the dropdowns carry the catalog. */
function restoreSaved(node) {
    const saved = node?._nsSaved;
    if (!saved) return;
    const lost = [];
    for (const [name, value] of Object.entries(saved)) {
        const w = widget(node, name);
        if (!w || value === undefined || w.value === value) continue;
        const options = w.options?.values;
        const isCombo = Array.isArray(options) && options.length;
        if (!isCombo) {
            // switches, numbers and text have nothing to be checked against
            w.value = value;
        } else if (!state.ready) {
            continue;                    // judge it against the real list later
        } else if (options.includes(value)) {
            w.value = value;
        } else if (value !== "None") {
            lost.push(`${name} = '${value}'`);
        }
    }
    if (lost.length) {
        console.warn("Neons Style Explorer: a saved selection is no longer in the catalog — "
            + lost.join(", "));
    }
    if (state.ready) delete node._nsSaved;
}

function hook(node) {
    for (const w of node.widgets || []) {
        if (w._nsHooked || w.name === "ns_panel") continue;
        w._nsHooked = true;
        const original = w.callback;
        w.callback = function (...args) {
            const result = original?.apply(this, args);
            // one active slot: choosing here switches the others off
            if (STYLE_SLOTS.includes(w.name) && args[0] && args[0] !== "None") {
                claimSlot(node, w.name);
            }
            if (STYLE_SLOTS.includes(w.name)) refresh(node);
            // the crawl set depends on the switch and on the scope
            if (w.name === "crawl" || w.name === "roll_scope") {
                syncCrawl(node);
            }
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

    }
}

function setup(node) {
    attachPanel(node);
    syncCombos(node);
    hook(node);
    if (value(node, "crawl", false)) syncCrawl(node);
    refresh(node);
    layout(node);
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
        // patch the saved previews in rather than refetching the manifest
        let patched = 0;
        for (const entry of result.saved || []) {
            if (entry.key && entry.record) {
                patchPreview(entry.key, entry.record);
                patched += 1;
            }
        }
        if (!patched) await loadGallery();
        for (const node of app.graph?._nodes || []) {
            if (!NODE_TYPES.has(node.comfyClass || node.type)) continue;
            refresh(node);
            report(node, result);
        }
        return;
    }
    if (result === null || result?.error) {
        // a hard failure: say so on every Neons node rather than silently
        // dropping the image
        const why = result?.error || lastErrorText("auto-gallery could not reach the server");
        console.warn(`Neons Style Explorer: auto-gallery failed — ${why}`);
        for (const node of app.graph?._nodes || []) {
            if (NODE_TYPES.has(node.comfyClass || node.type)) say(node, why, true);
        }
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

/** Tell the user what the server did with this prompt's image. */
function report(node, result) {
    const mine = String(node.id);
    const saved = (result.saved || []).find((entry) => String(entry.node) === mine);
    if (saved) {
        say(node, `saved to ${saved.style}`);
        return;
    }
    const skipped = (result.skipped || []).find((entry) => String(entry.node) === mine);
    if (skipped && skipped.reason !== "another node") say(node, `not saved — ${skipped.reason}`, true);
}

/**
 * Record each queued prompt's style at QUEUE time.
 *
 * The node records what it composed with when it runs — but ComfyUI caches a
 * node whose inputs have not changed, so a re-queue can leave a prompt with no
 * record at all, and the server then had to guess from the most recent one.
 * That guess is how an image reached a style it was never made with. Here the
 * prompt id and the style are both known for certain, so no guess is needed.
 */
function watchQueue() {
    if (app._nsQueueWatched) return;
    app._nsQueueWatched = true;
    const original = app.queuePrompt?.bind(app);
    if (!original) return;
    app.queuePrompt = async function (number, batchCount) {
        // read the styles BEFORE the call: crawl advances the dropdown in
        // afterQueued, which runs inside it
        const carried = [];
        for (const node of app.graph?._nodes || []) {
            if (!NODE_TYPES.has(node.comfyClass || node.type)) continue;
            const style = effectiveStyle(node);
            if (style && style !== "None" && style !== RANDOM) {
                carried.push({ node: node.id, style,
                    mode: value(node, "auto_gallery", "off"),
                    prompt: value(node, "prompt", "") });
            }
        }
        const result = await original(number, batchCount);
        const promptId = result?.prompt_id || api.lastPromptId || state.lastQueuedId;
        if (promptId) {
            state.lastQueuedId = String(promptId);
            for (const item of carried) {
                recordRun(promptId, item.node, item.style, item.mode, item.prompt);
            }
        }
        return result;
    };
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
        watchQueue();
        for (const node of app.graph?._nodes || []) {
            if (!NODE_TYPES.has(node.comfyClass || node.type)) continue;
            syncCombos(node);
            restoreSaved(node);
            syncCombos(node);      // the restored style decides the active slot
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

        // Litegraph restores widget values BY INDEX, so any change to the
        // widget list shifts every value after it — which is how a switch came
        // back on a refresh holding its neighbour's setting. A copy keyed by
        // NAME travels with the workflow and settles the question.
        const onSerialize = nodeType.prototype.onSerialize;
        nodeType.prototype.onSerialize = function (info) {
            const result = onSerialize?.apply(this, arguments);
            try {
                if (info) info.ns_values = namedValues(this);
            } catch (err) {
                /* never let bookkeeping break saving a workflow */
            }
            return result;
        };

        const onConfigure = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function (info) {
            const result = onConfigure?.apply(this, arguments);
            // the by-name copy wins over anything index-mapping produced
            if (info?.ns_values && typeof info.ns_values === "object") {
                this._nsSaved = { ...(this._nsSaved || {}), ...info.ns_values };
            }
            setup(this);
            restoreSaved(this);
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

        // Litegraph applies widget values BY INDEX, so any release that adds,
        // removes or moves a widget would load an older workflow one place out
        // of step — style_mix landing in the format field, and so on down.
        //
        // Rather than patch positions, the known past layouts are listed by
        // name. A saved array whose length matches one of them is read with
        // that layout's names and rebuilt in the current order; anything the
        // old file did not have keeps the widget's own default.
        // Widget orders of past releases, taken from this repository's history
        // rather than memory — an invented layout is worse than none, because a
        // wrong match loads every value one place out of step. Each includes
        // the control widget litegraph adds after roll_seed.
        const LAYOUTS = [
            // 1.15.0 — style_2/3 and the imported slot, roll controls mid-list
            ["prompt", "quality", "negative", "style", "style_2", "style_3", "extra_style",
             "custom_style", "style_mix", "format", "finish", "output_format", "style_position",
             "include_style_negative", "style_weight", "tag_separator", "crawl", "crawl_source",
             "crawl_missing_only", "roll_scope", "roll_seed", "control_after_generate",
             "auto_gallery"],
            // 1.10.0 - 1.14.2 — custom_style added, no imported slot
            ["prompt", "quality", "negative", "style", "style_2", "style_3", "custom_style",
             "style_mix", "format", "finish", "output_format", "style_position",
             "include_style_negative", "style_weight", "tag_separator", "crawl",
             "crawl_missing_only", "roll_scope", "roll_seed", "control_after_generate",
             "auto_gallery"],
            // 1.8.0 - 1.9.x — before custom_style
            ["prompt", "quality", "negative", "style", "style_2", "style_3", "style_mix",
             "format", "finish", "output_format", "style_position", "include_style_negative",
             "style_weight", "tag_separator", "crawl", "crawl_missing_only", "roll_scope",
             "roll_seed", "control_after_generate", "auto_gallery"],
        ];

        /**
         * Is this value usable by this widget?
         *
         * The last line of defence: whatever the layout matching decides, a
         * combo must end up holding one of its own options and a number must
         * land inside its range. Without this a bad match leaves impossible
         * state on the node — a style_weight of 0.00 when its minimum is 1.
         */
        function valueFits(widget, value) {
            const options = widget?.options?.values;
            if (Array.isArray(options) && options.length) return options.includes(value);
            if (widget?.type === "number" && typeof value === "number") {
                const min = widget.options?.min;
                const max = widget.options?.max;
                if (typeof min === "number" && value < min) return false;
                if (typeof max === "number" && value > max) return false;
                return true;
            }
            if (typeof value === "object" && value !== null) return false;
            return true;
        }

        /**
         * How well does a set of names explain a saved value array?
         *
         * Length alone cannot identify a layout — the current one and the
         * 1.9-1.12 one both hold twenty values — so each candidate is scored on
         * how many of its combo widgets receive a value that is actually one of
         * their options. The right layout scores near-perfectly; a wrong one
         * puts "blended with" where an output format belongs and scores badly.
         */
        function scoreLayout(live, names, values) {
            let score = 0;
            names.forEach((name, index) => {
                const widget = live.find((w) => w.name === name);
                const options = widget?.options?.values;
                if (!Array.isArray(options) || !options.length) return;
                if (options.includes(values[index])) score += 1;
            });
            return score;
        }

        const configure = nodeType.prototype.configure;
        nodeType.prototype.configure = function (info) {
            try {
                const live = (this.widgets || []).filter((w) => w?.options?.serialize !== false);
                const values = info?.widgets_values;
                if (Array.isArray(values) && values.length) {
                    const current = live.map((w) => w.name);
                    const candidates = [current, ...LAYOUTS]
                        .filter((names) => names.length === values.length);
                    let best = candidates[0] || current;
                    let bestScore = candidates.length ? scoreLayout(live, best, values) : -1;
                    for (const names of candidates.slice(1)) {
                        const score = scoreLayout(live, names, values);
                        if (score > bestScore) {
                            best = names;
                            bestScore = score;
                        }
                    }
                    const sameOrder = best.length === current.length
                        && best.every((name, index) => name === current[index]);
                    if (!sameOrder || values.length !== live.length) {
                        const layout = candidates.length ? best : null;
                        const held = new Map((layout || []).map((name, index) => [name, values[index]]));
                        // style_2 and style_3 are gone: if an old file used one
                        // while the main slot was empty, keep that style rather
                        // than drop it
                        for (const spare of ["style_2", "style_3"]) {
                            const kept = held.get(spare);
                            const main = held.get("style");
                            if (kept && kept !== "None" && (!main || main === "None")) {
                                held.set("style", kept);
                            }
                        }
                        if (held.size) {
                            info.widgets_values = live.map((w, index) =>
                                held.has(w.name) ? held.get(w.name) : values[index]);
                            console.log(
                                "Neons Style Explorer: remapped a workflow saved with an older layout "
                                + `(${values.length} values -> ${live.length})`
                            );
                        } else {
                            console.warn(
                                "Neons Style Explorer: a saved workflow has an unfamiliar widget layout "
                                + `(${values.length} values, expected ${live.length}) — check its style slots`
                            );
                        }
                    }
                }
                // whatever happened above, nothing impossible may reach a widget
                const finalValues = info?.widgets_values;
                stashSaved(this, live, finalValues);
                if (Array.isArray(finalValues)) {
                    live.forEach((w, index) => {
                        if (index >= finalValues.length) return;
                        if (valueFits(w, finalValues[index])) return;
                        // the catalog has not arrived, so its dropdowns still
                        // hold the definition's short list: nothing to judge by
                        if (!state.ready && Array.isArray(w.options?.values)) return;
                        console.warn(
                            `Neons Style Explorer: '${finalValues[index]}' is not valid for `
                            + `${w.name}; using its default instead`
                        );
                        finalValues[index] = w.options?.values?.[0] !== undefined && Array.isArray(w.options.values)
                            ? (w.options.values.includes(w.value) ? w.value : w.options.values[0])
                            : w.value;
                    });
                }
            } catch (err) {
                console.warn("Neons Style Explorer: widget migration skipped", err);
            }
            return configure?.apply(this, arguments);
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
                        restoreSaved(this);   // a value held back on load
                        refresh(this);
                        composeNow(this);
                    },
                },
                { content: "Neons: fit node to content", callback: () => fitToContent(this) }
            );
        };
    },
});
