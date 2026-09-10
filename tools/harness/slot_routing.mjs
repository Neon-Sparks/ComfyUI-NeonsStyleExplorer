globalThis.__calls = []; globalThis.__replies = {};
const MAIN = ["[Anime] Chibi", "[Photo] Kodak Portra"];
const EXTRA = ["[Extra] 1-bit Pixel Art", "[Extra] Airbrush Art"];
const ALL = [...MAIN, ...EXTRA];
globalThis.__replies["/neons_style/catalog"] = {
  styles: ALL, formats: [], finishes: [], families: {}, family_order: ["Anime & Manga", "Extra"],
  shipped_families: ["Anime & Manga", "Photography & Film", "Extra"], imported_families: ["Extra"],
  by_name: Object.fromEntries(ALL.map((n) => [n, { name: n, id: n.toLowerCase().replace(/[^a-z0-9]+/g, "_"),
    family: n.startsWith("[Extra]") ? "Extra" : "Anime & Manga", axis: "style", medium: "style image",
    source: "shipped", written: true, aliases: [], tags: [], tags_negative: [] }])),
  favourites: [], recents: [], coverage: {},
};
globalThis.__replies["/neons_style/gallery"] = { previews: {} };
globalThis.__replies["/neons_style/compose"] = { ok: true, positive: "", negative: "" };
globalThis.document = { createElement: () => ({ style: {}, classList: { toggle() {}, add() {}, contains: () => false }, querySelector: () => null, querySelectorAll: () => [], appendChild() {}, addEventListener() {}, remove() {} }), body: { appendChild() {} }, querySelector: () => null, getElementById: () => null };
globalThis.window = { addEventListener() {}, removeEventListener() {}, innerWidth: 1200, innerHeight: 800 };
const panel = await import("./ext/web/panel.js");
const api = await import("./ext/web/api.js");
await api.loadCatalog();
const node = { id: 1, widgets: [
  { name: "style", value: "None", options: { values: ["None", ...MAIN] }, callback() {} },
  { name: "extra_style", value: "None", options: { values: ["None", ...EXTRA] }, callback() {} },
  { name: "custom_style", value: "None", options: { values: ["None"] }, callback() {} },
  { name: "crawl", value: false, callback() {} },
  { name: "crawl_source", value: "main", callback() {} },
  { name: "roll_scope", value: "all", callback() {} },
], setDirtyCanvas() {} };
console.log("slotFor(extra):", api.slotFor(EXTRA[0]), "| slotFor(main):", api.slotFor(MAIN[0]));
panel.setValue(node, api.slotFor(EXTRA[0]), EXTRA[0]);
console.log("after picking an Extra card -> style:", panel.value(node, "style", "None"),
            "| extra_style:", panel.value(node, "extra_style", "None"));
console.log("value survives an option-list sync:", node.widgets[1].options.values.includes(node.widgets[1].value));
console.log("preview follows the active slot:", panel.effectiveStyle(node));
panel.setValue(node, "style", MAIN[0]);
console.log("picking a main card switches the other off -> style:", panel.value(node, "style", "None"),
            "| extra_style:", panel.value(node, "extra_style", "None"));

// a crawl over the extra source, with the list NOT preloaded: every step must
// stay in the extra slot
globalThis.__replies["/neons_style/crawl"] = { ok: true, names: EXTRA, count: EXTRA.length };
const crawler = { id: 2, widgets: [
  { name: "style", value: "None", options: { values: ["None", ...MAIN] }, callback() {} },
  { name: "extra_style", value: "None", options: { values: ["None", ...EXTRA] }, callback() {} },
  { name: "custom_style", value: "None", options: { values: ["None"] }, callback() {} },
  { name: "crawl", value: true, callback() {} },
  { name: "crawl_source", value: "extra", callback() {} },
  { name: "roll_scope", value: "all", callback() {} },
], setDirtyCanvas() {} };
for (let i = 0; i < 4; i++) await panel.advanceCrawl(crawler);
console.log("crawl(extra) x4 -> extra_style:", panel.value(crawler, "extra_style", "None"),
            "| style stays:", panel.value(crawler, "style", "None"));
