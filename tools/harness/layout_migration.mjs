// Exercise the layout scorer with value arrays shaped like real saves.
const LIVE = ["prompt","quality","negative","style","extra_style","custom_style","format","finish",
  "output_format","style_position","include_style_negative","style_weight","tag_separator","crawl",
  "crawl_source","crawl_missing_only","auto_gallery","roll_scope","roll_seed","control_after_generate"];
const OPTIONS = {
  style: ["None","[Anime] Chibi","[Painting] Sfumato"], extra_style: ["None","[Extra] Airbrush Art"],
  custom_style: ["None"], format: ["None","[Format] Album Cover"], finish: ["None","[Finish] Foil Stamp"],
  output_format: ["natural","danbooru","natural + danbooru"], style_position: ["start","end"],
  tag_separator: ["comma+space","comma","space"], crawl_source: ["main","extra","custom"],
  auto_gallery: ["off","first","every"], roll_scope: ["all","family","favourites","recent","has preview","missing preview"],
  control_after_generate: ["fixed","increment","decrement","randomize"], style_mix: ["blended with","mixed with","layered over","then also"],
};
const live = LIVE.map((name) => ({ name, options: { values: OPTIONS[name] } }));
function score(names, values) {
  let s = 0;
  names.forEach((name, i) => {
    const opts = OPTIONS[name];
    if (Array.isArray(opts) && opts.includes(values[i])) s += 1;
  });
  return s;
}
// a 1.9-1.12 save: same LENGTH as the current layout, different order
const OLD20 = ["prompt","quality","negative","style","style_2","style_3","custom_style","style_mix",
  "format","finish","output_format","style_position","include_style_negative","style_weight",
  "tag_separator","crawl","roll_scope","roll_seed","control_after_generate","auto_gallery"];
const oldValues = ["a cat","masterpiece","","[Anime] Chibi","None","None","None","blended with",
  "None","None","natural","start",true,1.5,"comma+space",false,"all",0,"randomize","off"];
console.log("old 20-value save scored as current layout:", score(LIVE, oldValues));
console.log("old 20-value save scored as its own layout:", score(OLD20, oldValues));
const currentValues = ["a cat","masterpiece","","[Anime] Chibi","None","None","None","None",
  "natural","start",true,1.0,"comma+space",false,"main",false,"off","all",54321,"randomize"];
console.log("current save scored as current layout:  ", score(LIVE, currentValues));
console.log("current save scored as the old layout:  ", score(OLD20, currentValues));
