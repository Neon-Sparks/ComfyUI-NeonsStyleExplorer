globalThis.__calls = [];
globalThis.__replies = {};
// a small stand-in catalog for the crawl route
const NAMES = ["[A] one", "[A] two", "[A] three", "[A] four", "[A] five"];
globalThis.__replies["/neons_style/crawl"] = (process.env.EMPTY ? { ok: false } : { ok: true, names: NAMES, count: NAMES.length });
globalThis.__replies["/neons_style/catalog"] = { styles: NAMES, formats: [], finishes: [], families: ["Anime & Manga"], favourites: [], recents: [], coverage: {} };
globalThis.__replies["/neons_style/gallery"] = { previews: {} };
globalThis.__replies["/neons_style/compose"] = { ok: true, positive: "", negative: "" };

// minimal DOM so the panel module can be imported
globalThis.document = { createElement: () => ({ style: {}, classList: { toggle() {}, add() {}, contains: () => false }, querySelector: () => null, querySelectorAll: () => [], appendChild() {}, addEventListener() {}, remove() {} }), body: { appendChild() {} }, querySelector: () => null, getElementById: () => null };
globalThis.window = { addEventListener() {}, removeEventListener() {}, innerWidth: 1200, innerHeight: 800 };

const panel = await import("./ext/web/panel.js");
const api = await import("./ext/web/api.js");
await api.loadCatalog();

const node = {
    id: 7,
    widgets: [
        { name: "style", value: "None", callback() {} },
        { name: "crawl", value: true, callback() {} },
        { name: "roll_scope", value: "all", callback() {} },
        { name: "auto_gallery", value: "every", callback() {} },
    ],
    setDirtyCanvas() {},
};

console.log("style before:", panel.value(node, "style", "None"));
await panel.syncCrawl(node);
console.log("after syncCrawl:", panel.value(node, "style", "None"));
for (let i = 0; i < 4; i++) {
    panel.advanceCrawl(node);
    console.log(`after advance ${i + 1}:`, panel.value(node, "style", "None"));
}
