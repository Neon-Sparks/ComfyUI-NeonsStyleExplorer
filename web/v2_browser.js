/**
 * Neons Style Explorer 2 — the style browser.
 *
 * Three columns: where to look (categories, favourites, collections), the
 * styles themselves, and the one you have selected with the blend you are
 * building. The grid only ever holds the cards that are on screen, so it opens
 * and scrolls the same with three thousand styles as with thirty.
 */
import { ensureCss } from "./v2_css.js";
import { MAX_PICKS, deletePreview, formatPicks, h, loadCatalog, loadState, onChange, parsePicks,
    post, previewUrl, resolve, savePreview, store, tint, toggleFavourite } from "./v2_api.js";

const MEMORY = "ns2.browser";
const GAP = 10;
const CAPTION = 32;
const VIEWS = [["all", "All styles"], ["fav", "Favourites"], ["recent", "Recently used"],
    ["preview", "With a preview"], ["missing", "No preview yet"]];
let current = null;

function remember(state) {
    try {
        localStorage.setItem(MEMORY, JSON.stringify({
            view: state.view, cat: state.cat, sub: state.sub, traits: [...state.traits],
            sort: state.sort, size: state.size, query: state.query,
        }));
    } catch (error) {
        // private browsing: the browser simply opens fresh next time
    }
}

function recall() {
    try {
        const saved = JSON.parse(localStorage.getItem(MEMORY) || "{}");
        return saved && typeof saved === "object" ? saved : {};
    } catch (error) {
        return {};
    }
}

