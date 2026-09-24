/**
 * The asset explorer: one interface, used by the LoRA and checkpoint nodes.
 *
 * Both want the same thing — a picker grouped by the folders the files already
 * live in, a preview gallery per top folder, favourites, and a line of text per
 * file. Keeping two copies of this is what let the two drift apart, so the
 * whole interface is built once here and each node passes in what differs.
 *
 * `createExplorer(cfg)` registers one extension. See lora.js and model.js for
 * the two configurations.
 */
import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { ensureCss } from "./css.js";
import { state } from "./api.js";

export function createExplorer(cfg) {
    /**
     * Neons LoRA Explorer — the LoRA loader with its gallery attached.
     *
     * The picker is grouped by the folders the files live in: the top
     * folder is a gallery, a folder inside it is a family. Each gallery keeps its
     * own previews, so one LoRA filed under two checkpoints has two sets of
     * images. Saving is manual — there is no crawl and no auto-populate here.
     */

    const catalog = { rows: [], galleries: [], favourites: [], text: {}, previews: {},
        moved: [], detached: [], ready: false };

    async function call(path, body) {
        try {
            const init = body
                ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }
                : undefined;
            const response = await api.fetchApi(path, init);
            if (!response || response.ok === false) return null;
            return await response.json();
        } catch (err) {
            console.warn(`${cfg.label}: ${path} failed`, err);
            return null;
        }
    }

    async function loadCatalog(refresh = false) {
        const data = await call(`${cfg.route}/catalog${refresh ? "?refresh=1" : ""}`);
        if (!data?.ok) return catalog;
        Object.assign(catalog, {
            rows: data[cfg.listKey] || [],
            galleries: data.galleries || [],
            favourites: data.favourites || [],
            text: data[cfg.textField] || {},
            moved: data.moved || [],
            detached: data.detached || [],
            previews: data.previews || {},
            ready: true,
        });
        return catalog;
    }

    const VIEW_KEY = `ns.${cfg.kind}.view`;

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

    const entryOf = (name) => catalog.rows.find((row) => row.name === name) || null;
    const textFor = (name) => catalog.text?.[name] || entryOf(name)?.[cfg.textField] || "";
    const isFavourite = (name) => catalog.favourites.includes(name);

    function shotsOf(name) {
        const row = entryOf(name);
        if (!row) return null;
        return (catalog.previews[row.gallery] || {})[row.key] || null;
    }

    // Which image each card is showing. Kept outside the cards so scrolling a
    // virtualised grid — or a repaint after a save — does not lose your place.
    const shotIndex = new Map();

    const coverIndex = (shots) => Math.max(0, shots.shots.findIndex((s) => s.file === shots.cover));

    // cards are 190px; the stored preview is 512. Ask for what fits.
    const CARD_THUMB = 256;

    function shotUrl(name, file, size) {
        const row = entryOf(name);
        if (!row) return "";
        const query = new URLSearchParams({ gallery: row.gallery, key: row.key, file: file || "" });
        if (size) query.set("size", String(size));
        return `${cfg.route}/shot?${query}`;
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
        const found = widget(node, cfg.picker);
        if (!found) return;
        found.value = name;
        found.callback?.(name);
        refresh(node);
        node.setDirtyCanvas?.(true, true);
    }

    /* --------------------------------------------------------------- browser */

    function openBrowser(node) {
        ensureCss();
        document.getElementById(`ns-${cfg.kind}-browser`)?.remove();
        const overlay = document.createElement("div");
        overlay.className = "ns-overlay";
        overlay.id = `ns-${cfg.kind}-browser`;
        overlay.innerHTML = `
          <div class="ns-scroll">
            <div class="ns-banner asset"><img src="${cfg.route}/banner" alt=""></div>
            <div class="ns-tools">
              <strong>${cfg.plural}</strong>
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
              <button class="rescan" title="Re-read the ${cfg.folder} folder">Rescan</button>
          <button class="thumbs" title="Only needed if you are updating from an earlier version: it builds the small copies the gallery loads instead of the full-size previews, so the grid opens faster. New previews get theirs automatically. ComfyUI will be busy while it runs.">Build fast thumbs</button>
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
            for (const family of bucket ? bucket.families : [...new Set(catalog.rows.map((r) => r.family))].filter(Boolean).sort()) {
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
            const rows = catalog.rows.filter((row) => {
                if (galSel.value && row.gallery !== galSel.value) return false;
                if (famSel.value && row.family !== famSel.value) return false;
                const shots = shotsOf(row.name);
                if (haveSel.value === "has" && !shots) return false;
                if (haveSel.value === "missing" && shots) return false;
                if (haveSel.value === "fav" && !isFavourite(row.name)) return false;
                if (!query) return true;
                return `${row.label} ${row.gallery} ${row.family}`.toLowerCase().includes(query);
            });

            counter.textContent = `${rows.length} of ${catalog.rows.length}`;
            const withShots = Object.values(catalog.previews).reduce((sum, bucket) => sum + Object.keys(bucket).length, 0);
            coverage.textContent = `${withShots} of ${catalog.rows.length} have previews`
                + (catalog.favourites.length ? ` · ${catalog.favourites.length} favourites` : "");

            cards.innerHTML = "";
            for (const row of rows) {
                const shots = shotsOf(row.name);
                const card = document.createElement("div");
                card.className = "ns-card";
                card.style.width = "190px";
                const trigLine = textFor(row.name);
                card.title = `${row.name}\n${row.gallery}${row.family ? ` · ${row.family}` : ""}\n`
                    + (shots ? `${shots.count} preview${shots.count === 1 ? "" : "s"}` : "no preview yet")
                    + (trigLine ? `\n${cfg.textLabel}: ${trigLine}` : "");
                card.innerHTML = `
                  <div class="pic" style="height:190px">
                    ${shots
                        ? `<img loading="lazy" decoding="async" draggable="false" src="${shotUrl(row.name, shots.shots[shotIndex.get(row.name) ?? coverIndex(shots)]?.file || shots.cover, CARD_THUMB)}" alt="">
                           ${shots.count > 1
                               ? `<button class="flip prev" type="button" title="Previous image">&#8249;</button>
                                  <button class="flip next" type="button" title="Next image">&#8250;</button>
                                  <span class="cnt">${(shotIndex.get(row.name) ?? coverIndex(shots)) + 1}/${shots.count}</span>`
                               : ""}
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
                const trig = textFor(row.name);
                if (trig) {
                    const line = document.createElement("span");
                    line.className = "trig";
                    line.textContent = trig;
                    line.title = trig;
                    card.querySelector(".ttl").after(line);
                }
                if (shots && shots.count > 1) {
                    const picture = card.querySelector("img");
                    const counter = card.querySelector(".cnt");
                    const step = (by) => {
                        const at = shotIndex.get(row.name) ?? coverIndex(shots);
                        // wraps at both ends, so you can keep going either way
                        const next = (at + by + shots.count) % shots.count;
                        shotIndex.set(row.name, next);
                        picture.src = shotUrl(row.name, shots.shots[next].file, CARD_THUMB);
                        counter.textContent = `${next + 1}/${shots.count}`;
                    };
                    for (const [selector, by] of [[".prev", -1], [".next", 1]]) {
                        card.querySelector(selector).addEventListener("click", (ev) => {
                            ev.stopPropagation();   // not a click on the card
                            ev.preventDefault();
                            step(by);
                        });
                    }
                }

                card.querySelector(".killshot")?.addEventListener("click", async (ev) => {
                    ev.stopPropagation();
                    const shot = shotsOf(row.name);
                    const many = shot && shot.count > 1;
                    const question = many
                        ? `Delete all ${shot.count} images for ${row.label}?`
                        : `Delete the preview for ${row.label}?`;
                    if (!confirm(question)) return;
                    shotIndex.delete(row.name);
                    await call(`${cfg.route}/delete`, { [cfg.key]: row.name });
                    await loadCatalog();
                    draw();
                    for (const open of app.graph?._nodes || []) {
                        if ((open.comfyClass || open.type) === NODE) refresh(open);
                    }
                });
                card.querySelector(".star").addEventListener("click", async (ev) => {
                    ev.stopPropagation();
                    const result = await call(`${cfg.route}/favourite`, { [cfg.key]: row.name, toggle: true });
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
        overlay.querySelector(".thumbs").onclick = async () => {
        const total = Object.values(catalog.previews || {})
            .reduce((sum, bucket) => sum + Object.keys(bucket).length, 0);
        if (!confirm(`Build fast thumbs for your ${cfg.plural}?\n\n`
            + `About ${total} preview${total === 1 ? "" : "s"} to check. ComfyUI will be `
            + "busy for a few seconds while it works, and the gallery will open faster "
            + "afterwards.\n\nOnly worth doing once, after updating from a version that "
            + "did not have them.")) return;
        const result = await call(`${cfg.route}/thumbs`, {});
        if (!result?.ok) return alert("Could not build the thumbs.");
        alert(result.built
            ? `Built ${result.built} for ${result.previews} preview(s).`
            : `Nothing to do — all ${result.previews} preview(s) already have theirs.`);
    };

    overlay.querySelector(".rescan").onclick = async () => {
            const fresh = await loadCatalog(true);
            const moved = fresh?.moved || catalog.moved || [];
            const detached = fresh?.detached || catalog.detached || [];
            if (moved.length || detached.length) {
                // a move is silent otherwise, and the previews appear to have
                // wandered — say what was reattached
                const lines = [
                    ...moved.map((m) => `moved: ${m.from} → ${m.to}`),
                    ...detached.map((p) => `different file now at: ${p}`),
                ];
                console.log("${cfg.label}: " + lines.join(" | "));
                alert(`Rescan reattached ${moved.length} moved ${cfg.singular}${moved.length === 1 ? "" : "s"}`
                    + (detached.length ? `, and parked previews for ${detached.length} replaced file${detached.length === 1 ? "" : "s"}` : "")
                    + ".");
            }
            paintGalleries();
            paintFamilies();
            draw();
        };
        overlay.querySelector(".close").onclick = () => overlay.remove();
        overlay.addEventListener("mousedown", (ev) => {
            if (ev.target === overlay) overlay.remove();
        });
        overlay.addEventListener(`ns:${cfg.kind}-refresh`, draw);
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
        const panel = node._nsAssetPanel;
        if (!panel) return;
        const name = String(valueOf(node, cfg.picker, "None") || "None");
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
            none.textContent = row ? "No preview yet — generate, then Save" : cfg.pick;
        }

        panel.querySelector(".ns-name").textContent = row ? row.label : "";
        const chip = panel.querySelector(".ns-chip");
        chip.textContent = row ? `${row.gallery}${row.family ? ` / ${row.family}` : ""}` : "";
        chip.style.display = chip.textContent ? "block" : "none";

        const words = panel.querySelector(".ns-asset-text .words");
        const saved = row ? textFor(name) : "";
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
                await call(`${cfg.route}/cover`, { gallery: row.gallery, key: row.key, file: button.dataset.file });
                await loadCatalog();
                refresh(node);
            };
        });
        strip.querySelectorAll(".drop").forEach((button) => {
            button.onclick = async () => {
                await call(`${cfg.route}/shot/delete`, { gallery: row.gallery, key: row.key, file: button.dataset.file });
                await loadCatalog();
                refresh(node);
            };
        });
    }

    function say(node, text, bad = false) {
        const note = node._nsAssetPanel?.querySelector(".ns-say");
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
        const name = String(valueOf(node, cfg.picker, "None") || "None");
        if (name === "None") return say(node, cfg.pickFirst, true);
        const image = state.lastImages?.[0];
        if (!image) return say(node, "generate an image first", true);
        const result = await call(`${cfg.route}/save`, {
            [cfg.key]: name,
            filename: image.filename,
            subfolder: image.subfolder || "",
            type: image.type || "output",
        });
        if (!result?.ok) return say(node, result?.error || "could not save that image", true);
        await loadCatalog();
        refresh(node);
        // repaint an open browser too, so the new preview appears without reopening
        document.getElementById(`ns-${cfg.kind}-browser`)?.dispatchEvent(new CustomEvent(`ns:${cfg.kind}-refresh`));
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
        const panel = node._nsAssetPanel;
        const found = widget(node, `ns_${cfg.kind}_panel`);
        if (!panel || !found) return;
        const width = Math.max(240, node.size?.[0] || 380);
        const side = Math.max(THUMB_MIN, Math.min(THUMB_MAX, width - 26));
        const height = side + PANEL_ROWS;

        node._nsAssetHeight = height;
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
        const found = widget(node, `ns_${cfg.kind}_panel`);
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
        if (!node?.size || node.flags?.collapsed || !node._nsAssetPanel) return;
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

    /**
     * Only one of the two strength controls is ever in charge.
     *
     * With random_roll on, the strength comes from random_low/random_high, so
     * leaving the strength sliders live invites you to set a value that is then
     * ignored. With it off, the range is the dead pair instead. The unused ones are
     * disabled and dimmed rather than hidden, so the node does not change height
     * as you flip the switch.
     */
    function syncStrengthMode(node) {
        const rolling = Boolean(valueOf(node, "random_roll", false));
        const state = {
            strength_model: rolling,
            strength_clip: rolling,
            random_low: !rolling,
            random_high: !rolling,
            roll_seed: !rolling,
        };
        if (!cfg.strengthMode) return;
        for (const [name, off] of Object.entries(state)) {
            const found = widget(node, name);
            if (!found) continue;
            found.disabled = off;
            // litegraph dims a disabled widget; say why in the tooltip too
            const why = name.startsWith("strength")
                ? "Set by random_low / random_high while random_roll is on"
                : "Used only while random_roll is on";
            found._nsWhy = found._nsWhy ?? found.tooltip ?? "";
            found.tooltip = off ? why : found._nsWhy;
        }
        node.setDirtyCanvas?.(true, true);
    }

    function attachPanel(node) {
        if (node._nsAssetPanel) return;
        ensureCss();
        const panel = document.createElement("div");
        panel.className = `ns-panel asset ${cfg.kind}`;
        panel.innerHTML = `
          <div class="ns-stage">
            <div class="ns-thumb">
              <img alt="${cfg.singular} preview">
              <div class="ns-none">${cfg.pick}</div>
              <div class="ns-chip"></div>
              <div class="ns-name"></div>
              <div class="ns-say"></div>
            </div>
          </div>
          <div class="ns-shots"></div>
          <div class="ns-asset-text">
            <span class="lbl">${escapeHtml(cfg.textLabel)}</span>
            <span class="words none">none saved</span>
            <input type="text" placeholder="${escapeHtml(cfg.textPlaceholder)}" maxlength="400" style="display:none">
            <button type="button" class="edit">Edit</button>
          </div>
          <div class="ns-bar">
            <button type="button" class="browse key" title="Browse your ${cfg.plural} by gallery and family">Gallery</button>
            <button type="button" class="save" title="Save the newest generated image against this ${cfg.singular}">Save</button>
            <button type="button" class="fav icon" title="Favourite this ${cfg.singular}">&#9734;</button>
            <button type="button" class="more icon" title="More">&#8943;</button>
          </div>
        `;

        panel.querySelector(".ns-thumb").onclick = () => openBrowser(node);
        panel.querySelector(".browse").onclick = () => openBrowser(node);
        panel.querySelector(".save").onclick = () => saveLatest(node);
        panel.querySelector(".fav").onclick = async () => {
            const name = String(valueOf(node, cfg.picker, "None") || "None");
            if (name === "None") return;
            const result = await call(`${cfg.route}/favourite`, { [cfg.key]: name, toggle: true });
            if (result?.ok) catalog.favourites = result.favourites || [];
            refresh(node);
        };
        panel.querySelector(".more").onclick = async () => {
            const name = String(valueOf(node, cfg.picker, "None") || "None");
            if (name === "None") return;
            if (!confirm(`Delete every saved image for ${name}?`)) return;
            const result = await call(`${cfg.route}/delete`, { [cfg.key]: name });
            await loadCatalog();
            refresh(node);
            say(node, `deleted ${result?.removed || 0} image(s)`);
        };

        // trigger words: shown under the name, edited in place
        const trigger = panel.querySelector(".ns-asset-text");
        const words = trigger.querySelector(".words");
        const field = trigger.querySelector("input");
        const editButton = trigger.querySelector(".edit");
        const editing = (on) => {
            field.style.display = on ? "block" : "none";
            words.style.display = on ? "none" : "block";
            editButton.textContent = on ? "Save" : "Edit";
            if (on) {
                field.value = textFor(String(valueOf(node, cfg.picker, "None") || "None"));
                field.focus();
            }
        };
        const commit = async () => {
            const name = String(valueOf(node, cfg.picker, "None") || "None");
            if (name === "None") return editing(false);
            const result = await call(`${cfg.route}/text`, { [cfg.key]: name, text: field.value });
            if (!result?.ok) {
                // say so rather than closing as though it worked
                return say(node, result?.error || `could not save ${cfg.textLabel}`, true);
            }
            // every route answers with `text`; the per-node field name is there
            // too, and reading only that one is how this broke for notes
            const saved = result.text ?? result[cfg.textField] ?? "";
            catalog.text = { ...catalog.text, [name]: saved };
            editing(false);
            refresh(node);
            say(node, saved ? `${cfg.textLabel} saved` : `${cfg.textLabel} cleared`);
        };
        editButton.onclick = () => (field.style.display === "none" ? editing(true) : commit());
        field.onkeydown = (ev) => {
            ev.stopPropagation();
            if (ev.key === "Enter") commit();
            if (ev.key === "Escape") editing(false);
        };
        field.onkeyup = (ev) => ev.stopPropagation();

        const w = node.addDOMWidget(`ns_${cfg.kind}_panel`, "panel", panel, { serialize: false });
        w.computeSize = () => [node.size?.[0] || 380, node._nsAssetHeight || 300];
        node._nsAssetPanel = panel;
        sizePanel(node);
    }

    /* ------------------------------------------------------------ extension */

    app.registerExtension({
        name: `Neons.${cfg.extension}`,

        async setup() {
            await loadCatalog();
            for (const node of app.graph?._nodes || []) {
                if ((node.comfyClass || node.type) === cfg.node) refresh(node);
            }
        },

        async beforeRegisterNodeDef(nodeType, nodeData) {
            if (nodeData?.name !== cfg.node) return;

            const onNodeCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function () {
                const result = onNodeCreated?.apply(this, arguments);
                attachPanel(this);
                if (!catalog.ready) loadCatalog().then(() => refresh(this));
                else refresh(this);
                for (const name of [cfg.picker, ...(cfg.strengthMode ? ["random_roll"] : [])]) {
                    const found = widget(this, name);
                    if (!found || found._nsHooked) continue;
                    found._nsHooked = true;
                    const original = found.callback;
                    found.callback = (...args) => {
                        const out = original?.apply(found, args);
                        if (name === "random_roll") syncStrengthMode(this);
                        refresh(this);
                        return out;
                    };
                }
                syncStrengthMode(this);
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
                requestAnimationFrame(() => {
                    fitNode(this);
                    syncStrengthMode(this);   // a saved workflow may have it on
                });
                return result;
            };

            const onDrawForeground = nodeType.prototype.onDrawForeground;
            nodeType.prototype.onDrawForeground = function (ctx) {
                const result = onDrawForeground?.apply(this, arguments);
                // last_y only exists after a draw pass, so the first one settles
                // the layout and every one after holds it
                if (!this._nsAssetSized && this._nsAssetPanel) {
                    this._nsAssetSized = true;
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
                    { content: `Neons: browse ${cfg.plural}`, callback: () => openBrowser(this) },
                    { content: `Neons: save last image to this ${cfg.singular}`, callback: () => saveLatest(this) },
                    {
                        content: `Neons: rescan the ${cfg.folder} folder`,
                        callback: async () => {
                            await loadCatalog(true);
                            refresh(this);
                        },
                    },
                );
            };
        },
    });
}
