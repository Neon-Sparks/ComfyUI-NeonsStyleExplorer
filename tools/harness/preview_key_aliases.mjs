// The node holds a name the style used to have. Does the browser now find the
// same preview key the server writes?
const entries = [
    { name: "[Painting] My Expressionism", id: "traditio.expressionism",
      aliases: ["[Painting] Expressionism", "[Painting][Clio] Expressionism"] },
    { name: "[Painting] Abstract Expressionism", id: "traditio.abstract_expressionism_2",
      aliases: ["[Painting][v2] Abstract Expressionism"] },
];
const catalog = { by_name: Object.fromEntries(entries.map((e) => [e.name, e])) };
const indexAliases = (c) => {
    const byAlias = {};
    for (const entry of Object.values(c.by_name || {})) {
        byAlias[entry.name.toLowerCase()] = entry;
        for (const a of entry.aliases || []) if (!byAlias[a.toLowerCase()]) byAlias[a.toLowerCase()] = entry;
    }
    c.by_alias = byAlias; return c;
};
const slug = (s) => String(s).replace(/[^A-Za-z0-9]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 140);
const old = (name) => slug(catalog.by_name[name]?.id || name);
const now = (name) => slug((catalog.by_name[name] || catalog.by_alias[name.toLowerCase()])?.id || name);
indexAliases(catalog);
const SERVER = "traditio_expressionism";
for (const probe of ["[Painting] My Expressionism", "[Painting] Expressionism", "[Painting][Clio] Expressionism"]) {
    console.log(`  ${probe.padEnd(36)} before: ${old(probe).padEnd(24)} after: ${now(probe).padEnd(24)} ${now(probe) === SERVER ? "matches the server" : "MISMATCH"}`);
}
console.log(`  a different style stays separate: ${now("[Painting] Abstract Expressionism")}`);
