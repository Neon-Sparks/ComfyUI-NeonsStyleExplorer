// What does the browser tell the server a prompt's style is, at queue time?
const RANDOM = "\u{1F3B2} Random";
const nodes = [
    { label: "a chosen style",        slot: "[Painting] Acrylic", random: false, last: "[Anime] Chibi" },
    { label: "random_roll on",        slot: "None",               random: true,  last: "[Anime] Chibi" },
    { label: "nothing picked yet",    slot: "None",               random: false, last: "" },
    { label: "an old dice workflow",  slot: RANDOM,               random: false, last: "[Anime] Chibi" },
];
const effectiveStyle = (n) => (n.slot === RANDOM || n.slot === "None" ? n.last : n.slot);

for (const n of nodes) {
    // the rule: never speak for a run whose style is not decided yet
    const skipped = n.random;
    const style = skipped ? null : effectiveStyle(n);
    const sent = !skipped && style && style !== "None" && style !== RANDOM ? style : null;
    const verdict = n.random
        ? (sent === null ? "records nothing — the node reports what it rolls" : `WRONG: would record ${sent}`)
        : (sent ? `records ${sent}` : "records nothing");
    console.log(`  ${n.label.padEnd(22)} ${verdict}`);
}
