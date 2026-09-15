/**
 * Neons Model Explorer — the checkpoint loader with its gallery attached.
 *
 * The same interface as the LoRA explorer (explorer.js) pointed at your
 * checkpoints folder. Its per-file text is notes rather than trigger words: a
 * checkpoint wants a reminder of the sampler and CFG it likes, not words in
 * the prompt. There is no roll — a checkpoint is a choice, not a variation.
 */
import { createExplorer } from "./explorer.js";

createExplorer({
    node: "NeonsModelExplorer",
    extension: "ModelExplorer",
    kind: "model",
    route: "/neons_model",
    key: "model",
    picker: "ckpt_name",
    listKey: "models",
    textField: "notes",
    textLabel: "notes",
    textPlaceholder: "sampler, CFG, resolution — whatever this checkpoint likes",
    label: "Neons Model Explorer",
    singular: "checkpoint",
    plural: "checkpoints",
    folder: "checkpoints",
    pick: "Pick a checkpoint",
    pickFirst: "pick a checkpoint first",
    strengthMode: false,
});
