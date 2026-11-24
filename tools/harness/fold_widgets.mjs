// Do the settings fold with their switch, and does roll_seed hold still while
// the dice is off? Run like crawl_steps.mjs: copy web/*.js into ext/web/ next
// to this file, then `node fold_widgets.mjs`. Exits non-zero on a failure.
globalThis.__calls = [];
globalThis.__replies = {};
globalThis.document = { createElement: () => ({ style: {}, classList: { toggle() {}, add() {}, contains: () => false }, querySelector: () => null, querySelectorAll: () => [], appendChild() {}, addEventListener() {}, remove() {} }), body: { appendChild() {} }, querySelector: () => null, getElementById: () => null };
globalThis.window = { addEventListener() {}, removeEventListener() {}, innerWidth: 1200, innerHeight: 800 };
globalThis.requestAnimationFrame = () => 0;

const panel = await import("./ext/web/panel.js");

let failed = 0;
const check = (label, ok) => {
    console.log(`  ${ok ? "ok     " : "PROBLEM"} ${label}`);
    if (!ok) failed += 1;
};

// the control litegraph adds after a seed, advancing it once per queued prompt
let advanced = 0;
const control = { name: "control_after_generate", value: "randomize", afterQueued() { advanced += 1; }, beforeQueued() { advanced += 1; } };
const names = ["prompt", "style", "output_format", "tag_separator", "crawl", "crawl_source",
    "crawl_missing_only", "auto_gallery", "random_roll", "random_source", "roll_scope", "roll_seed"];
const node = {
    id: 1,
    size: [430, 760],
    widgets: names.map((name) => ({ name, value: false, callback() {} })),
    setDirtyCanvas() {},
    setSize() {},
};
const w = (name) => node.widgets.find((item) => item.name === name);
w("output_format").value = "natural";
w("roll_seed").linkedWidgets = [control];
node.widgets.push(control);
const hidden = () => node.widgets.filter((item) => item.hidden).map((item) => item.name).sort().join(", ");
const order = () => node.widgets.map((item) => item.name).join(",");
const before = order();

console.log("folding");
panel.syncFold(node);
check("everything off: crawl_source, random_source, the seed, its control and tag_separator fold",
    hidden() === "control_after_generate, crawl_source, random_source, roll_seed, tag_separator");
check("roll_scope and crawl_missing_only never fold (the arrows use them)",
    !w("roll_scope").hidden && !w("crawl_missing_only").hidden);

w("random_roll").value = true;
panel.syncFold(node);
check("dice on: its source, seed and control come back", hidden() === "crawl_source, tag_separator");

w("crawl").value = true;
w("output_format").value = "danbooru";
panel.syncFold(node);
check("crawl on and booru output: nothing is folded", hidden() === "");

w("crawl").value = false;
w("random_roll").value = false;
w("output_format").value = "natural + danbooru";
panel.syncFold(node);
check("natural + danbooru keeps tag_separator", !w("tag_separator").hidden && w("crawl_source").hidden);
check("folding never adds, removes or reorders a widget", order() === before);

console.log("seed");
panel.holdSeed(node);
panel.holdSeed(node);                       // attaching twice must not double-wrap
control.afterQueued();
control.beforeQueued();
check("dice off: queueing does not advance roll_seed", advanced === 0);
w("random_roll").value = true;
control.afterQueued();
check("dice on: it advances once per queued prompt", advanced === 1);

console.log(failed ? `fold check: ${failed} problem(s)` : "fold check: clean");
process.exit(failed ? 1 : 0);