export function openBrowser(options) {
    if (current) return;
    ensureCss();
    const saved = recall();
    const state = {
        view: typeof saved.view === "string" ? saved.view : "all",
        cat: typeof saved.cat === "string" ? saved.cat : "",
        sub: typeof saved.sub === "string" ? saved.sub : "",
        traits: new Set(Array.isArray(saved.traits) ? saved.traits : []),
        sort: ["category", "name", "preview"].includes(saved.sort) ? saved.sort : "category",
        size: Math.max(130, Math.min(320, Number(saved.size) || 190)),
        query: typeof saved.query === "string" ? saved.query : "",
        selected: "",
        tray: parsePicks(options.value),
        list: [],
        cols: 1,
        cardW: 190,
        cardH: 222,
    };
    const rendered = new Map();
    let composeTimer = 0;
    let frame = 0;

    /* ------------------------------------------------------------ shell */
    const search = h("input", { type: "search", value: state.query,
        placeholder: "Search name, description, tag or category   ( / )",
        title: "Every word you type must appear somewhere in the style." });
    const count = h("span", { class: "ns2-count" });
    const sort = h("select", { title: "Order of the styles" },
        h("option", { value: "category", text: "By category" }),
        h("option", { value: "name", text: "A to Z" }),
        h("option", { value: "preview", text: "Previews first" }));
    sort.value = state.sort;
    const sizer = h("input", { type: "range", min: 130, max: 320, step: 10, value: state.size,
        title: "Card size" });
    const side = h("div", { class: "ns2-side" });
    const traits = h("div", { class: "ns2-traits" });
    const spacer = h("div", { class: "ns2-spacer" });
    const grid = h("div", { class: "ns2-grid", tabIndex: 0 }, spacer);
    const detail = h("div", { class: "ns2-detail" });
    const body = h("div", { class: "ns2-body", style: "position:relative" }, side,
        h("div", { class: "ns2-main" }, traits, grid), detail);
    const windowEl = h("div", { class: "ns2-window", role: "dialog", "aria-label": "Style browser" },
        h("div", { class: "ns2-top" },
            h("h2", { text: "Style Explorer 2" }), search, count,
            h("label", {}, "Order", sort), h("label", {}, "Size", sizer),
            h("button", { text: "New style", title: "Write a style of your own",
                onclick: () => openForm(null) }),
            h("button", { text: "Close", title: "Close without changing the node (Esc)",
                onclick: () => close() })),
        body);
    const overlay = h("div", { class: "ns2 ns2-overlay" }, windowEl);

    function close() {
        remember(state);
        stopWatching();
        cancelAnimationFrame(frame);
        clearTimeout(composeTimer);
        document.removeEventListener("keydown", onKey, true);
        resizer?.disconnect();
        overlay.remove();
        current = null;
    }

    function applyAndClose() {
        options.apply(formatPicks(state.tray));
        close();
    }

    /* ---------------------------------------------------------- filter */
    function inTray(style) {
        return state.tray.findIndex((pick) => !pick.token.startsWith("@")
            && resolve(pick.token)?.id === style.id);
    }

    function filter() {
        const words = state.query.toLowerCase().split(/\s+/).filter(Boolean);
        const wanted = [...state.traits].map((name) => store.traits.indexOf(name))
            .filter((index) => index >= 0);
        const recent = new Map(store.recents.map((id, index) => [id, index]));
        let scope = null;
        if (state.view.startsWith("col:")) {
            scope = new Set(store.collections[state.view.slice(4)] || []);
        }
        const list = store.styles.filter((style) => {
            if (state.view === "fav" && !store.favourites.has(style.id)) return false;
            if (state.view === "recent" && !recent.has(style.id)) return false;
            if (state.view === "preview" && !store.previews[style.id]) return false;
            if (state.view === "missing" && store.previews[style.id]) return false;
            if (scope && !scope.has(style.id)) return false;
            if (state.view === "cat") {
                if (style.catId !== state.cat) return false;
                if (state.sub && style.sub !== state.sub) return false;
            }
            for (const index of wanted) if (!style.traits.includes(index)) return false;
            for (const word of words) if (!style.hay.includes(word)) return false;
            return true;
        });
        if (state.view === "recent") {
            list.sort((a, b) => recent.get(a.id) - recent.get(b.id));
        } else if (state.sort === "name") {
            list.sort((a, b) => a.name.localeCompare(b.name));
        } else if (state.sort === "preview") {
            list.sort((a, b) => (store.previews[b.id] ? 1 : 0) - (store.previews[a.id] ? 1 : 0));
        }
        state.list = list;
        count.textContent = `${list.length.toLocaleString()} of ${store.styles.length.toLocaleString()}`;
        if (!list.some((style) => style.id === state.selected)) state.selected = list[0]?.id || "";
    }

    /* ------------------------------------------------------------ grid */
    function measure() {
        const width = Math.max(120, grid.clientWidth - 2 * GAP);
        state.cols = Math.max(1, Math.floor((width + GAP) / (state.size + GAP)));
        state.cardW = Math.floor((width - GAP * (state.cols - 1)) / state.cols);
        state.cardH = state.cardW + CAPTION;
        const rows = Math.ceil(state.list.length / state.cols);
        spacer.style.height = `${rows * (state.cardH + GAP) + GAP}px`;
    }

    function makeCard(style, index) {
        const pic = h("div", { class: "pic", style: `background:${tint(style)}` });
        const url = previewUrl(style.id, state.cardW > 256 ? 384 : 256);
        if (url) pic.append(h("img", { src: url, alt: "", loading: "lazy", draggable: false }));
        else pic.append(h("div", { class: "ph", text: style.lead }));
        const fav = store.favourites.has(style.id);
        pic.append(h("button", { class: `star${fav ? " on" : ""}`, text: "★",
            title: fav ? "Remove from favourites" : "Add to favourites",
            onclick: (event) => {
                event.stopPropagation();
                toggleFavourite(style.id);
            } }));
        const slot = inTray(style);
        if (slot >= 0) pic.append(h("span", { class: "mark", text: String(slot + 1), title: "In your blend" }));
        const row = Math.floor(index / state.cols);
        const col = index % state.cols;
        return h("div", {
            class: `ns2-card${style.id === state.selected ? " sel" : ""}`,
            style: `left:${GAP + col * (state.cardW + GAP)}px;top:${GAP + row * (state.cardH + GAP)}px;`
                + `width:${state.cardW}px;height:${state.cardH}px`,
            title: `${style.name}\n${style.catName} › ${style.sub}`,
            onclick: () => select(style.id),
            ondblclick: () => use(style),
        }, pic, h("div", { class: "cap" }, h("b", { text: style.name })));
    }

    function drawGrid(force) {
        if (force) {
            rendered.clear();
            spacer.replaceChildren();
        }
        if (!state.list.length) {
            spacer.style.height = "auto";
            spacer.replaceChildren(h("div", { class: "ns2-empty",
                text: store.styles.length ? "Nothing matches. Clear the search or the filters."
                    : "Loading the catalog…" }));
            rendered.clear();
            return;
        }
        const step = state.cardH + GAP;
        const first = Math.max(0, Math.floor(grid.scrollTop / step) - 2) * state.cols;
        const last = Math.min(state.list.length,
            (Math.ceil((grid.scrollTop + grid.clientHeight) / step) + 2) * state.cols);
        const keep = new Set();
        for (let index = first; index < last; index += 1) {
            const style = state.list[index];
            keep.add(style.id);
            if (!rendered.has(style.id)) {
                const element = makeCard(style, index);
                rendered.set(style.id, element);
                spacer.append(element);
            }
        }
        for (const [id, element] of rendered) {
            if (!keep.has(id)) {
                element.remove();
                rendered.delete(id);
            }
        }
    }

    function redraw() {
        filter();
        measure();
        drawGrid(true);
        drawSide();
        drawTraits();
        drawDetail();
    }

    function select(id, reveal) {
        state.selected = id;
        for (const [key, element] of rendered) element.classList.toggle("sel", key === id);
        if (reveal) {
            const index = state.list.findIndex((style) => style.id === id);
            if (index >= 0) {
                const top = GAP + Math.floor(index / state.cols) * (state.cardH + GAP);
                if (top < grid.scrollTop) grid.scrollTop = top - GAP;
                else if (top + state.cardH > grid.scrollTop + grid.clientHeight) {
                    grid.scrollTop = top + state.cardH + GAP - grid.clientHeight;
                }
                drawGrid();
                for (const [key, element] of rendered) element.classList.toggle("sel", key === id);
            }
        }
        drawDetail();
    }

    /* ------------------------------------------------------------ side */
    function row(label, active, total, onclick, child) {
        return h("button", { class: `ns2-row${child ? " child" : ""}${active ? " on" : ""}`, onclick },
            h("span", { text: label }), total === null ? null : h("span", { class: "n", text: String(total) }));
    }

    function go(view, cat = "", sub = "") {
        state.view = view;
        state.cat = cat;
        state.sub = sub;
        grid.scrollTop = 0;
        redraw();
    }

    function drawSide() {
        const kids = [];
        const totals = { all: store.styles.length, fav: store.favourites.size, recent: store.recents.length,
            preview: Object.keys(store.previews).length,
            missing: store.styles.length - Object.keys(store.previews).length };
        for (const [view, label] of VIEWS) {
            kids.push(row(label, state.view === view, totals[view], () => go(view)));
        }
        kids.push(h("h3", { text: "Collections" }));
        for (const name of Object.keys(store.collections).sort((a, b) => a.localeCompare(b))) {
            kids.push(row(name, state.view === `col:${name}`, store.collections[name].length,
                () => go(`col:${name}`)));
        }
        kids.push(row("+ New collection", false, null, () => newCollection(null)));
        if (state.view.startsWith("col:")) {
            const name = state.view.slice(4);
            kids.push(h("div", { class: "ns2-actions", style: "padding:4px 8px" },
                h("button", { text: "Rename", onclick: async () => {
                    const next = prompt("New name for the collection", name);
                    if (!next || next === name) return;
                    const reply = await post("/neons_style2/collection", { name, rename: next });
                    if (!reply.ok) return alert(reply.error);
                    await loadState();
                    go(`col:${Object.keys(store.collections).find(
                        (key) => key.toLowerCase() === next.trim().toLowerCase()) || name}`);
                } }),
                h("button", { text: "Delete", onclick: async () => {
                    if (!confirm(`Delete the collection "${name}"? Its styles are not deleted.`)) return;
                    await post("/neons_style2/collection", { name, delete: true });
                    await loadState();
                    go("all");
                } })));
        }
        kids.push(h("h3", { text: "Categories" }));
        const perCat = new Map();
        const perSub = new Map();
        for (const style of store.styles) {
            perCat.set(style.catId, (perCat.get(style.catId) || 0) + 1);
            const key = `${style.catId}/${style.sub}`;
            perSub.set(key, (perSub.get(key) || 0) + 1);
        }
        for (const cat of store.cats) {
            const open = state.view === "cat" && state.cat === cat.id;
            kids.push(row(cat.name, open && !state.sub, perCat.get(cat.id) || 0, () => go("cat", cat.id)));
            if (!open) continue;
            for (const sub of cat.subs) {
                const total = perSub.get(`${cat.id}/${sub}`) || 0;
                if (!total) continue;
                kids.push(row(sub, state.sub === sub, total, () => go("cat", cat.id, sub), true));
            }
        }
        side.replaceChildren(...kids);
    }

    function drawTraits() {
        const chips = store.traits.map((name) => h("button", {
            class: `ns2-chip${state.traits.has(name) ? " on" : ""}`,
            text: name,
            "aria-pressed": state.traits.has(name) ? "true" : "false",
            onclick: () => {
                if (state.traits.has(name)) state.traits.delete(name);
                else state.traits.add(name);
                grid.scrollTop = 0;
                redraw();
            },
        }));
        if (state.traits.size) {
            chips.push(h("button", { class: "ns2-chip", text: "clear", onclick: () => {
                state.traits.clear();
                redraw();
            } }));
        }
        traits.replaceChildren(...chips);
    }

    /* ---------------------------------------------------------- detail */
    async function newCollection(style) {
        const name = prompt("Name for the new collection");
        if (!name) return;
        const reply = await post("/neons_style2/collection", style ? { name, id: style.id } : { name });
        if (!reply.ok) alert(reply.error);
        await loadState();
    }

    function collectionMenu(style, anchor) {
        body.querySelector(".ns2-menu")?.remove();
        const names = Object.keys(store.collections).sort((a, b) => a.localeCompare(b));
        const menu = h("div", { class: "ns2-menu" },
            names.map((name) => {
                const has = store.collections[name].includes(style.id);
                return h("button", { class: "ns2-row", text: `${has ? "✓ " : ""}${name}`,
                    onclick: async () => {
                        menu.remove();
                        await post("/neons_style2/collection", { name, id: style.id, on: !has });
                        await loadState();
                    } });
            }),
            h("button", { class: "ns2-row", text: "+ New collection…", onclick: () => {
                menu.remove();
                newCollection(style);
            } }));
        const box = anchor.getBoundingClientRect();
        const frameBox = body.getBoundingClientRect();
        menu.style.right = `${Math.max(8, frameBox.right - box.right)}px`;
        menu.style.top = `${box.bottom - frameBox.top + 4}px`;
        body.append(menu);
        const dismiss = (event) => {
            if (menu.contains(event.target)) return;
            menu.remove();
            document.removeEventListener("mousedown", dismiss, true);
        };
        setTimeout(() => document.addEventListener("mousedown", dismiss, true), 0);
    }

    function use(style) {
        state.tray = [{ token: style.name, weight: 1 }];
        applyAndClose();
    }

    function blend(style) {
        if (inTray(style) >= 0) return;
        if (state.tray.length >= MAX_PICKS) state.tray.pop();
        state.tray.push({ token: style.name, weight: 1 });
        drawGrid(true);
        drawDetail();
    }

    function diceChoices() {
        const out = [["@all", "any style"], ["@favourites", "one of my favourites"],
            ["@recent", "one I used recently"], ["@missing", "one with no preview"],
            ["@next", "the next one with no preview, in order"]];
        const cat = store.cats.find((entry) => entry.id === state.cat);
        if (state.view === "cat" && cat) {
            out.push([`@${cat.id}`, `any ${cat.name} style`]);
            if (state.sub) out.push([`@${cat.id}/${state.sub}`, `any ${state.sub} style`]);
        }
        for (const name of Object.keys(store.collections)) out.push([`@${name}`, `from "${name}"`]);
        return out;
    }

    function drawTray() {
        const rows = state.tray.map((pick, index) => {
            const dice = pick.token.startsWith("@");
            const found = dice ? null : resolve(pick.token);
            const value = h("span", { text: pick.weight.toFixed(1) });
            return h("div", { class: "ns2-pick" },
                h("span", { class: "nm", title: pick.token,
                    text: dice ? `Dice: ${pick.token.slice(1)}` : (found?.name || `${pick.token} (not found)`) }),
                h("input", { type: "range", min: 0.1, max: 2, step: 0.1, value: pick.weight,
                    title: "How strongly this style is blended in",
                    oninput: (event) => {
                        pick.weight = Number(event.target.value);
                        value.textContent = pick.weight.toFixed(1);
                        queueCompose();
                    } }),
                value,
                h("button", { text: "×", title: "Remove", onclick: () => {
                    state.tray.splice(index, 1);
                    drawGrid(true);
                    drawDetail();
                } }));
        });
        const dice = h("select", { title: "Let the node roll a style for this slot on every run" },
            h("option", { value: "", text: "Add a dice…" }),
            diceChoices().map(([value, label]) => h("option", { value, text: label })));
        dice.addEventListener("change", () => {
            if (!dice.value) return;
            if (state.tray.length >= MAX_PICKS) state.tray.pop();
            state.tray.push({ token: dice.value, weight: 1 });
            drawDetail();
        });
        const out = h("div", { class: "ns2-out", text: state.tray.length ? "…" : "No style: the node writes your prompt as it is." });
        state.out = out;
        queueCompose();
        return h("div", { class: "ns2-tray" },
            h("h4", { text: `On the node (${state.tray.length} of ${MAX_PICKS})` }),
            rows, dice, out,
            h("div", { class: "ns2-actions" },
                h("button", { class: "key", text: "Apply", title: "Put this selection on the node",
                    onclick: () => applyAndClose() }),
                h("button", { text: "Clear", onclick: () => {
                    state.tray = [];
                    drawGrid(true);
                    drawDetail();
                } })));
    }

    function queueCompose() {
        clearTimeout(composeTimer);
        if (!state.tray.length) return;
        composeTimer = setTimeout(async () => {
            const reply = await post("/neons_style2/compose", {
                ...(options.settings?.() || {}), styles: formatPicks(state.tray), prompt: "" });
            if (!state.out || !state.out.isConnected) return;
            state.out.textContent = reply.ok
                ? (reply.style || "(nothing to write)") + (reply.notes?.length ? `\n\n${reply.notes.join("; ")}` : "")
                : (reply.error || "Could not compose.");
        }, 160);
    }

    function drawDetail() {
        const style = store.byId.get(state.selected);
        if (!style) {
            detail.replaceChildren(h("div", { class: "hint",
                text: "Select a style to see what it writes. Double-click a card to use it straight away." }),
            drawTray());
            return;
        }
        const big = h("div", { class: "ns2-big", style: `background:${tint(style)}` });
        const url = previewUrl(style.id);
        if (url) big.append(h("img", { src: url, alt: `Preview of ${style.name}` }));
        else big.append(h("div", { class: "ph", text: "No preview yet. Generate an image with this style, then press Save preview here or on the node." }));
        const fav = store.favourites.has(style.id);
        const collections = h("button", { text: "Collections",
            onclick: () => collectionMenu(style, collections) });
        const full = state.tray.length >= MAX_PICKS;
        detail.replaceChildren(
            big,
            h("h3", { text: style.name }),
            h("div", { class: "where", text: `${style.catName} › ${style.sub || "Unfiled"}` }),
            h("div", { class: "ns2-actions" },
                h("button", { class: "key", text: "Use", title: "Put only this style on the node (Enter)",
                    onclick: () => use(style) }),
                h("button", { text: inTray(style) >= 0 ? "In blend" : (full ? "Swap into blend" : "Add to blend"),
                    disabled: inTray(style) >= 0, title: "Blend it with what is already chosen (B)",
                    onclick: () => blend(style) }),
                h("button", { text: fav ? "★ Favourite" : "☆ Favourite",
                    "aria-pressed": fav ? "true" : "false", title: "F",
                    onclick: () => toggleFavourite(style.id) }),
                collections),
            h("div", { class: "lead", text: style.lead }),
            h("ol", {}, style.parts.map((part, index) => h("li", {
                class: index === 1 || index === 3 ? "cut" : "", text: part }))),
            h("div", { class: "hint", text: "Light strength keeps the first two lines, standard four, heavy all of them." }),
            style.tags.length ? h("div", { class: "tags" }, style.tags.map((tag) => h("span", { text: tag }))) : null,
            h("div", { class: "tags" }, style.traits.map((index) => h("span", { text: store.traits[index] }))),
            h("div", { class: "ns2-actions" },
                h("button", { text: "Save preview", disabled: !store.latestImage,
                    title: store.latestImage ? "Use the newest generated image as this style's preview"
                        : "Generate an image first",
                    onclick: async () => {
                        const reply = await savePreview(style.id, store.latestImage);
                        if (!reply.ok) alert(reply.error || "Could not save.");
                    } }),
                url ? h("button", { text: "Remove preview", onclick: () => deletePreview(style.id) }) : null,
                h("button", { text: style.catId === "custom" ? "Edit" : "Copy to my styles",
                    title: style.catId === "custom" ? "Change this style" : "Make your own version to edit",
                    onclick: () => openForm(style) }),
                style.catId === "custom" ? h("button", { text: "Delete", onclick: async () => {
                    if (!confirm(`Delete your style "${style.name}"?`)) return;
                    await post("/neons_style2/custom/delete", { name: style.name });
                    await loadCatalog();
                    redraw();
                } }) : null),
            drawTray());
    }

    /* ------------------------------------------------------------ form */
    function openForm(style) {
        body.querySelector(".ns2-form")?.remove();
        const editing = style && style.catId === "custom";
        const name = h("input", { type: "text", maxLength: 40,
            value: style ? (editing ? style.name : `${style.name} Copy`.slice(0, 40)) : "" });
        const sub = h("input", { type: "text", maxLength: 60, value: editing ? style.sub : "",
            placeholder: "optional: a group inside My Styles" });
        const lead = h("input", { type: "text", maxLength: 120, value: style?.lead || "",
            placeholder: "Soft cel-shaded anime illustration" });
        const parts = h("textarea", { value: (style?.parts || []).join("\n"),
            placeholder: "one descriptor per line, most defining first" });
        const tags = h("input", { type: "text", value: (style?.tags || []).join(", "),
            placeholder: "optional booru tags, comma-separated" });
        const error = h("div", { class: "err", role: "alert" });
        const form = h("div", { class: "ns2-form" }, h("div", { class: "box" },
            h("h3", { style: "margin:0", text: editing ? "Edit your style" : "New style" }),
            h("label", {}, "Name", name),
            h("label", {}, "Lead: one phrase naming the look and its medium", lead),
            h("label", {}, "Descriptors", parts),
            h("label", {}, "Tags, for tag-trained models", tags),
            h("label", {}, "Group", sub),
            error,
            h("div", { class: "ns2-actions" },
                h("button", { class: "key", text: "Save", onclick: async () => {
                    const reply = await post("/neons_style2/custom/save", {
                        style: { name: name.value, sub: sub.value, lead: lead.value,
                            parts: parts.value, tags: tags.value, traits: style
                                ? style.traits.map((index) => store.traits[index]) : [] },
                        replace: editing ? style.name : "" });
                    if (!reply.ok) {
                        error.textContent = reply.error || "Could not save.";
                        return;
                    }
                    form.remove();
                    await loadCatalog();
                    state.view = "cat";
                    state.cat = "custom";
                    state.sub = "";
                    state.selected = reply.id;
                    redraw();
                } }),
                h("button", { text: "Cancel", onclick: () => form.remove() }))));
        body.append(form);
        name.focus();
    }

    /* ------------------------------------------------------------ keys */
    function onKey(event) {
        if (event.key === "Escape") {
            event.stopPropagation();
            event.preventDefault();
            const layer = body.querySelector(".ns2-form, .ns2-menu");
            if (layer) layer.remove();
            else close();
            return;
        }
        const typing = ["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName);
        if (body.querySelector(".ns2-form")) return;
        if (event.key === "/" && !typing) {
            event.preventDefault();
            search.focus();
            search.select();
            return;
        }
        if (typing && document.activeElement !== search) return;
        if (document.activeElement === search && !["ArrowDown", "Enter"].includes(event.key)) return;
        const index = state.list.findIndex((style) => style.id === state.selected);
        const moves = { ArrowRight: 1, ArrowLeft: -1, ArrowDown: state.cols, ArrowUp: -state.cols };
        if (event.key in moves && state.list.length) {
            event.preventDefault();
            const next = Math.max(0, Math.min(state.list.length - 1, Math.max(0, index) + moves[event.key]));
            grid.focus();
            select(state.list[next].id, true);
            return;
        }
        const style = store.byId.get(state.selected);
        if (!style) return;
        if (event.key === "Enter") {
            event.preventDefault();
            use(style);
        } else if (!typing && event.key.toLowerCase() === "f") {
            toggleFavourite(style.id);
        } else if (!typing && event.key.toLowerCase() === "b") {
            blend(style);
        }
    }

    /* ------------------------------------------------------------ wire */
    search.addEventListener("input", () => {
        state.query = search.value;
        grid.scrollTop = 0;
        filter();
        measure();
        drawGrid(true);
        drawDetail();
    });
    sort.addEventListener("change", () => {
        state.sort = sort.value;
        redraw();
    });
    sizer.addEventListener("input", () => {
        state.size = Number(sizer.value);
        measure();
        drawGrid(true);
    });
    grid.addEventListener("scroll", () => {
        cancelAnimationFrame(frame);
        frame = requestAnimationFrame(() => drawGrid());
    });
    overlay.addEventListener("mousedown", (event) => {
        if (event.target === overlay) close();
    });
    document.addEventListener("keydown", onKey, true);
    const resizer = typeof ResizeObserver === "function" ? new ResizeObserver(() => {
        measure();
        drawGrid(true);
    }) : null;
    const stopWatching = onChange(() => {
        // a favourite, preview or collection changed: keep the place, refresh the faces
        filter();
        measure();
        drawGrid(true);
        drawSide();
        drawDetail();
    });

    document.body.append(overlay);
    current = overlay;
    resizer?.observe(grid);
    redraw();
    search.focus();
    loadCatalog().then(() => redraw()).catch(() => {
        spacer.replaceChildren(h("div", { class: "ns2-empty",
            text: "Could not load the style catalog. Restart ComfyUI and reload this page." }));
    });
}
