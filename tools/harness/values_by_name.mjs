// Widget values restore BY INDEX. What happens to a switch when the widget list
// gains one entry — and does the by-name copy survive it?
const OLD = ["prompt","quality","negative","style","extra_style","custom_style","format","finish",
  "output_format","style_position","include_style_negative","style_weight","tag_separator",
  "crawl","crawl_missing_only","auto_gallery","roll_scope","roll_seed","control_after_generate"];
const NEW = ["prompt","quality","negative","style","extra_style","custom_style","format","finish",
  "output_format","style_position","include_style_negative","style_weight","tag_separator",
  "crawl","crawl_source","crawl_missing_only","auto_gallery","roll_scope","roll_seed",
  "control_after_generate"];                       // crawl_source inserted at 14

const savedValues = OLD.map((n) => {
    if (n === "crawl_missing_only") return true;    // the user turned it ON
    if (n === "auto_gallery") return false;
    if (n === "crawl") return true;
    if (n === "roll_seed") return 54321;
    if (n === "style") return "[Paint] Plein Air";
    return "";
});
const byName = Object.fromEntries(OLD.map((n, i) => [n, savedValues[i]]));

const build = () => NEW.map((name) => ({ name, value: name === "roll_seed" ? 0 : (name.startsWith("crawl") || name === "auto_gallery" ? false : "") }));
const get = (ws, n) => ws.find((w) => w.name === n);

// by index, as litegraph does it
const indexed = build();
savedValues.forEach((v, i) => { if (indexed[i]) indexed[i].value = v; });
console.log("  by index  : crawl_missing_only =", get(indexed, "crawl_missing_only").value,
            "| auto_gallery =", get(indexed, "auto_gallery").value,
            "| crawl_source =", JSON.stringify(get(indexed, "crawl_source").value));

// by name, as the node now saves it
const named = build();
savedValues.forEach((v, i) => { if (named[i]) named[i].value = v; });     // index pass first
for (const [n, v] of Object.entries(byName)) { const w = get(named, n); if (w) w.value = v; }
console.log("  by name   : crawl_missing_only =", get(named, "crawl_missing_only").value,
            "| auto_gallery =", get(named, "auto_gallery").value,
            "| crawl =", get(named, "crawl").value,
            "| roll_seed =", get(named, "roll_seed").value);
