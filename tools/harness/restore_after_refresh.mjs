// A browser refresh restores the graph BEFORE the catalog is fetched. Does the
// node keep the user's style, or condemn it against the definition's stub list?
const DEFINITION = ["None", "🎲 Random"];          // what the node ships with
const CATALOG = ["None", "🎲 Random", "[Paint] Plein Air", "[Anime] Cel Shading Bands"];

function makeNode() {
    return { widgets: [
        { name: "style", value: "None", options: { values: [...DEFINITION] } },
        { name: "style_weight", value: 1.0, options: { min: 1, max: 5 } },
        { name: "quality", value: "", options: {} },
    ] };
}
const widget = (node, name) => node.widgets.find((w) => w.name === name);
const valueFits = (w, v) => {
    const o = w?.options?.values;
    if (Array.isArray(o) && o.length) return o.includes(v);
    return true;
};

function configure(node, values, ready) {
    node._nsSaved = {};
    node.widgets.forEach((w, i) => { node._nsSaved[w.name] = values[i]; });
    node.widgets.forEach((w, i) => {
        if (valueFits(w, values[i])) { w.value = values[i]; return; }
        if (!ready && Array.isArray(w.options?.values)) { w.value = values[i]; return; }   // the fix
        w.value = w.options?.values?.[0] ?? w.value;                                        // sanitise
    });
}
function syncCombos(node, ready) {
    if (!ready) return;
    const w = widget(node, "style");
    w.options.values = [...CATALOG];
    if (!w.options.values.includes(w.value)) w.value = "None";
}
function restoreSaved(node, ready) {
    for (const [name, value] of Object.entries(node._nsSaved || {})) {
        const w = widget(node, name);
        if (!w || w.value === value) continue;
        const o = w.options?.values;
        if (!Array.isArray(o) || !o.length || o.includes(value)) w.value = value;
    }
    if (ready) delete node._nsSaved;
}

const saved = ["[Paint] Plein Air", 2.5, "masterpiece"];

// how it used to go
const old = makeNode();
old.widgets.forEach((w, i) => { w.value = valueFits(w, saved[i]) ? saved[i] : (w.options?.values?.[0] ?? w.value); });
console.log("  before the fix, after a refresh: style =", JSON.stringify(widget(old, "style").value));

// how it goes now: configure (catalog not ready) -> setup (catalog ready)
const now = makeNode();
configure(now, saved, false);
console.log("  with the fix, mid-load:          style =", JSON.stringify(widget(now, "style").value));
syncCombos(now, true); restoreSaved(now, true);
console.log("  with the fix, after setup:       style =", JSON.stringify(widget(now, "style").value),
            "| weight =", widget(now, "style_weight").value,
            "| quality =", JSON.stringify(widget(now, "quality").value));

// a style that really has gone from the catalog must not stick
const gone = makeNode();
configure(gone, ["[Paint] Deleted Style", 1, ""], false);
syncCombos(gone, true); restoreSaved(gone, true);
console.log("  a style deleted from the catalog:", JSON.stringify(widget(gone, "style").value));
