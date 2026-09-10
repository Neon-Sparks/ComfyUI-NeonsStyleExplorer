globalThis.__calls = [];
globalThis.__replies = {};
const NAMES = Array.from({ length: 12 }, (_, i) => `[A] s${String(i + 1).padStart(2, "0")}`);
globalThis.__replies["/neons_style/crawl"] = { ok: true, names: NAMES, count: NAMES.length };
globalThis.__replies["/neons_style/catalog"] = { styles: NAMES, formats: [], finishes: [], families: ["Anime & Manga"], favourites: [], recents: [], coverage: {} };
globalThis.__replies["/neons_style/gallery"] = { previews: {} };
globalThis.__replies["/neons_style/compose"] = { ok: true, positive: "", negative: "" };
globalThis.document = { createElement: () => ({ style: {}, classList: { toggle() {}, add() {}, contains: () => false }, querySelector: () => null, querySelectorAll: () => [], appendChild() {}, addEventListener() {}, remove() {} }), body: { appendChild() {} }, querySelector: () => null, getElementById: () => null };
globalThis.window = { addEventListener() {}, removeEventListener() {}, innerWidth: 1200, innerHeight: 800 };

const panel = await import("./ext/web/panel.js");
const api = await import("./ext/web/api.js");
await api.loadCatalog();

function makeNode(extra = {}) {
    return {
        id: 7,
        widgets: [
            { name: "style", value: extra.style ?? "None", callback() {} },
            { name: "crawl", value: true, callback() {} },
            { name: "crawl_missing_only", value: extra.missingOnly ?? false, callback() {} },
        { name: "crawl_source", value: extra.source ?? "main", callback() {} },
        { name: "extra_style", value: "None", callback() {} },
        { name: "custom_style", value: "None", callback() {} },
            { name: "roll_scope", value: "all", callback() {} },
        ],
        setDirtyCanvas() {},
    };
}

// 1. a full lap from a chosen start must visit every entry exactly once
const node = makeNode({ style: "[A] s05" });
await panel.syncCrawl(node);
const seen = [panel.value(node, "style", "None")];
for (let i = 0; i < NAMES.length - 1; i++) {
    panel.advanceCrawl(node);
    seen.push(panel.value(node, "style", "None"));
}
console.log("start:", seen[0], "| visited:", seen.length, "| unique:", new Set(seen).size);
console.log("missed:", NAMES.filter((n) => !seen.includes(n)).length ? NAMES.filter((n) => !seen.includes(n)) : "none");

// 2. a resync landing mid-walk must not move or skip
const node2 = makeNode({ style: "[A] s01" });
await panel.syncCrawl(node2);
panel.advanceCrawl(node2); panel.advanceCrawl(node2);
const before = panel.value(node2, "style", "None");
await panel.syncCrawl(node2);                       // the 1.7.3 background resync
const after = panel.value(node2, "style", "None");
panel.advanceCrawl(node2);
console.log(`resync: at ${before} -> after resync ${after} -> next ${panel.value(node2, "style", "None")}`);

// 3. missing-only skips styles that already have previews
const covered = ["[A] s02", "[A] s03"];
globalThis.__replies["/neons_style/gallery"] = {
    previews: Object.fromEntries(covered.map((name) => [
        api.keyOf(name),
        { shots: [{ file: "x.jpg" }], cover: "x.jpg", count: 1, style: name },
    ])),
};
console.log("covered keys:", covered.map((n) => api.keyOf(n)).join(", "));
await api.loadGallery();
const node3 = makeNode({ style: "[A] s01", missingOnly: true });
await panel.syncCrawl(node3);
const walk = [panel.value(node3, "style", "None")];
for (let i = 0; i < 3; i++) { panel.advanceCrawl(node3); walk.push(panel.value(node3, "style", "None")); }
// a crawl over the extra source must drive the extra_style slot
const node4 = makeNode({ style: "None", source: "extra" });
await panel.syncCrawl(node4);
const walked = [panel.value(node4, "extra_style", "None")];
for (let i = 0; i < 2; i++) { panel.advanceCrawl(node4); walked.push(panel.value(node4, "extra_style", "None")); }
console.log("extra-source walk drives extra_style:", walked.join(" -> "), "| main slot stays:", panel.value(node4, "style", "None"));

console.log("missing-only walk:", walk.join(" -> "), "(s02 and s03 have previews)");
