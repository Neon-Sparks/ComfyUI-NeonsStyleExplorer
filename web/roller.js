/**
 * Neons Style Roller — shows the words a run rolled, previews a roll without
 * queueing the workflow, and saves a roll you like as a style.
 *
 * The node itself is plain widgets; this adds four things under them: a
 * "preview roll" button, a "keep these words" button, a "save as style" button,
 * and a read-only box holding the last words. With a seed set, the preview is
 * exactly what the next run will roll.
 *
 * A saved roll becomes one of your own styles in Neons Style Explorer 2
 * (My Styles), optionally with the newest generated image as its preview.
 */
import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { ComfyWidgets } from "../../scripts/widgets.js";
import { ensureCss } from "./v2_css.js";
import { h, loadCatalog, post, savePreview, store } from "./v2_api.js";

const NODE = "NeonsStyleRoller";
const SENT = ["kind", "count", "seed", "aspect", "vocabulary", "output_as", "weight",
    "always_include", "never_include", "theme", "words_per_term"];
const EMPTY = "Run the workflow, or press preview roll, to see the words here.";
const GROUP = "Rolled";

function widgetOf(node, name) {
    return node.widgets?.find((entry) => entry.name === name);
}

function show(node, words, note) {
    const box = widgetOf(node, "rolled");
    if (!box) return;
    const text = [words, note].filter(Boolean).join("\n\n");
    box.value = text;
    // the classic textarea is its own element and does not follow .value
    if (box.inputEl && box.inputEl.value !== text) box.inputEl.value = text;
    node.setDirtyCanvas?.(true, true);
}

/** Keep the roll as plain lists: what "save as style" writes down. */
function keep(node, terms, tags, words, seed) {
    node._nsRoll = {
        terms: Array.isArray(terms) ? terms.filter(Boolean) : [],
        tags: Array.isArray(tags) ? tags.filter(Boolean) : [],
        words: words || "",
        seed: Number(seed) || 0,
    };
}

/**
 * Hold on to the roll in the box: put the seed it came from on the node and
 * stop the seed from moving. Needed because the seed widget has usually moved
 * on by the time you see the words (randomize steps it after every run), and
 * because a seed of 0 never shows which seed it used.
 */
function keepWords(node) {
    const roll = node._nsRoll;
    if (!roll?.seed) {
        show(node, roll?.words || "", "Roll some words first: run the workflow or press preview roll.");
        return;
    }
    const seed = widgetOf(node, "seed");
    const control = widgetOf(node, "control_after_generate")
        || node.widgets?.find((entry) => entry.name?.startsWith("control"));
    if (seed) {
        seed.value = roll.seed;
        seed.callback?.(roll.seed);
    }
    if (control) {
        control.value = "fixed";
        control.callback?.("fixed");
    }
    show(node, roll.words, `Kept: seed ${roll.seed}, fixed. These words repeat until you change `
        + "a setting or the seed.");
}

async function preview(node) {
    const body = {};
    for (const name of SENT) body[name] = widgetOf(node, name)?.value;
    try {
        const response = await api.fetchApi("/neons_roller/roll", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        });
        const data = await response.json();
        if (!data?.ok) throw new Error(data?.error || `HTTP ${response.status}`);
        keep(node, data.terms, data.tags, data.words, data.seed);
        const unseeded = data.seeded ? ""
            : "Seed is 0, so the run will roll different words. Press keep these words to hold these.";
        show(node, data.words, [data.note, unseeded].filter(Boolean).join(" "));
    } catch (error) {
        show(node, "", `Could not roll a preview (${error?.message || error}). `
            + "Restart ComfyUI if the node was just installed.");
    }
}

function titleCase(text) {
    return String(text || "").replace(/\s+/g, " ").trim().split(" ")
        .map((word) => (word ? word[0].toUpperCase() + word.slice(1) : word)).join(" ");
}

function suggestName(terms) {
    let name = "";
    for (const term of terms) {
        const next = name ? `${name} ${titleCase(term)}` : titleCase(term);
        if (next.length > 40) break;
        name = next;
        if (name.split(" ").length >= 3) break;
    }
    return name.replace(/[,:@|()<>\[\]]/g, " ").replace(/\s+/g, " ").trim().slice(0, 40);
}

