// Can the node still be dragged into dead space?
const ROWS = 36 + 22 + 32 + 22, T_MIN = 150, T_MAX = 420, W_MIN = 300, W_MAX = T_MAX + 46;
const panelHeight = (width) => Math.max(T_MIN, Math.min(T_MAX, Math.max(240, width) - 26)) + ROWS;
const ideal = (node, top = 150) => Math.round(top + panelHeight(node.size[0]) + 14);
const onResize = (node, size) => {           // what litegraph hands us mid-drag
    size[0] = Math.max(W_MIN, Math.min(W_MAX, Math.round(size[0])));
    node.size[0] = size[0];
    size[1] = ideal(node);
    node.size[1] = size[1];
    return [...size];
};
const node = { size: [380, 466] };
for (const drag of [[380, 1400], [380, 220], [1200, 900], [120, 300], [466, 700]]) {
    const out = onResize(node, [...drag]);
    console.log(`  dragged to ${String(drag[0]).padStart(4)}x${String(drag[1]).padStart(4)}  ->  node ${out[0]}x${out[1]}`);
}
const twice = onResize(node, [...node.size]);
console.log("  re-applying its own size changes nothing:", twice[0] === node.size[0] && twice[1] === node.size[1]);
