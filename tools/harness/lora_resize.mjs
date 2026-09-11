// Does a repeated resize settle, or creep? The old code fed the node's height
// back into the panel's height, so each pass added the slack again.
const ROWS = 36 + 22 + 32 + 22, MIN = 150, MAX = 420;
const sizePanel = (node) => {
    const width = Math.max(240, node.size[0]);
    const side = Math.max(MIN, Math.min(MAX, width - 26));
    return side + ROWS;
};
const fitNode = (node, top = 150) => {
    const height = sizePanel(node);
    const wanted = Math.round(top + height + 14);
    if (Math.abs(node.size[1] - wanted) > 4) node.size[1] = wanted;
    return node.size[1];
};
const node = { size: [380, 460] };
const seen = [];
for (let pass = 0; pass < 12; pass++) seen.push(fitNode(node));
console.log("width fixed, twelve layout passes:", seen.join(" "));
console.log("settles:", new Set(seen.slice(2)).size === 1);
// and the old behaviour, for comparison
const old = { size: [380, 460] };
const oldPass = () => {
    const panel = Math.max(200, old.size[1] - 150 - 8);
    old.size[1] = 150 + panel + 14;   // litegraph re-adds chrome each pass
    return old.size[1];
};
console.log("old maths, same twelve passes:", Array.from({ length: 12 }, oldPass).join(" "));
