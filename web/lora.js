import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { ensureCss } from "./css.js";
import { state } from "./api.js";

/**
 * Neons LoRA Explorer — the LoRA loader with its gallery attached.
 *
 * The picker is grouped by the folders in ComfyUI's loras directory: the top
 * folder is a gallery, a folder inside it is a family. Each gallery keeps its
 * own previews, so one LoRA filed under two checkpoints has two sets of
 * images. Saving is manual — there is no crawl and no auto-populate here.
 */

const NODE = "NeonsLoraExplorer";
const catalog = { loras: [], galleries: [], favourites: [], triggers: {}, previews: {}, ready: false };

async function call(path, body) {
    try {
        const init = body
            ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }
            : undefined;
        const response = await api.fetchApi(path, init);
        if (!response || response.ok === false) return null;
        return await response.json();
    } catch (err) {
        console.warn(`Neons LoRA Explorer: ${path} failed`, err);
        return null;
    }
}

async function loadCatalog(refresh = false) {
    const data = await call(`/neons_lora/catalog${refresh ? "?refresh=1" : ""}`);
    if (!data?.ok) return catalog;
    Object.assign(catalog, {
        loras: data.loras || [],
        galleries: data.galleries || [],
        favourites: data.favourites || [],
        triggers: data.triggers || {},
        previews: data.previews || {},
        ready: true,
    });
    return catalog;
}

const VIEW_KEY = "ns.lora.view";

/** The browser's toolbar state, kept between visits. */
function savedView() {
    try {
        const stored = JSON.parse(localStorage.getItem(VIEW_KEY) || "{}");
        return stored && typeof stored === "object" ? stored : {};
    } catch (err) {
        return {};
    }
}

function saveView(view) {
    try {
        localStorage.setItem(VIEW_KEY, JSON.stringify({ ...savedView(), ...view }));
    } catch (err) {
        /* private browsing, or a full quota: the browser just will not remember */
    }
}

/** Put a value back on a dropdown, but only if that option still exists. */
function restoreSelect(select, value) {
    if (!value) return;
    if ([...select.options].some((option) => option.value === value)) select.value = value;
}

const entryOf = (name) => catalog.loras.find((row) => row.name === name) || null;
const triggersFor = (name) => catalog.triggers?.[name] || entryOf(name)?.triggers || "";
const isFavourite = (name) => catalog.favourites.includes(name);

function shotsOf(name) {
    const row = entryOf(name);
    if (!row) return null;
    return (catalog.previews[row.gallery] || {})[row.key] || null;
}

function shotUrl(name, file) {
    const row = entryOf(name);
    if (!row) return "";
    const query = new URLSearchParams({ gallery: row.gallery, key: row.key, file: file || "" });
    return `/neons_lora/shot?${query}`;
}

const escapeHtml = (text) => String(text ?? "").replace(/[&<>]/g, (ch) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[ch]));

/* --------------------------------------------------------------- widgets */

const widget = (node, name) => (node.widgets || []).find((w) => w.name === name);
const valueOf = (node, name, fallback) => {
    const found = widget(node, name);
    return found ? found.value : fallback;
};

function setLora(node, name) {
    const found = widget(node, "lora");
    if (!found) return;
    found.value = name;
    found.callback?.(name);
    refresh(node);
    node.setDirtyCanvas?.(true, true);
}

/* --------------------------------------------------------------- browser */

