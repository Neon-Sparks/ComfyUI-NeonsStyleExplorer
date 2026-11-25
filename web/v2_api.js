/**
 * Neons Style Explorer 2 — data layer shared by the node panel and the browser.
 *
 * The catalog is fetched once and kept; the server answers later requests with
 * "not modified" until a style file changes. The user's own state (favourites,
 * collections, which styles have a preview) is small and fetched fresh.
 */
import { api } from "../../scripts/api.js";

export const NODE_TYPES = new Set(["NeonsStyleExplorer2", "NeonsStyleExplorer2Encode"]);
export const MOD_KINDS = ["lighting", "palette", "camera", "mood", "format", "finish"];
export const MAX_PICKS = 3;

export const store = {
    signature: "",
    cats: [],
    traits: [],
    styles: [],
    byId: new Map(),
    byName: new Map(),
    mods: {},
    favourites: new Set(),
    recents: [],
    collections: {},
    previews: {},
    latestImage: null,
    loading: null,
    listeners: new Set(),
};

/** Build an element. Text always goes in as text, never as markup. */
export function h(tag, props, ...kids) {
    const el = document.createElement(tag);
    for (const [key, value] of Object.entries(props || {})) {
        if (value === null || value === undefined || value === false) continue;
        if (key === "class") el.className = value;
        else if (key === "text") el.textContent = value;
        else if (key === "style") el.style.cssText = value;
        else if (key.startsWith("on")) el.addEventListener(key.slice(2), value);
        else if (key in el && key !== "list") el[key] = value;
        else el.setAttribute(key, value);
    }
    for (const kid of kids.flat()) {
        if (kid === null || kid === undefined || kid === false) continue;
        el.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
    }
    return el;
}

export async function post(path, body) {
    try {
        const response = await api.fetchApi(path, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body || {}),
        });
        try {
            return await response.json();
        } catch (error) {
            return { ok: false, error: `the server answered ${response.status}` };
        }
    } catch (error) {
        return { ok: false, error: "could not reach ComfyUI" };
    }
}

function decode(data) {
    store.signature = data.signature;
    store.cats = data.cats || [];
    store.traits = data.traits || [];
    store.mods = data.mods || {};
    store.byId = new Map();
    store.byName = new Map();
    store.styles = (data.styles || []).map((row) => {
        const cat = store.cats[row[2]];
        const style = {
            id: row[0],
            name: row[1],
            cat: row[2],
            catId: cat ? cat.id : "",
            catName: cat ? cat.name : "",
            sub: cat && row[3] >= 0 ? cat.subs[row[3]] : "",
            lead: row[4],
            parts: row[5] || [],
            tags: row[6] || [],
            traits: row[7] || [],
        };
        // everything search looks through, lower-cased once
        style.hay = [style.name, style.lead, style.parts.join(" "), style.tags.join(" "),
            style.catName, style.sub].join(" ").toLowerCase();
        store.byId.set(style.id, style);
        store.byName.set(style.name.toLowerCase(), style);
        return style;
    });
}

export async function loadState() {
    try {
        const response = await api.fetchApi("/neons_style2/state", { cache: "no-store" });
        const data = await response.json();
        store.favourites = new Set(data.favourites || []);
        store.recents = data.recents || [];
        store.collections = data.collections || {};
        store.previews = data.previews || {};
    } catch (error) {
        // keep whatever we had; the browser still works without user state
    }
    announce();
}

export function loadCatalog() {
    if (store.loading) return store.loading;
    store.loading = (async () => {
        const response = await api.fetchApi("/neons_style2/catalog");
        const data = await response.json();
        if (data.signature !== store.signature) decode(data);
        await loadState();
        return store;
    })().finally(() => {
        store.loading = null;
    });
    return store.loading;
}

export function onChange(listener) {
    store.listeners.add(listener);
    return () => store.listeners.delete(listener);
}

export function announce() {
    store.listeners.forEach((listener) => {
        try {
            listener();
        } catch (error) {
            console.error("[Neons Style Explorer 2]", error);
        }
    });
}

export function resolve(token) {
    const text = String(token || "").trim();
    return store.byId.get(text) || store.byName.get(text.toLowerCase()) || null;
}

/** The styles box as a list: [{ token, weight }]. Mirrors explorer2.parse. */
export function parsePicks(text) {
    const picks = [];
    for (const raw of String(text || "").split(/[,\n|]/)) {
        let token = raw.replace(/\s+/g, " ").trim();
        if (!token) continue;
        let weight = 1;
        const found = token.match(/^(.*?)\s*:\s*([0-9]*\.?[0-9]+)$/);
        if (found) {
            token = found[1].trim();
            weight = Math.max(0.1, Math.min(2, parseFloat(found[2]) || 1));
        }
        if (token) picks.push({ token, weight });
        if (picks.length >= MAX_PICKS) break;
    }
    return picks;
}

export function formatPicks(picks) {
    return picks.map((pick) => (Math.abs(pick.weight - 1) > 0.001
        ? `${pick.token}:${Number(pick.weight.toFixed(2))}` : pick.token)).join(", ");
}

export function previewUrl(id, size) {
    const stamp = store.previews[id];
    if (!stamp) return "";
    const query = new URLSearchParams({ id, v: String(stamp) });
    if (size) query.set("size", String(size));
    return api.apiURL(`/neons_style2/preview?${query}`);
}

/** A quiet colour per category, so a style with no preview is still placeable at a glance. */
export function tint(style, lightness = 24) {
    const total = Math.max(1, store.cats.length);
    const hue = Math.round((((style?.cat ?? 0) + 0.5) / total) * 360);
    return `hsl(${hue} 18% ${lightness}%)`;
}

export async function toggleFavourite(id) {
    const reply = await post("/neons_style2/favourite", { id });
    if (reply.ok) {
        if (reply.on) store.favourites.add(id);
        else store.favourites.delete(id);
        announce();
    }
    return reply;
}

export async function savePreview(id, image, onlyIfMissing = false) {
    if (!id || !image?.filename) return { ok: false, error: "no image to save yet" };
    const reply = await post("/neons_style2/preview/save", {
        id,
        filename: image.filename,
        subfolder: image.subfolder || "",
        type: image.type || "output",
        only_if_missing: onlyIfMissing,
    });
    if (reply.ok && reply.stamp) {
        store.previews[id] = reply.stamp;
        announce();
    }
    return reply;
}

export async function deletePreview(id) {
    const reply = await post("/neons_style2/preview/delete", { id });
    if (reply.ok) {
        delete store.previews[id];
        announce();
    }
    return reply;
}
