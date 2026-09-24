// The arrows step through a style's saved images and wrap at both ends.
const shots = { count: 4, cover: "c.jpg",
    shots: [{ file: "a.jpg" }, { file: "b.jpg" }, { file: "c.jpg" }, { file: "d.jpg" }] };
const shotIndex = new Map();
const coverIndex = (s) => Math.max(0, s.shots.findIndex((x) => x.file === s.cover));
const step = (name, by) => {
    const at = shotIndex.get(name) ?? coverIndex(shots);
    const next = (at + by + shots.count) % shots.count;
    shotIndex.set(name, next);
    return `${shots.shots[next].file} (${next + 1}/${shots.count})`;
};
console.log("  opens on the cover:", `${shots.cover} (${coverIndex(shots) + 1}/${shots.count})`);
console.log("  next  ->", step("x", 1));
console.log("  next  ->", step("x", 1), " <- wrapped past the end");
console.log("  prev  ->", step("x", -1));
console.log("  prev  ->", step("x", -1));
console.log("  prev  ->", step("x", -1), " <- wrapped past the start");
console.log("  place is remembered:", shotIndex.get("x") === 1);