function openBrowser(node) {
    ensureCss();
    document.getElementById("ns-lora-browser")?.remove();
    const overlay = document.createElement("div");
    overlay.className = "ns-overlay";
    overlay.id = "ns-lora-browser";
    overlay.innerHTML = `
      <div class="ns-scroll">
        <div class="ns-banner lora"><img src="/neons_lora/banner" alt=""></div>
        <div class="ns-tools">
          <strong>LoRAs</strong>
          <span class="n"></span>
          <input type="search" placeholder="Search name, gallery or family">
          <select class="gal"></select>
          <select class="fam"><option value="">All families</option></select>
          <select class="have">
            <option value="all">All</option>
            <option value="fav">&#9733; Favourites</option>
            <option value="has">Has preview</option>
            <option value="missing">Missing preview</option>
          </select>
          <button class="rescan" title="Re-read the loras folder">Rescan</button>
          <button class="close">Close</button>
        </div>
        <div class="ns-viewport"><div class="ns-cards flow"></div></div>
      </div>
      <div class="ns-foot"><span class="clause"></span><span class="cov"></span></div>
    `;
    document.body.appendChild(overlay);

    const scroll = overlay.querySelector(".ns-scroll");
    const banner = overlay.querySelector(".ns-banner");
    // fades out under the toolbar as the grid is scrolled, and comes back at
    // the top — the list matters more than the picture once you are reading it
    let scrollTimer = null;
    scroll.addEventListener("scroll", () => {
        const fade = Math.min(1, Math.max(0, scroll.scrollTop / 140));
        banner.style.opacity = String(1 - fade);
        clearTimeout(scrollTimer);
        scrollTimer = setTimeout(remember, 400);
    }, { passive: true });

    const cards = overlay.querySelector(".ns-cards");
    const counter = overlay.querySelector(".n");
    const coverage = overlay.querySelector(".cov");
    const search = overlay.querySelector("input[type=search]");
    const galSel = overlay.querySelector(".gal");
    const famSel = overlay.querySelector(".fam");
    const haveSel = overlay.querySelector(".have");

    const view = savedView();

    function paintGalleries() {
        const had = galSel.value;
        galSel.innerHTML = "";
        galSel.add(new Option("All galleries", ""));
        for (const bucket of catalog.galleries) {
            galSel.add(new Option(`${bucket.name} (${bucket.count})`, bucket.name));
        }
        restoreSelect(galSel, had);
    }

    function paintFamilies() {
        const had = famSel.value;
        const bucket = catalog.galleries.find((row) => row.name === galSel.value);
        famSel.innerHTML = "";
        famSel.add(new Option("All families", ""));
        for (const family of bucket ? bucket.families : [...new Set(catalog.loras.map((r) => r.family))].filter(Boolean).sort()) {
            famSel.add(new Option(family, family));
        }
        restoreSelect(famSel, had);
    }

    const remember = () => saveView({
        search: search.value,
        gallery: galSel.value,
        family: famSel.value,
        have: haveSel.value,
        scroll: Math.round(scroll.scrollTop),
    });

    function draw() {
        const query = search.value.trim().toLowerCase();
        const rows = catalog.loras.filter((row) => {
            if (galSel.value && row.gallery !== galSel.value) return false;
            if (famSel.value && row.family !== famSel.value) return false;
            const shots = shotsOf(row.name);
            if (haveSel.value === "has" && !shots) return false;
            if (haveSel.value === "missing" && shots) return false;
            if (haveSel.value === "fav" && !isFavourite(row.name)) return false;
            if (!query) return true;
            return `${row.label} ${row.gallery} ${row.family}`.toLowerCase().includes(query);
        });

        counter.textContent = `${rows.length} of ${catalog.loras.length}`;
        const withShots = Object.values(catalog.previews).reduce((sum, bucket) => sum + Object.keys(bucket).length, 0);
        coverage.textContent = `${withShots} of ${catalog.loras.length} have previews`
            + (catalog.favourites.length ? ` · ${catalog.favourites.length} favourites` : "");

        cards.innerHTML = "";
        for (const row of rows) {
            const shots = shotsOf(row.name);
            const card = document.createElement("div");
            card.className = "ns-card";
            card.style.width = "190px";
            const trigLine = triggersFor(row.name);
            card.title = `${row.name}\n${row.gallery}${row.family ? ` · ${row.family}` : ""}\n`
                + (shots ? `${shots.count} preview${shots.count === 1 ? "" : "s"}` : "no preview yet")
                + (trigLine ? `\ntriggers: ${trigLine}` : "");
            card.innerHTML = `
              <div class="pic" style="height:190px">
                ${shots
                    ? `<img loading="lazy" decoding="async" draggable="false" src="${shotUrl(row.name, shots.cover)}" alt="">
                       ${shots.count > 1 ? `<span class="cnt">${shots.count}</span>` : ""}
                       <button class="killshot" type="button" title="Delete this preview">&#10005;</button>`
                    : `<div class="empty">no preview</div>`}
                <button class="star${isFavourite(row.name) ? " on" : ""}" type="button"
                        title="Favourite">${isFavourite(row.name) ? "&#9733;" : "&#9734;"}</button>
              </div>
              <div class="body">
                <div class="ttl"></div>
                <div class="meta">
                  <span class="pill shipped">${escapeHtml(row.gallery)}</span>
                  ${row.family ? `<span class="pill draft">${escapeHtml(row.family)}</span>` : ""}
                  <span class="sp"></span>
                  <button class="use key" type="button">Use</button>
                </div>
              </div>`;
            card.querySelector(".ttl").textContent = row.label;
            const trig = triggersFor(row.name);
            if (trig) {
                const line = document.createElement("span");
                line.className = "trig";
                line.textContent = trig;
                line.title = trig;
                card.querySelector(".ttl").after(line);
            }
            card.querySelector(".killshot")?.addEventListener("click", async (ev) => {
                ev.stopPropagation();
                const shot = shotsOf(row.name);
                const many = shot && shot.count > 1;
                const question = many
                    ? `Delete all ${shot.count} images for ${row.label}?`
                    : `Delete the preview for ${row.label}?`;
                if (!confirm(question)) return;
                await call("/neons_lora/delete", { lora: row.name });
                await loadCatalog();
                draw();
                for (const open of app.graph?._nodes || []) {
                    if ((open.comfyClass || open.type) === NODE) refresh(open);
                }
            });
            card.querySelector(".star").addEventListener("click", async (ev) => {
                ev.stopPropagation();
                const result = await call("/neons_lora/favourite", { lora: row.name, toggle: true });
                if (result?.ok) catalog.favourites = result.favourites || [];
                draw();
            });
            const pick = () => {
                setLora(node, row.name);
                overlay.remove();
            };
            card.querySelector(".use").addEventListener("click", (ev) => {
                ev.stopPropagation();
                pick();
            });
            card.addEventListener("click", (ev) => {
                if (ev.target.closest("button")) return;
                pick();
            });
            card.addEventListener("mouseenter", () => {
                overlay.querySelector(".clause").textContent = row.name;
            });
            cards.appendChild(card);
        }
    }

    paintGalleries();
    paintFamilies();
    // the filters you left the browser on are the ones you come back to
    restoreSelect(galSel, view.gallery);
    paintFamilies();
    restoreSelect(famSel, view.family);
    restoreSelect(haveSel, view.have);
    if (typeof view.search === "string") search.value = view.search;

    galSel.addEventListener("change", () => {
        paintFamilies();
        draw();
    });
    [search, famSel, haveSel].forEach((control) => {
        control.addEventListener("input", draw);
        control.addEventListener("input", remember);
        control.addEventListener("change", remember);
    });
    galSel.addEventListener("change", remember);
    overlay.querySelector(".rescan").onclick = async () => {
        await loadCatalog(true);
        paintGalleries();
        paintFamilies();
        draw();
    };
    overlay.querySelector(".close").onclick = () => overlay.remove();
    overlay.addEventListener("mousedown", (ev) => {
        if (ev.target === overlay) overlay.remove();
    });
    overlay.addEventListener("ns:lora-refresh", draw);
    draw();
    if (view.scroll > 0) {
        // after the cards exist, or there is nothing to scroll through yet
        requestAnimationFrame(() => {
            scroll.scrollTop = view.scroll;
            banner.style.opacity = String(1 - Math.min(1, scroll.scrollTop / 140));
        });
    }
    search.focus();
}

/* ----------------------------------------------------------------- panel */

function refresh(node) {
    const panel = node._nsLoraPanel;
    if (!panel) return;
    const name = String(valueOf(node, "lora", "None") || "None");
    const row = name === "None" ? null : entryOf(name);
    const shots = row ? shotsOf(name) : null;

    const img = panel.querySelector(".ns-thumb img");
    const none = panel.querySelector(".ns-none");
    if (shots) {
        img.src = shotUrl(name, shots.cover);
        img.style.display = "block";
        none.style.display = "none";
    } else {
        img.removeAttribute("src");
        img.style.display = "none";
        none.style.display = "flex";
        none.textContent = row ? "No preview yet — generate, then Save" : "Pick a LoRA";
    }

    panel.querySelector(".ns-name").textContent = row ? row.label : "";
    const chip = panel.querySelector(".ns-chip");
    chip.textContent = row ? `${row.gallery}${row.family ? ` / ${row.family}` : ""}` : "";
    chip.style.display = chip.textContent ? "block" : "none";

    const words = panel.querySelector(".ns-lora-trigger .words");
    const saved = row ? triggersFor(name) : "";
    words.textContent = saved || "none saved";
    words.classList.toggle("none", !saved);

    const star = panel.querySelector(".fav");
    const starred = row ? isFavourite(name) : false;
    star.innerHTML = starred ? "&#9733;" : "&#9734;";
    star.classList.toggle("on", starred);

    const strip = panel.querySelector(".ns-shots");
    strip.innerHTML = shots
        ? shots.shots.map((shot) => `
            <span class="ns-shot${shot.file === shots.cover ? " on" : ""}">
              <button type="button" class="pick" data-file="${shot.file}" title="Use as cover">
                <img loading="lazy" draggable="false" src="${shotUrl(name, shot.file)}" alt="">
              </button>
              <button type="button" class="drop" data-file="${shot.file}" title="Delete this preview">&#10005;</button>
            </span>`).join("")
        : "";
    strip.querySelectorAll(".pick").forEach((button) => {
        button.onclick = async () => {
            await call("/neons_lora/cover", { gallery: row.gallery, key: row.key, file: button.dataset.file });
            await loadCatalog();
            refresh(node);
        };
    });
    strip.querySelectorAll(".drop").forEach((button) => {
        button.onclick = async () => {
            await call("/neons_lora/shot/delete", { gallery: row.gallery, key: row.key, file: button.dataset.file });
            await loadCatalog();
            refresh(node);
        };
    });
}

function say(node, text, bad = false) {
    const note = node._nsLoraPanel?.querySelector(".ns-say");
    if (!note) return;
    note.textContent = text || "";
    note.classList.toggle("bad", Boolean(bad));
    note.style.display = text ? "block" : "none";
    clearTimeout(node._nsLoraSayTimer);
    if (text) {
        node._nsLoraSayTimer = setTimeout(() => {
            note.textContent = "";
            note.style.display = "none";
        }, 6000);
    }
}

async function saveLatest(node) {
    const name = String(valueOf(node, "lora", "None") || "None");
    if (name === "None") return say(node, "pick a LoRA first", true);
    const image = state.lastImages?.[0];
    if (!image) return say(node, "generate an image first", true);
    const result = await call("/neons_lora/save", {
        lora: name,
        filename: image.filename,
        subfolder: image.subfolder || "",
        type: image.type || "output",
    });
    if (!result?.ok) return say(node, result?.error || "could not save that image", true);
    await loadCatalog();
    refresh(node);
    // repaint an open browser too, so the new preview appears without reopening
    document.getElementById("ns-lora-browser")?.dispatchEvent(new CustomEvent("ns:lora-refresh"));
    say(node, `saved to ${result.gallery} — ${result.record?.count || 1} image(s)`);
}

/* rows under the preview: shot strip, trigger line, button bar, gaps */
const PANEL_ROWS = 36 + 22 + 32 + 22;
const THUMB_MIN = 150;
const THUMB_MAX = 420;
const NODE_MIN_W = 300;
const NODE_MAX_W = THUMB_MAX + 46;   // the widest the square preview can use

/**
 * Size the panel from the node's WIDTH, never its height.
 *
 * Deriving it from the height was a feedback loop: litegraph sizes a node from
 * its widgets, so a panel that measured the node and then reported a height
 * added the slack back on every pass and the node crept longer with each drag.
 * Width is an input the node does not recompute, so this settles immediately —
 * drag the node wider and the square preview grows with it.
 */
function sizePanel(node) {
    const panel = node._nsLoraPanel;
    const found = widget(node, "ns_lora_panel");
    if (!panel || !found) return;
    const width = Math.max(240, node.size?.[0] || 380);
    const side = Math.max(THUMB_MIN, Math.min(THUMB_MAX, width - 26));
    const height = side + PANEL_ROWS;

    node._nsLoraHeight = height;
    found.computedHeight = height;
    // the current frontend lays DOM widgets out through computeLayoutSize and
    // ignores computeSize, so report the same figure both ways
    found.computeLayoutSize = () => ({
        minHeight: height, maxHeight: height, minWidth: 240,
    });
    panel.style.height = `${height}px`;
    const stage = panel.querySelector(".ns-stage");
    const thumb = panel.querySelector(".ns-thumb");
    if (stage) stage.style.height = `${side}px`;
    if (thumb) {
        thumb.style.width = `${side}px`;
        thumb.style.height = `${side}px`;
    }
    return height;
}

/** Exactly the height this node needs: the widgets, the panel, a margin. */
function idealHeight(node) {
    const height = sizePanel(node) || 300;
    const found = widget(node, "ns_lora_panel");
    const top = typeof found?.last_y === "number" && found.last_y > 20 ? found.last_y : 150;
    // the buttons sat a few pixels below the frame without this margin
    return Math.round(top + height + 14);
}

/**
 * Keep the node at its content size on every draw.
 *
 * Clamping inside onResize was not enough: the frontend does not always route a
 * corner drag through onResize, so the node could still be stretched. A draw
 * pass always happens, and since the wanted size is derived only from the
 * width this corrects once and then agrees with itself.
 */
function holdSize(node) {
    if (!node?.size || node.flags?.collapsed || !node._nsLoraPanel) return;
    const width = Math.max(NODE_MIN_W, Math.min(NODE_MAX_W, Math.round(node.size[0] || 380)));
    if (Math.abs(node.size[0] - width) > 1) node.size[0] = width;
    const height = idealHeight(node);
    if (Math.abs((node.size[1] || 0) - height) > 2) {
        node.size[1] = height;
        node.setDirtyCanvas?.(true, true);
    }
}

/**
 * Hold the node at its content size.
 *
 * There is nothing to gain from a taller node — the panel is a square preview
 * and three rows — so dragging it longer only added dead space below the
 * buttons. The width is clamped to the range the preview can use, and the
 * height is then whatever that width needs.
 */
function fitNode(node) {
    if (!node?.size) return [0, 0];
    const width = Math.max(NODE_MIN_W, Math.min(NODE_MAX_W, Math.round(node.size[0] || 380)));
    node.size[0] = width;                 // the panel measures the width
    const height = idealHeight(node);
    if (Math.abs(node.size[0] - width) > 2 || Math.abs((node.size[1] || 0) - height) > 4) {
        node.setSize?.([width, height]);
    }
    node.size[1] = height;
    sizePanel(node);
    return [width, height];
}

function attachPanel(node) {
    if (node._nsLoraPanel) return;
    ensureCss();
    const panel = document.createElement("div");
    panel.className = "ns-panel lora";
    panel.innerHTML = `
      <div class="ns-stage">
        <div class="ns-thumb">
          <img alt="lora preview">
          <div class="ns-none">Pick a LoRA</div>
          <div class="ns-chip"></div>
          <div class="ns-name"></div>
          <div class="ns-say"></div>
        </div>
      </div>
      <div class="ns-shots"></div>
      <div class="ns-lora-trigger">
        <span class="lbl">triggers</span>
        <span class="words none">none saved</span>
        <input type="text" placeholder="words this LoRA wants in the prompt" maxlength="400" style="display:none">
        <button type="button" class="edit">Edit</button>
      </div>
      <div class="ns-bar">
        <button type="button" class="browse key" title="Browse your LoRAs by gallery and family">Gallery</button>
        <button type="button" class="save" title="Save the newest generated image against this LoRA">Save</button>
        <button type="button" class="fav icon" title="Favourite this LoRA">&#9734;</button>
        <button type="button" class="more icon" title="More">&#8943;</button>
      </div>
    `;

    panel.querySelector(".ns-thumb").onclick = () => openBrowser(node);
    panel.querySelector(".browse").onclick = () => openBrowser(node);
    panel.querySelector(".save").onclick = () => saveLatest(node);
    panel.querySelector(".fav").onclick = async () => {
        const name = String(valueOf(node, "lora", "None") || "None");
        if (name === "None") return;
        const result = await call("/neons_lora/favourite", { lora: name, toggle: true });
        if (result?.ok) catalog.favourites = result.favourites || [];
        refresh(node);
    };
    panel.querySelector(".more").onclick = async () => {
        const name = String(valueOf(node, "lora", "None") || "None");
        if (name === "None") return;
        if (!confirm(`Delete every saved image for ${name}?`)) return;
        const result = await call("/neons_lora/delete", { lora: name });
        await loadCatalog();
        refresh(node);
        say(node, `deleted ${result?.removed || 0} image(s)`);
    };

    // trigger words: shown under the name, edited in place
    const trigger = panel.querySelector(".ns-lora-trigger");
    const words = trigger.querySelector(".words");
    const field = trigger.querySelector("input");
    const editButton = trigger.querySelector(".edit");
    const editing = (on) => {
        field.style.display = on ? "block" : "none";
        words.style.display = on ? "none" : "block";
        editButton.textContent = on ? "Save" : "Edit";
        if (on) {
            field.value = triggersFor(String(valueOf(node, "lora", "None") || "None"));
            field.focus();
        }
    };
    const commit = async () => {
        const name = String(valueOf(node, "lora", "None") || "None");
        if (name === "None") return editing(false);
        const result = await call("/neons_lora/triggers", { lora: name, text: field.value });
        if (result?.ok) catalog.triggers = { ...catalog.triggers, [name]: result.triggers };
        editing(false);
        refresh(node);
        say(node, result?.triggers ? "trigger words saved" : "trigger words cleared");
    };
    editButton.onclick = () => (field.style.display === "none" ? editing(true) : commit());
    field.onkeydown = (ev) => {
        ev.stopPropagation();
        if (ev.key === "Enter") commit();
        if (ev.key === "Escape") editing(false);
    };
    field.onkeyup = (ev) => ev.stopPropagation();

    const w = node.addDOMWidget("ns_lora_panel", "panel", panel, { serialize: false });
    w.computeSize = () => [node.size?.[0] || 380, node._nsLoraHeight || 300];
    node._nsLoraPanel = panel;
    sizePanel(node);
}

/* ------------------------------------------------------------ extension */

app.registerExtension({
    name: "Neons.LoraExplorer",

    async setup() {
        await loadCatalog();
        for (const node of app.graph?._nodes || []) {
            if ((node.comfyClass || node.type) === NODE) refresh(node);
        }
    },

    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData?.name !== NODE) return;

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const result = onNodeCreated?.apply(this, arguments);
            attachPanel(this);
            if (!catalog.ready) loadCatalog().then(() => refresh(this));
            else refresh(this);
            const found = widget(this, "lora");
            if (found && !found._nsHooked) {
                found._nsHooked = true;
                const original = found.callback;
                found.callback = (...args) => {
                    const out = original?.apply(found, args);
                    refresh(this);
                    return out;
                };
            }
            this.setSize?.([Math.max(this.size?.[0] || 380, 380), this.size?.[1] || 460]);
            sizePanel(this);
            // last_y only exists after a draw, so settle the height next frame
            requestAnimationFrame(() => fitNode(this));
            return result;
        };

        // dragging the node's corner has to reach the panel
        const onResize = nodeType.prototype.onResize;
        nodeType.prototype.onResize = function (size) {
            const result = onResize?.apply(this, arguments);
            // Clamp in place: litegraph hands us its own size array while the
            // drag is happening, so writing here holds the node at its content
            // size instead of letting it be stretched into empty space.
            if (Array.isArray(size)) {
                size[0] = Math.max(NODE_MIN_W, Math.min(NODE_MAX_W, Math.round(size[0])));
                this.size[0] = size[0];
                sizePanel(this);
                size[1] = idealHeight(this);
                this.size[1] = size[1];
                if (size !== this.size) {
                    this.size[0] = size[0];
                    this.size[1] = size[1];
                }
            }
            return result;
        };

        // a saved workflow can carry a size from an older version
        const onConfigure = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function (info) {
            const result = onConfigure?.apply(this, arguments);
            requestAnimationFrame(() => fitNode(this));
            return result;
        };

        const onDrawForeground = nodeType.prototype.onDrawForeground;
        nodeType.prototype.onDrawForeground = function (ctx) {
            const result = onDrawForeground?.apply(this, arguments);
            // last_y only exists after a draw pass, so the first one settles
            // the layout and every one after holds it
            if (!this._nsLoraSized && this._nsLoraPanel) {
                this._nsLoraSized = true;
                fitNode(this);
            } else {
                holdSize(this);
            }
            return result;
        };

        const onExecuted = nodeType.prototype.onExecuted;
        nodeType.prototype.onExecuted = function (message) {
            const result = onExecuted?.apply(this, arguments);
            refresh(this);
            return result;
        };

        const getExtraMenuOptions = nodeType.prototype.getExtraMenuOptions;
        nodeType.prototype.getExtraMenuOptions = function (canvas, options) {
            getExtraMenuOptions?.apply(this, arguments);
            options.push(
                { content: "Neons: browse LoRAs", callback: () => openBrowser(this) },
                { content: "Neons: save last image to this LoRA", callback: () => saveLatest(this) },
                {
                    content: "Neons: rescan the loras folder",
                    callback: async () => {
                        await loadCatalog(true);
                        refresh(this);
                    },
                },
            );
        };
    },
});
