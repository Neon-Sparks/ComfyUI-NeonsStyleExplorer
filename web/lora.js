/**
 * Neons LoRA Explorer — the LoRA loader with its gallery attached.
 *
 * The interface lives in explorer.js, shared with the checkpoint explorer.
 * Everything specific to LoRAs is in the configuration below: the route
 * prefix, the payload key, the words on screen, and the fact that this node
 * has a random roll whose range takes over from the strength sliders.
 */
import { createExplorer } from "./explorer.js";

createExplorer({
    node: "NeonsLoraExplorer",
    extension: "LoraExplorer",
    kind: "lora",
    route: "/neons_lora",
    key: "lora",                 // the payload field the routes read
    picker: "lora",              // the widget holding the choice
    listKey: "loras",            // what the catalog route calls its list
    textField: "triggers",
    textLabel: "triggers",
    textPlaceholder: "words this LoRA wants in the prompt",
    label: "Neons LoRA Explorer",
    singular: "LoRA",
    plural: "LoRAs",
    folder: "loras",
    pick: "Pick a LoRA",
    pickFirst: "pick a LoRA first",
    strengthMode: true,          // random_roll dims the strength sliders
});
