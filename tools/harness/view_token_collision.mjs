// A browser left on 2.2.0's "My styles" option reopens under 2.4.x. Does it
// land somewhere that shows styles?
const OLD_TOKEN = "\u0000mine";            // what 2.2.0-2.4.0 saved
const versions = {
    "2.4.1 (reused the token)": { custom: "\u0000mine",  edited: "\u0000edited" },
    "2.4.2 (new token)":        { custom: "\u0000own",   edited: "\u0000edited" },
};
const catalogue = [
    { name: "[Anime] Cel Shading", source: "shipped" },
    { name: "[Painting] Acrylic",  source: "shipped" },
];                                          // a user with no custom styles

for (const [label, tokens] of Object.entries(versions)) {
    const options = ["", tokens.custom, tokens.edited, "Anime & Manga", "Traditional Painting"];
    // restore: only applied when the option still exists
    const restored = options.includes(OLD_TOKEN) ? OLD_TOKEN : "";
    const rows = catalogue.filter((entry) => {
        if (restored === tokens.custom) return entry.source === "custom";
        if (restored === tokens.edited) return entry.source === "override";
        return true;
    });
    console.log(`  ${label.padEnd(26)} restores to ${JSON.stringify(restored)} -> ${rows.length} styles shown`);
}
