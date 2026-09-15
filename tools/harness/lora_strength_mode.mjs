// Which strength controls are live in each mode?
const widgets = ["strength_model", "strength_clip", "random_low", "random_high", "roll_seed"];
const sync = (rolling) => {
    const off = {
        strength_model: rolling, strength_clip: rolling,
        random_low: !rolling, random_high: !rolling, roll_seed: !rolling,
    };
    return widgets.filter((w) => !off[w]);
};
console.log("  random_roll off -> live:", sync(false).join(", "));
console.log("  random_roll on  -> live:", sync(true).join(", "));
console.log("  never both strength and range:",
    sync(false).includes("strength_model") !== sync(false).includes("random_low"));
