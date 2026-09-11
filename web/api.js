import { api } from "../../scripts/api.js";

export const NODE_TYPES = new Set(["NeonsStyleExplorer", "NeonsStyleExplorerEncode"]);
export const RANDOM = "\u{1F3B2} Random";

/** An empty catalog: the shape everything reads, with nothing in it yet. */
const EMPTY_CATALOG = {
    schema: 1, styles: [], formats: [], finishes: [], families: {},
    family_order: [], shipped_families: [], imported_families: [],
    by_name: {}, favourites: [], recents: [], coverage: {}, count: 0,
};

export const state = {
    // The bundled snapshot is 1.6 MB of JavaScript and used to be parsed on
    // every page load just to have something before the server answered. It is
    // now only imported if /neons_style/catalog cannot be reached.
    catalog: EMPTY_CATALOG,
    previews: {},
    tags: [],
    lastImages: [],
    lastPromptId: "",
    lastError: null,
    gallerySig: "",
    ready: false,
    snapshotTried: false,
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

/**
 * Index every name a style answers to.
 *
 * A style keeps its id through a rename and its old name becomes an alias, so
 * the server files previews under the id either way. The browser only indexed
 * the CURRENT name, so a node still holding the old one fell back to slugging
 * that name — looking for previews under a key nothing writes, which made a
 * saved image seem to land on the wrong style.
 */
function indexAliases(catalog) {
    const byAlias = {};
    for (const entry of Object.values(catalog?.by_name || {})) {
        if (!entry?.name) continue;
        byAlias[entry.name.toLowerCase()] = entry;
        for (const alias of entry.aliases || []) {
            if (alias && !byAlias[alias.toLowerCase()]) byAlias[alias.toLowerCase()] = entry;
        }
    }
    catalog.by_alias = byAlias;
    return catalog;
}

export async function loadCatalog() {
    const data = await call("/neons_style/catalog");
    if (data?.styles) {
        state.catalog = indexAliases(data);
        state.favourites = data.favourites || [];
        state.recents = data.recents || [];
        state.ready = true;
        return state.catalog;
    }
    // The server did not answer — an old backend behind a refreshed front end,
    // or a restart in progress. Fall back to the snapshot bundled with the
    // extension, imported only now so its weight costs nothing in the normal
    // case.
    if (!state.ready && !state.snapshotTried) {
        state.snapshotTried = true;
        try {
            const module = await import("./style_index.js");
            if (module?.NEONS_STYLE_INDEX?.styles) {
                state.catalog = indexAliases(module.NEONS_STYLE_INDEX);
                console.warn("Neons Style Explorer: using the bundled catalog snapshot — restart ComfyUI");
            }
        } catch (err) {
            console.warn("Neons Style Explorer: no catalog available", err);
        }
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

/* --------------------------------------------- one entry, in full, on demand */

const detailCache = new Map();

/**
 * The clause and avoid terms for one entry.
 *
 * The catalog payload carries a light index — names, families, tags — because
 * shipping every clause with it meant moving nearly two megabytes on each of
 * the eighteen paths that reload the catalog. The long text is wanted one entry
 * at a time, so it is fetched and cached here.
 */
export async function entryDetail(name) {
    if (!name || name === "None" || name === RANDOM) return null;
    if (detailCache.has(name)) return detailCache.get(name);
    const data = await call(`/neons_style/entry?name=${encodeURIComponent(name)}`);
    const entry = data?.entry || null;
    if (entry) detailCache.set(name, entry);
    return entry;
}

/** Drop cached detail after an edit, so the next read sees the new text. */
export function forgetDetail(name) {
    if (name) detailCache.delete(name);
    else detailCache.clear();
}

/**
 * Splice one saved preview into the local gallery state.
 *
 * The alternative is refetching the whole manifest after every save, which
 * grows with coverage — a crawl a thousand previews in was re-downloading a
 * quarter of a megabyte per image, then redrawing on it.
 */
export function patchPreview(key, record) {
    if (!key || !record) return;
    state.previews = { ...state.previews, [key]: record };
    state.gallerySig = `${Object.keys(state.previews).length}:${JSON.stringify(state.previews).length}`;
    try {
        window.dispatchEvent(new CustomEvent(GALLERY_EVENT, { detail: { key, record } }));
    } catch (err) {
        /* nothing listening */
    }
}

/** Cheap "has the gallery changed?" check, for polling. */
export async function gallerySignature() {
    const data = await call("/neons_style/gallery/signature");
    return data?.signature || "";
}

export async function loadGallery() {
    const data = await call("/neons_style/gallery");
    const previews = data?.previews || {};
    // Only announce a real change: the browser rebuilds its grid on this event,
    // and an unchanged manifest used to trigger that rebuild anyway — six times
    // a minute while the poller ran.
    const before = state.gallerySig;
    state.gallerySig = `${Object.keys(previews).length}:${JSON.stringify(previews).length}`;
    state.previews = previews;
    if (before === state.gallerySig) return state.previews;
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
/**
 * Download the catalog as a shareable bundle.
 *
 * Fetched rather than linked: a plain <a download> gave no feedback and no way
 * to tell whether it had worked, and it bypasses api.fetchApi, which is what
 * knows the server's base path. Streaming also means progress can be reported,
 * and where the browser supports it the user picks the folder.
 */
export async function exportCatalogBundle(id, onProgress) {
    const query = new URLSearchParams({ id: id || "" });
    state.lastError = null;
    let response;
    try {
        response = await api.fetchApi(`/neons_style/catalogs/export?${query}`);
    } catch (err) {
        state.lastError = { path: "/neons_style/catalogs/export", status: 0, message: String(err) };
        return null;
    }
    if (!response || response.ok === false) {
        state.lastError = { path: "/neons_style/catalogs/export", status: response?.status || 0 };
        return null;
    }

    const disposition = response.headers.get("Content-Disposition") || "";
    // no regex here: a quote inside one trips the source checker, and this is
    // clearer anyway
    const QUOTE = String.fromCharCode(34);
    const after = disposition.split("filename=")[1] || "";
    const filename = after.split(";")[0].split(QUOTE).join("").trim() || "neons-catalog.zip";
    const total = Number(response.headers.get("Content-Length")) || 0;

    let blob;
    const reader = response.body?.getReader?.();
    if (reader) {
        const chunks = [];
        let received = 0;
        for (;;) {
            const { done, value } = await reader.read();
            if (done) break;
            chunks.push(value);
            received += value.length;
            onProgress?.(received, total);
        }
        blob = new Blob(chunks, { type: "application/zip" });
    } else {
        blob = await response.blob();
        onProgress?.(blob.size, blob.size);
    }

    // Chrome and Edge can ask where to put it; everything else goes to the
    // browser's download folder
    if (typeof window.showSaveFilePicker === "function") {
        try {
            const handle = await window.showSaveFilePicker({
                suggestedName: filename,
                types: [{ description: "Neons catalog bundle", accept: { "application/zip": [".zip"] } }],
            });
            const writable = await handle.createWritable();
            await writable.write(blob);
            await writable.close();
            return { filename: handle.name || filename, bytes: blob.size, chosen: true };
        } catch (err) {
            if (err?.name === "AbortError") return { cancelled: true };
            // fall through to a normal download
        }
    }

    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
    return { filename, bytes: blob.size, chosen: false };
}

/** Unpack someone else's bundle into a new catalog. */
export async function importCatalogBundle(file, name = "") {
    const form = new FormData();
    form.append("bundle", file, file.name || "bundle.zip");
    if (name) form.append("name", name);
    state.lastError = null;
    try {
        const response = await api.fetchApi("/neons_style/catalogs/import", { method: "POST", body: form });
        if (response && response.ok === false) {
            state.lastError = { path: "/neons_style/catalogs/import", status: response.status };
            return null;
        }
        const data = await response.json();
        if (data?.ok) state.catalogs = { active: data.active, name: data.name, items: data.items || [] };
        return data;
    } catch (err) {
        state.lastError = { path: "/neons_style/catalogs/import", status: 0, message: String(err?.message || err) };
        return null;
    }
}

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
export async function loadCrawl(scope = "all", family = "", source = "main") {
    const query = new URLSearchParams({ scope, family: family || "", source });
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
export const toggleFavourite = (name) => call("/neons_style/favourite", { name, toggle: true });
export const clearRecents = () => call("/neons_style/recent", { clear: true });
export const deleteAllShots = () => call("/neons_style/gallery/delete_family", { family: "" });
export const exportStyles = () => call("/neons_style/export");
export const importStyles = (styles) => call("/neons_style/import", { styles });

export function entryOf(name) {
    if (!name || name === "None" || name === RANDOM) return null;
    return state.catalog.by_name?.[name]
        || state.catalog.by_alias?.[String(name).toLowerCase()]
        || null;
}

export function keyOf(name) {
    const entry = entryOf(name);
    if (!entry && name && name !== "None" && name !== RANDOM && state.ready) {
        // a key derived from a name the catalog does not know cannot match what
        // the server writes; say so rather than quietly filing it elsewhere
        console.warn(`Neons Style Explorer: '${name}' is not in the catalog — `
            + "its previews cannot be matched");
    }
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

/**
 * Which style slot can hold this entry.
 *
 * Each dropdown carries one source, so a name put in the wrong slot is not in
 * that slot's option list — it displays until the next sync and is then reset
 * to None, which looks exactly like the preview vanishing on its own.
 */
export function slotFor(name) {
    const entry = entryOf(name);
    if (!entry) return "style";
    if ((state.catalog.imported_families || []).includes(entry.family)) return "extra_style";
    if ((entry.source || "shipped") === "custom") return "custom_style";
    return "style";
}

/** The names one of the node's style dropdowns carries. */
export function sourceNames(source) {
    const imported = state.catalog.imported_families || [];
    const all = state.catalog.styles || [];
    if (source === "extra") {
        return all.filter((name) => imported.includes(entryOf(name)?.family));
    }
    if (source === "custom") {
        return all.filter((name) => (entryOf(name)?.source || "shipped") === "custom");
    }
    return all.filter((name) => {
        const entry = entryOf(name);
        return !imported.includes(entry?.family) && (entry?.source || "shipped") !== "custom";
    });
}

export function namesOf(axis) {
    if (axis === "format") return state.catalog.formats || [];
    if (axis === "finish") return state.catalog.finishes || [];
    return state.catalog.styles || [];
}
