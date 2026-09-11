// Does the browser come back on the filters it was left on, and survive a
// Rescan rebuilding the dropdowns?
const store = new Map();
globalThis.localStorage = {
    getItem: (k) => (store.has(k) ? store.get(k) : null),
    setItem: (k, v) => store.set(k, String(v)),
};
const VIEW_KEY = "ns.lora.view";
const savedView = () => { try { return JSON.parse(localStorage.getItem(VIEW_KEY) || "{}") || {}; } catch { return {}; } };
const saveView = (v) => localStorage.setItem(VIEW_KEY, JSON.stringify({ ...savedView(), ...v }));
const restoreSelect = (sel, value) => {
    if (!value) return;
    if (sel.options.some((o) => o.value === value)) sel.value = value;
};
const gal = { value: "", options: [{ value: "" }, { value: "krea 2" }, { value: "Unsorted" }] };
const fam = { value: "", options: [{ value: "" }, { value: "portraits" }] };
const have = { value: "", options: [{ value: "" }, { value: "has" }, { value: "fav" }] };

// a visit: pick a gallery, a family, favourites only, scroll a bit
gal.value = "krea 2"; fam.value = "portraits"; have.value = "fav";
saveView({ search: "soft", gallery: gal.value, family: fam.value, have: have.value, scroll: 640 });

// next visit: fresh controls
const g2 = { value: "", options: [...gal.options] }, f2 = { value: "", options: [...fam.options] }, h2 = { value: "", options: [...have.options] };
const v = savedView();
restoreSelect(g2, v.gallery); restoreSelect(f2, v.family); restoreSelect(h2, v.have);
console.log(`  reopened on: gallery=${g2.value} family=${f2.value} filter=${h2.value} search=${v.search} scroll=${v.scroll}`);

// a Rescan rebuilds the gallery list; the choice must survive it
// innerHTML = "" then add(): a real select falls back to its first option
const rebuild = (sel, values) => {
    const had = sel.value;
    sel.options = values.map((value) => ({ value }));
    sel.value = values[0];
    restoreSelect(sel, had);
};
rebuild(g2, ["", "krea 2", "Unsorted", "new_folder"]);
console.log("  after Rescan:", g2.value || "(lost)");
// a gallery that has since been deleted must not stick
rebuild(g2, ["", "Unsorted"]);
console.log("  gallery gone from disk:", g2.value === "" ? "falls back to All galleries" : g2.value);
