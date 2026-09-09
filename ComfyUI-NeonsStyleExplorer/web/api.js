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
    lastError: null,
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

/**
 * Every request goes through here. On failure it records the status in
 * state.lastError so the UI can say something useful: a 404 means the running
 * ComfyUI has not loaded this version's routes (the browser picked up the new
 * front-end files, but routes only register when the server restarts), which is
 * a very different problem from a write error.
 */
async function call(path, body) {
    state.lastError = null;
    try {
        const init = body
            ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }
            : undefined;
        const response = await api.fetchApi(path, init);
        if (response && response.ok === false) {
            state.lastError = { path, status: response.status };
            console.warn(`Neons Style Explorer: ${path} → HTTP ${response.status}`);
            return null;
        }
        return (await parse(response)) || null;
    } catch (err) {
        state.lastError = { path, status: 0, message: String(err?.message || err) };
        console.warn(`Neons Style Explorer: ${path} failed`, err);
        return null;
    }
}

/** A sentence for the last failure, aimed at the person who has to fix it. */
export function lastErrorText(fallback = "that did not work") {
    const error = state.lastError;
    if (!error) return fallback;
    if (error.status === 404 || error.status === 405) {
        return "restart ComfyUI — the running server has not loaded this version";
    }
    if (error.status === 0) return `no reply from the server (${error.message})`;
    return `server error ${error.status} — see the ComfyUI console`;
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

/** The event any open view listens to so it can redraw when previews change. */
export const GALLERY_EVENT = "ns:gallery";

export async function loadGallery() {
    const data = await call("/neons_style/gallery");
    state.previews = data?.previews || {};
    // Announce it: the catalog browser used to read the gallery once when it
    // opened, so previews saved during a crawl only appeared after closing and
    // reopening it.
    try {
        window.dispatchEvent(new CustomEvent(GALLERY_EVENT, { detail: { previews: state.previews } }));
    } catch (err) {
        /* no window (or no CustomEvent): nothing is listening anyway */
    }
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

/* ------------------------------------------------------------- families */

export const loadFamilies = () => call("/neons_style/families");
export const renameFamily = (old, next) =>
    call("/neons_style/families/rename", { old, new: next });
export const deleteFamily = (name) => call("/neons_style/families/delete", { name });

/** True when a family was made by the user rather than shipped with the node. */
export function isCustomFamily(name) {
    const shipped = state.catalog.shipped_families || [];
    return Boolean(name) && !shipped.includes(name);
}

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
export const addCatalogPrompt = (id, text) =>
    catalogSetCall("/neons_style/catalogs/prompt", { id, text });
export const deleteCatalogPrompt = (id, text) =>
    catalogSetCall("/neons_style/catalogs/prompt", { id, text, delete: true });

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