/** The naming dialog. Nothing is saved until Save is pressed. */
function saveDialog(node) {
    const roll = node._nsRoll;
    if (!roll?.terms?.length) {
        show(node, widgetOf(node, "rolled")?.value?.split("\n\n")[0] || "",
            "Roll some words first: run the workflow or press preview roll.");
        return;
    }
    ensureCss();
    document.querySelector(".ns2-roll-dialog")?.remove();

    const [first, ...rest] = roll.terms;
    const name = h("input", { type: "text", maxLength: 40, value: suggestName(roll.terms) });
    const group = h("input", { type: "text", maxLength: 60, value: GROUP,
        title: "The group inside My Styles this is filed under" });
    const lead = h("input", { type: "text", maxLength: 120,
        value: first ? first[0].toUpperCase() + first.slice(1) : "",
        title: "The phrase that leads the style. Naming the look and its medium works best." });
    const words = h("textarea", { value: rest.join("\n"),
        title: "One per line, most important first. Edit freely before saving." });
    const whole = h("input", { type: "checkbox", checked: true });
    const image = h("input", { type: "checkbox", checked: Boolean(store.latestImage),
        disabled: !store.latestImage });
    const error = h("div", { class: "err", role: "alert" });
    const save = h("button", { class: "key", text: "Save style" });
    const check = (box, label, hint) => h("label",
        { style: "flex-direction:row;align-items:flex-start;gap:8px;color:var(--ns2-fg)" },
        box, h("span", {}, label, h("div", { class: "hint",
            style: "color:var(--ns2-dim);font-size:11px;margin-top:2px", text: hint })));

    const overlay = h("div", { class: "ns2 ns2-overlay ns2-roll-dialog" },
        h("div", { class: "ns2-form", role: "dialog", "aria-label": "Save roll as a style" },
            h("div", { class: "box" },
                h("h3", { style: "margin:0", text: "Save this roll as a style" }),
                h("div", { class: "hint", style: "color:var(--ns2-dim);font-size:12px;line-height:1.45",
                    text: "It is added to My Styles in Neons Style Explorer 2, where it can be "
                        + "used, blended and rolled like any other style." }),
                h("label", {}, "Name", name),
                h("label", {}, "Lead", lead),
                h("label", {}, `Words (${rest.length})`, words),
                h("label", {}, "Group", group),
                check(whole, "Always write every word",
                    "Otherwise the strength setting on Style Explorer 2 shortens it: light keeps "
                    + "the first two words, standard four."),
                check(image, "Use the newest generated image as its preview",
                    store.latestImage ? "The last image any node made in this session."
                        : "No image has been generated in this session yet."),
                error,
                h("div", { class: "ns2-actions" }, save,
                    h("button", { text: "Cancel", onclick: () => close() })))));

    function close() {
        document.removeEventListener("keydown", onKey, true);
        overlay.remove();
    }
    function onKey(event) {
        if (event.key !== "Escape") return;
        event.preventDefault();
        event.stopPropagation();
        close();
    }
    overlay.addEventListener("mousedown", (event) => {
        if (event.target === overlay) close();
    });
    save.addEventListener("click", async () => {
        const parts = words.value.split(/[\n,]/).map((part) => part.trim()).filter(Boolean);
        if (!name.value.trim()) {
            error.textContent = "Give the style a name.";
            name.focus();
            return;
        }
        save.disabled = true;
        error.textContent = "";
        // tags follow the words that are still there, in the same order
        const byTerm = new Map(roll.terms.map((term, index) => [term, roll.tags[index]]));
        const tags = [lead.value.trim().toLowerCase(), ...parts]
            .map((term) => byTerm.get(term) || byTerm.get(term.toLowerCase())).filter(Boolean);
        const reply = await post("/neons_style2/custom/save", { style: {
            name: name.value, sub: group.value, lead: lead.value, parts, tags,
            fixed: whole.checked, traits: [] } });
        if (!reply.ok) {
            save.disabled = false;
            error.textContent = reply.error || "Could not save.";
            return;
        }
        let note = `Saved "${reply.name}" to My Styles.`;
        if (image.checked && store.latestImage) {
            await loadCatalog().catch(() => null);
            const saved = await savePreview(reply.id, store.latestImage);
            note += saved.ok ? " The newest image is its preview."
                : ` The preview was not saved: ${saved.error || "unknown error"}.`;
        } else {
            loadCatalog().catch(() => null);
        }
        close();
        show(node, roll.words, note);
    });
    document.addEventListener("keydown", onKey, true);
    document.body.append(overlay);
    name.focus();
    name.select();
}

function attach(node) {
    if (widgetOf(node, "rolled")) return;
    const button = node.addWidget("button", "preview roll", null, () => preview(node));
    button.serialize = false;
    button.options = { ...(button.options || {}), serialize: false };
    button.tooltip = "Roll now with these settings, without running the workflow.";

    const holder = node.addWidget("button", "keep these words", null, () => keepWords(node));
    holder.serialize = false;
    holder.options = { ...(holder.options || {}), serialize: false };
    holder.tooltip = "Set the seed to the one these words came from and fix it, so they repeat.";

    const keeper = node.addWidget("button", "save as style", null, () => saveDialog(node));
    keeper.serialize = false;
    keeper.options = { ...(keeper.options || {}), serialize: false };
    keeper.tooltip = "Save the words shown below as a style for Neons Style Explorer 2.";

    const made = ComfyWidgets.STRING(node, "rolled", ["STRING", { multiline: true }], app);
    const box = made?.widget || widgetOf(node, "rolled");
    if (!box) return;
    // display only: never saved with the workflow, never sent with the prompt
    box.serialize = false;
    box.options = { ...(box.options || {}), serialize: false, read_only: true };
    box.value = "";
    if (box.inputEl) {
        box.inputEl.readOnly = true;
        box.inputEl.placeholder = EMPTY;
    }
    const size = node.computeSize?.();
    if (size) node.setSize?.([Math.max(node.size[0], 330), Math.max(node.size[1], size[1])]);
}

app.registerExtension({
    name: "Neons.StyleRoller",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== NODE) return;

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const result = onNodeCreated?.apply(this, arguments);
            attach(this);
            return result;
        };

        const onExecuted = nodeType.prototype.onExecuted;
        nodeType.prototype.onExecuted = function (message) {
            const result = onExecuted?.apply(this, arguments);
            const words = message?.ns_rolled_words?.[0] || "";
            keep(this, message?.ns_rolled_terms?.[0], message?.ns_rolled_tags?.[0], words,
                message?.ns_rolled_seed?.[0]);
            show(this, words, message?.ns_roller_note?.[0] || "");
            return result;
        };
    },
});
