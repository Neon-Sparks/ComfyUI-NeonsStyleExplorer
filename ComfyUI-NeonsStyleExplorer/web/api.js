import { api } from "../../scripts/api.js";
import { NEONS_STYLE_INDEX } from "./style_index.js";

export const NODE_TYPES = new Set(["NeonsStyleExplorer", "NeonsStyleExplorerEncode"]);
export const RANDOM = "\u{1F3B2} Random";

export const state = {
    // bundled snapshot so the combos are populated on first paint; the live
    // catalog replaces it as soon as /neons_style/catalog answers
    catalog: NEONS_STYLE_INDEX,
    previews: {},
    tags: [],
    lastImages: [],
    lastPromptId: "",
    // named preview catalogs: one per model or project
    catalogs: { active: "default", name: "Default", items: [] },
    // prompt_id -> { images: [], nodes: Map(nodeId -> {style, mode, prompt}) }
    // ComfyUI can run several prompts at once, so an image may only ever be
    // paired with the style reported by its OWN prompt.
    runs: new Map(),
    favourites: [],
    recents: [],
    ready: false,
};

async function parse(res) {
    if (!res) return null;
    if (typeof res.json === "function") {
        try {
            return await res.json();
        } catch (err) { /* fall through */ }
    }
    try {
        const text = typeof res.text === "function" ? await res.text() : String(res);
        const start = text.indexOf("{");
        const end = text.lastIndexOf("}");
        return start >= 0 && end > start ? JSON.parse(text.slice(start, end + 1)) : null;
    } catch (err) {
        return null;
    }
}

async function call(path, body) {
    try {
        const init = body
            ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }
            : undefined;
        return (await parse(await api.fetchApi(path, init))) || null;
    } catch (err) {
        console.warn(`Neons Style Explorer: ${path} failed`, err);
        return null;
    }
}

export async function loadCatalog() {
    const data = await call("/neons_style/catalog");
    if (data?.styles) {
        state.catalog = data;
        state.favourites = data.favourites || [];
        state.recents = data.recents || [];
        state.ready = true;
    }
    return state.catalog;
}

export function isFavourite(name) {
    const key = String(name || "").toLowerCase();
    return state.favourites.some((item) => item.toLowerCase() === key);
}

export async function starStyle(name) {
    const result = await toggleFavourite(name);
    if (result?.favourites) state.favourites = result.favourites;
    return Boolean(result?.favourite);
}

export async function loadGallery() {
    const data = await call("/neons_style/gallery");
    state.previews = data?.previews || {};
    return state.previews;
}

export async function loadTags() {
    if (state.tags.length) return state.tags;
    const data = await call("/neons_style/tags");
    state.tags = data?.tags || [];
    return state.tags;
}

export const composeRemote = (body) => call("/neons_style/compose", body);
export const rollRemote = (body) => call("/neons_style/roll", body);

/* ---------------------------------------------- catalogs (named preview sets) */

export async function loadCatalogSets() {
    const data = await call("/neons_style/catalogs");
    if (data?.ok) state.catalogs = { active: data.active, name: data.name, items: data.items || [] };
    return state.catalogs;
}

async function catalogSetCall(path, body) {
    const data = await call(path, body);
    if (data?.ok) state.catalogs = { active: data.active, name: data.name, items: data.items || [] };
    return data;
}

export const createCatalogSet = (name) => catalogSetCall("/neons_style/catalogs/create", { name });
export const selectCatalogSet = (id) => catalogSetCall("/neons_style/catalogs/select", { id });
export const renameCatalogSet = (id, name) => catalogSetCall("/neons_style/catalogs/rename", { id, name });
export const deleteCatalogSet = (id, deleteFiles = false) =>
    catalogSetCall("/neons_style/catalogs/delete", { id, delete_files: deleteFiles });

/** Switch catalog and pull everything that belongs to it. */
export async function useCatalogSet(id) {
    await selectCatalogSet(id);
    await loadCatalog();   // favourites and recents live in the catalog
    await loadGallery();
    return state.catalogs;
}

/** Auto-gallery for a finished prompt: the server pairs the images with the
 *  style ITS record says that prompt used, so a moving dropdown cannot drift. */
export const saveRun = (promptId, images, extra = {}) =>
    call("/neons_style/gallery/save_run", {
        prompt_id: promptId || "",
        images: images || [],
        ...extra,
    });

/** The ordered style names crawl mode walks, straight from the server so the
 *  sequence matches the node's own fallback exactly. */
export async function loadCrawl(scope = "all", family = "") {
    const query = new URLSearchParams({ scope, family: family || "" });
    const data = await call(`/neons_style/crawl?${query}`);
    return Array.isArray(data?.names) ? data.names : [];
}
export const saveShot = (body) => call("/neons_style/gallery/save", body);
export const setCover = (key, file) => call("/neons_style/gallery/cover", { key, file });
export const deleteShot = (key, file) => call("/neons_style/gallery/delete", { key, file });
export const deleteStyleShots = (style) => call("/neons_style/gallery/delete", { style });
export const deleteFamilyShots = (family) => call("/neons_style/gallery/delete_family", { family });
export const saveCustom = (body) => call("/neons_style/custom", body);
export const saveOverride = (body) => call("/neons_style/override", body);
export const revertOverride = (name) => call("/neons_style/override/delete", { name });
export const hideStyle = (name) => call("/neons_style/style/hide", { name });
export const loadHidden = () => call("/neons_style/hidden");
export const restoreStyle = (name) => call("/neons_style/style/restore", { name });
// a bodyless call() is a GET, and these routes are POST-only — send {} so the
// method is right (this is why "Restore all" silently did nothing)
export const restoreAllStyles = () => call("/neons_style/style/restore_all", {});
export const loadFavourites = () => call("/neons_style/favourites");
export const toggleFavourite = (name) => call("/neons_style/favourite", { name, toggle: true });
export const pushRecent = (name) => call("/neons_style/recent", { name });
export const clearRecents = () => call("/neons_style/recent", { clear: true });
export const deleteAllShots = () => call("/neons_style/gallery/delete_family", { family: "" });
export const exportStyles = () => call("/neons_style/export");
export const importStyles = (styles) => call("/neons_style/import", { styles });

export function entryOf(name) {
    if (!name || name === "None" || name === RANDOM) return null;
    return state.catalog.by_name?.[name] || null;
}

export function keyOf(name) {
    const entry = entryOf(name);
    return String(entry?.id || name || "")
        .replace(/[^A-Za-z0-9]+/g, "_")
        .replace(/^_+|_+$/g, "")
        .slice(0, 140);
}

export function shotsOf(name) {
    return state.previews[keyOf(name)] || null;
}

export function shotUrl(name, file) {
    const suffix = file ? `&file=${encodeURIComponent(file)}` : "";
    return `/neons_style/shot?key=${encodeURIComponent(keyOf(name))}${suffix}`;
}

export function namesOf(axis) {
    if (axis === "format") return state.catalog.formats || [];
    if (axis === "finish") return state.catalog.finishes || [];
    return state.catalog.styles || [];
}
