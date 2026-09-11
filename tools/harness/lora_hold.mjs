// The frontend may resize a node without calling onResize. Does the draw pass
// still pull it back? Simulate: user stretch, then frames of drawing.
const ROWS = 36 + 22 + 32 + 22, T_MIN = 150, T_MAX = 420, W_MIN = 300, W_MAX = T_MAX + 46;
const ideal = (node, top = 150) =>
    Math.round(top + Math.max(T_MIN, Math.min(T_MAX, Math.max(240, node.size[0]) - 26)) + ROWS + 14);
const holdSize = (node) => {
    const width = Math.max(W_MIN, Math.min(W_MAX, Math.round(node.size[0])));
    if (Math.abs(node.size[0] - width) > 1) node.size[0] = width;
    const height = ideal(node);
    if (Math.abs(node.size[1] - height) > 2) node.size[1] = height;
    return [...node.size];
};
const node = { size: [380, 630] };
node.size[1] = 1500;                      // a stretch that bypassed onResize
console.log("  after the stretch:", node.size.join("x"));
const frames = Array.from({ length: 4 }, () => holdSize(node).join("x"));
console.log("  next four draw frames:", frames.join("  "));
node.size[0] = 1000;                      // stretched wide instead
console.log("  widened to 1000:", holdSize(node).join("x"), "then", holdSize(node).join("x"));
