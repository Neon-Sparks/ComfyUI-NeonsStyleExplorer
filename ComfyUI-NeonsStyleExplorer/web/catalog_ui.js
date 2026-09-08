import { ensureCss } from "./css.js";
import {
    clearRecents,
    createCatalogSet,
    deleteCatalogSet,
    deleteAllShots,
    deleteFamilyShots,
    deleteStyleShots,
    entryOf,
    exportStyles,
    isFavourite,
    hideStyle,
    importStyles,
    loadCatalog,
    loadCatalogSets,
    loadGallery,
    loadHidden,
    loadTags,
    namesOf,
    renameCatalogSet,
    restoreAllStyles,
    restoreStyle,
    starStyle,
    revertOverride,
    saveCustom,
    saveOverride,
    shotUrl,
    shotsOf,
    state,
    useCatalogSet,
} from "./api.js";

const AXES = ["style", "format", "finish"];
const CARD_MIN = 190;
const CARD_GAP = 12;
const BODY_H = 84;

export function closeAll() {
    document.getElementById("ns-overlay")?.remove();
    document.getElementById("ns-modal")?.remove();
    document.querySelector(".ns-menu")?.remove();
}

/**
 * Anchor rectangle for a menu: the button that opened it when we can find one,
 * otherwise a point at the cursor. Passing an element and passing an event both
 * have to work — an element has no clientX, and reading it produced NaN and
 * dumped the menu in the top-left corner.
 */
function anchorRect(source) {
    const element = source instanceof Element
        ? source
        : (source?.currentTarget instanceof Element
            ? source.currentTarget
            : (source?.target instanceof Element ? source.target.closest("button, select, a") : null));
    if (element) return element.getBoundingClientRect();
    const x = Number(source?.clientX) || 0;
    const y = Number(source?.clientY) || 0;
    return { left: x, right: x, top: y, bottom: y, width: 0, height: 0 };
}

export function menu(event, items) {
    document.querySelector(".ns-menu")?.remove();
    ensureCss();
    const box = document.createElement("div");
    box.className = "ns-menu";
    for (const item of items) {
        if (item === "-") {
            box.appendChild(document.createElement("hr"));
            continue;
        }
        const button = document.createElement("button");
        button.textContent = item.label;
        if (item.bad) button.className = "bad";
        if (item.disabled) {
            button.disabled = true;
            button.style.opacity = ".4";
        }
        button.onclick = async () => {
            box.remove();
            await item.run?.();
        };
        box.appendChild(button);
    }
    document.body.appendChild(box);
    const rect = box.getBoundingClientRect();
    const anchor = anchorRect(event);
    const GAP = 6;
    // sit just above the trigger, right edges aligned; drop below only when
    // there is no room above
    let top = anchor.top - rect.height - GAP;
    if (top < 8) top = Math.min(anchor.bottom + GAP, window.innerHeight - rect.height - 8);
    let left = (anchor.right || anchor.left) - rect.width;
    left = Math.max(8, Math.min(left, window.innerWidth - rect.width - 8));
    box.style.left = `${left}px`;
    box.style.top = `${Math.max(8, top)}px`;
    const away = (ev) => {
        if (!box.contains(ev.target)) {
            box.remove();
            window.removeEventListener("mousedown", away, true);
        }
    };
    setTimeout(() => window.addEventListener("mousedown", away, true), 0);
}

/* ------------------------------------------------------------- editor */

export async function openEditor(opts = {}) {
    ensureCss();
    document.getElementById("ns-modal")?.remove();
    await loadCatalog();
    const vocab = await loadTags();

    const creating = Boolean(opts.create);
    const name = opts.name || "";
    const entry = (!creating && entryOf(name)) || {};
    const source = entry.source || (creating ? "custom" : "shipped");
    const isCustom = source === "custom" || creating;
    const families = state.catalog.family_order || ["Other"];

    const wrap = document.createElement("div");
    wrap.className = "ns-modal";
    wrap.id = "ns-modal";
    const card = document.createElement("div");
    card.className = "card";
    card.innerHTML = `
      <h3>${creating ? "New style" : "Edit style"}</h3>
      <p class="hint">${
          creating
              ? "Stored in user/custom.json. Shipped files are never written."
              : isCustom
              ? "Custom style in user/custom.json."
              : "Saving writes a local override; Revert restores the shipped clause."
      }</p>
      <label>Name</label><input id="ns-name" ${creating ? "" : "readonly"}>
      <div class="cols">
        <div><label>Family</label><select id="ns-family"></select></div>
        <div><label>Axis</label><select id="ns-axis"></select></div>
        <div><label>Closing medium</label><input id="ns-medium" placeholder="anime style image"></div>
      </div>
      <label>Style clause — describe only the rendering, end with the medium</label>
      <textarea id="ns-nl" rows="4"></textarea>
      <label>Avoid terms (natural language)</label>
      <textarea id="ns-neg" rows="2"></textarea>
      <div class="cols">
        <div><label>Booru tags</label><input id="ns-tags" list="ns-vocab"></div>
        <div><label>Booru negative tags</label><input id="ns-ntags" list="ns-vocab"></div>
      </div>
      <datalist id="ns-vocab"></datalist>
      <div class="err" id="ns-err"></div>
      <div class="btns"></div>
    `;
    wrap.appendChild(card);
    document.body.appendChild(wrap);
    const $ = (sel) => card.querySelector(sel);

    families.forEach((family) => $("#ns-family").add(new Option(family, family)));
    AXES.forEach((axis) => $("#ns-axis").add(new Option(axis, axis)));
    vocab.slice(0, 4000).forEach((tag) => $("#ns-vocab").appendChild(new Option(tag)));

    $("#ns-name").value = creating ? "" : name;
    $("#ns-family").value = families.includes(entry.family) ? entry.family : families[0];
    $("#ns-axis").value = entry.axis || "style";
    $("#ns-medium").value = entry.medium || "";
    $("#ns-nl").value = entry.nl || "";
    $("#ns-neg").value = entry.negative || "";
    $("#ns-tags").value = (entry.tags || []).join(", ");
    $("#ns-ntags").value = (entry.tags_negative || []).join(", ");

    const btns = card.querySelector(".btns");
    const add = (label, className, run) => {
        const button = document.createElement("button");
        button.textContent = label;
        if (className) button.className = className;
        button.onclick = run;
        btns.appendChild(button);
    };
    const collect = () => ({
        name: $("#ns-name").value,
        family: $("#ns-family").value,
        axis: $("#ns-axis").value,
        medium: $("#ns-medium").value,
        nl: $("#ns-nl").value,
        negative: $("#ns-neg").value,
        tags: $("#ns-tags").value.split(",").map((t) => t.trim()).filter(Boolean),
        tags_negative: $("#ns-ntags").value.split(",").map((t) => t.trim()).filter(Boolean),
    });

    add("Save", "key", async () => {
        $("#ns-err").textContent = "";
        const body = collect();
        const bad = [...body.tags, ...body.tags_negative].filter((t) => vocab.length && !vocab.includes(t));
        if (bad.length) {
            $("#ns-err").textContent = `Not real booru tags: ${bad.join(", ")}`;
            return;
        }
        const result = creating || isCustom
            ? await saveCustom({ ...body, update: !creating })
            : await saveOverride(body);
        if (!result?.ok) {
            $("#ns-err").textContent = result?.error || "Save failed";
            return;
        }
        await loadCatalog();
        wrap.remove();
        opts.onSaved?.(result.name || name);
    });
    if (!creating && source === "override") {
        add("Revert", "", async () => {
            await revertOverride(name);
            await loadCatalog();
            wrap.remove();
            opts.onSaved?.(name);
        });
    }
    if (!creating && name) {
        add("Delete", "bad", async () => {
            if (!confirm(isCustom ? "Delete this custom style?" : "Hide this style from the catalog?")) return;
            await hideStyle(name);
            await loadCatalog();
            wrap.remove();
            opts.onSaved?.("");
            await document.getElementById("ns-overlay")?._nsRefreshHidden?.();
        });
    }
    add("Cancel", "", () => wrap.remove());
    wrap.addEventListener("mousedown", (ev) => {
        if (ev.target === wrap) wrap.remove();
    });
    $("#ns-nl").focus();
}

/* ------------------------------------------------------------ catalog */

export async function openCatalog(options = {}) {
    ensureCss();
    closeAll();
    await Promise.all([loadCatalog(), loadGallery(), loadCatalogSets()]);

    const overlay = document.createElement("div");
    overlay.className = "ns-overlay";
    overlay.id = "ns-overlay";
    overlay.innerHTML = `
      <div class="ns-scroll">
        <div class="ns-banner"><img src="/neons_style/banner" alt=""></div>
        <div class="ns-tools">
          <strong>Neons Style Explorer</strong>
          <span class="n"></span>
          <input type="search" placeholder="Search name, family or tag   ( / )">
          <select class="axis"></select>
          <select class="family"><option value="">All families</option></select>
          <select class="have">
            <option value="all">All</option>
            <option value="fav">&#9733; Favourites</option>
            <option value="recent">Recently used</option>
            <option value="has">Has preview</option>
            <option value="missing">Missing preview</option>
          </select>
          <select class="src">
            <option value="">Any source</option>
            <option value="shipped">Stock</option>
            <option value="v2">v2</option>
            <option value="custom">Custom</option>
            <option value="override">Override</option>
          </select>
          <span class="ns-sep"></span>
          <label class="ns-cat">Catalog
            <select class="catset" title="Which preview catalog images are saved to and shown from"></select>
          </label>
          <button class="catnew" title="Start a new, empty preview catalog">+ New catalog</button>
          <button class="catedit icon" title="Rename or delete this catalog">&#8943;</button>
          <span class="ns-sep"></span>
          <button class="roll">Roll</button>
          <button class="hidden-styles">Restore deleted</button>
          <button class="new key">New style</button>
          <button class="io">Import / export</button>
          <button class="wipe">Delete family thumbs</button>
          <button class="close">Close</button>
        </div>
        <div class="ns-viewport"><div class="ns-cards"></div></div>
      </div>
      <div class="ns-foot"><span class="clause"></span><span class="cov"></span></div>
    `;
    document.body.appendChild(overlay);

    const scroll = overlay.querySelector(".ns-scroll");
    const viewport = overlay.querySelector(".ns-viewport");
    const cards = overlay.querySelector(".ns-cards");
    const foot = overlay.querySelector(".clause");
    const cov = overlay.querySelector(".cov");
    const counter = overlay.querySelector(".n");
    const search = overlay.querySelector("input[type=search]");
    const axisSel = overlay.querySelector(".axis");
    const famSel = overlay.querySelector(".family");
    const haveSel = overlay.querySelector(".have");
    const srcSel = overlay.querySelector(".src");

    AXES.forEach((axis) => axisSel.add(new Option(`${axis}s`, axis)));
    axisSel.value = options.axis || "style";
    (state.catalog.family_order || []).forEach((family) => famSel.add(new Option(family, family)));

    const coverage = state.catalog.coverage || { total: 0, written: 0 };
    cov.textContent = `${coverage.written} / ${coverage.total} hand-written`;

    let rows = [];
    let layout = { columns: 1, cardW: CARD_MIN, cardH: CARD_MIN + BODY_H, rows: 0 };
    const mounted = new Map();

    function filter() {
        const query = search.value.trim().toLowerCase();
        rows = namesOf(axisSel.value)
            .map((name) => ({ name, entry: entryOf(name) || {}, shots: shotsOf(name) }))
            .filter(({ name, entry, shots }) => {
                if (famSel.value && entry.family !== famSel.value) return false;
                if (srcSel.value && (entry.source || "shipped") !== srcSel.value) return false;
                if (haveSel.value === "has" && !shots) return false;
                if (haveSel.value === "missing" && shots) return false;
                if (haveSel.value === "fav" && !isFavourite(name)) return false;
                if (haveSel.value === "recent" && !(state.recents || []).includes(name)) return false;
                if (!query) return true;
                const hay = `${name} ${entry.family || ""} ${(entry.aliases || []).join(" ")} ${(entry.tags || []).join(" ")}`;
                return hay.toLowerCase().includes(query);
            });
        counter.textContent = `${rows.length} of ${namesOf(axisSel.value).length}`;
        measure();
    }

    function measure() {
        const width = viewport.clientWidth - 32;
        const columns = Math.max(1, Math.floor((width + CARD_GAP) / (CARD_MIN + CARD_GAP)));
        const cardW = Math.floor((width - CARD_GAP * (columns - 1)) / columns);
        const cardH = cardW + BODY_H;
        layout = { columns, cardW, cardH, rows: Math.ceil(rows.length / columns) };
        cards.style.height = `${layout.rows * (cardH + CARD_GAP)}px`;
        for (const node of mounted.values()) node.remove();
        mounted.clear();
        render();
    }

    function card(index) {
        const { name, entry, shots } = rows[index];
        const node = document.createElement("div");
        node.className = `ns-card${name === options.current ? " on" : ""}`;
        node.dataset.name = name;
        const source = entry.source || "shipped";
        const starred = isFavourite(name);
        node.innerHTML = `
          <div class="pic">
            ${shots
                ? `<img loading="lazy" decoding="async" draggable="false" src="${shotUrl(name, shots.cover)}" alt="">
                   ${shots.count > 1 ? `<span class="cnt">${shots.count}</span>` : ""}
                   <button class="killshot" type="button" title="Delete this preview">&#10005;</button>`
                : `<div class="empty">no preview</div>`}
            <button class="star${starred ? " on" : ""}" type="button"
                    title="${starred ? "Remove from favourites" : "Add to favourites"}">${starred ? "&#9733;" : "&#9734;"}</button>
          </div>
          <div class="body">
            <div class="ttl"></div>
            <div class="meta">
              <span class="pill ${source}">${source === "shipped" ? "stock" : source}</span>
              ${entry.written ? "" : `<span class="pill draft">draft</span>`}
              <span class="sp"></span>
              <button class="use key" type="button">Use</button>
              <button class="edit" type="button">Edit</button>
            </div>
          </div>
        `;
        node.querySelector(".ttl").textContent = name;
        node.querySelector(".pic").style.height = `${layout.cardW}px`;
        node.addEventListener("mouseenter", () => {
            foot.textContent = entry.nl || "";
        });
        const pick = () => {
            options.onPick?.(name, axisSel.value);
            closeAll();
        };
        node.querySelector(".star")?.addEventListener("click", async (ev) => {
            ev.preventDefault();
            ev.stopPropagation();
            await starStyle(name);
            filter();
        });
        node.querySelector(".killshot")?.addEventListener("click", async (ev) => {
            ev.preventDefault();
            ev.stopPropagation();
            if (!confirm(`Delete the preview for ${name}?`)) return;
            await deleteStyleShots(name);
            await loadGallery();
            filter();
        });
        node.querySelector(".edit")?.addEventListener("click", (ev) => {
            ev.preventDefault();
            ev.stopPropagation();
            openEditor({ name, onSaved: () => filter() });
        });
        node.querySelector(".use")?.addEventListener("click", (ev) => {
            ev.preventDefault();
            ev.stopPropagation();
            pick();
        });
        // any other part of the card — thumbnail included — selects the style
        node.addEventListener("click", (ev) => {
            if (ev.target.closest("button")) return;
            pick();
        });
        return node;
    }

    function render() {
        const top = scroll.scrollTop - viewport.offsetTop;
        const rowH = layout.cardH + CARD_GAP;
        const first = Math.max(0, Math.floor(top / rowH) - 2);
        const last = Math.min(
            layout.rows - 1,
            Math.ceil((top + scroll.clientHeight) / rowH) + 2
        );
        const needed = new Set();
        for (let row = first; row <= last; row++) {
            for (let col = 0; col < layout.columns; col++) {
                const index = row * layout.columns + col;
                if (index >= rows.length) break;
                needed.add(index);
                if (mounted.has(index)) continue;
                const node = card(index);
                node.style.width = `${layout.cardW}px`;
                node.style.height = `${layout.cardH}px`;
                node.style.left = `${col * (layout.cardW + CARD_GAP)}px`;
                node.style.top = `${row * rowH}px`;
                cards.appendChild(node);
                mounted.set(index, node);
            }
        }
        for (const [index, node] of [...mounted.entries()]) {
            if (!needed.has(index)) {
                node.remove();
                mounted.delete(index);
            }
        }
    }

    scroll.addEventListener("scroll", render, { passive: true });
    const observer = new ResizeObserver(() => measure());
    observer.observe(viewport);

    [search, axisSel, famSel, haveSel, srcSel].forEach((control) => {
        control.addEventListener("input", filter);
        control.addEventListener("change", filter);
    });

    const hiddenButton = overlay.querySelector(".hidden-styles");
    const refreshHiddenCount = async () => {
        const data = await loadHidden();
        const count = data?.count || 0;
        // always visible: hiding it is what made the feature undiscoverable
        hiddenButton.textContent = count ? `Restore deleted (${count})` : "Restore deleted";
        hiddenButton.classList.toggle("key", count > 0);
        return data?.hidden || [];
    };
    overlay._nsRefreshHidden = refreshHiddenCount;
    hiddenButton.onclick = async (ev) => {
        const names = await refreshHiddenCount();
        if (!names.length) {
            menu(ev, [{ label: "Nothing deleted — the catalog is complete", disabled: true }]);
            return;
        }
        const items = [
            {
                label: `Restore all ${names.length} deleted styles`,
                run: async () => {
                    const result = await restoreAllStyles();
                    await loadCatalog();
                    await refreshHiddenCount();
                    filter();
                    alert(`Restored ${result?.restored ?? 0} styles.`);
                },
            },
            "-",
        ];
        for (const name of names.slice(0, 40)) {
            items.push({
                label: `Restore ${name}`,
                run: async () => {
                    await restoreStyle(name);
                    await loadCatalog();
                    await refreshHiddenCount();
                    filter();
                },
            });
        }
        if (names.length > 40) {
            items.push({ label: `…and ${names.length - 40} more (use Restore all)`, disabled: true });
        }
        menu(ev, items);
    };
    refreshHiddenCount();

    overlay.querySelector(".close").onclick = closeAll;
    overlay.querySelector(".new").onclick = () => openEditor({ create: true, onSaved: () => filter() });
    overlay.querySelector(".roll").onclick = () => {
        if (!rows.length) return;
        const pick = rows[Math.floor(Math.random() * rows.length)];
        options.onPick?.(pick.name, axisSel.value);
        closeAll();
    };
    /* ------------------------------------------------ catalog picker */
    const catSel = overlay.querySelector(".catset");

    function paintCatalogs() {
        const { active, items } = state.catalogs;
        catSel.innerHTML = items
            .map((item) => `<option value="${item.id}"${item.id === active ? " selected" : ""}>`
                + `${item.name}${item.shots ? ` (${item.shots})` : ""}</option>`)
            .join("");
    }
    paintCatalogs();

    async function switchTo(id) {
        await useCatalogSet(id);
        paintCatalogs();
        refreshAfterCatalogChange();
    }

    function refreshAfterCatalogChange() {
        // previews, favourites and recents all just changed underneath us
        filter();
    }

    catSel.onchange = () => switchTo(catSel.value);

    overlay.querySelector(".catnew").onclick = async () => {
        const name = prompt("Name the new catalog (for example: my Krea 2)", "");
        if (name === null) return;
        const label = name.trim();
        if (!label) return;
        await createCatalogSet(label);
        await loadCatalog();
        await loadGallery();
        paintCatalogs();
        refreshAfterCatalogChange();
    };

    overlay.querySelector(".catedit").onclick = (ev) => {
        const { active, items, name } = state.catalogs;
        const isDefault = active === "default";
        menu(ev.currentTarget, [
            {
                label: `Rename "${name}"…`,
                run: async () => {
                    const next = prompt("Rename this catalog", name);
                    if (next === null || !next.trim()) return;
                    await renameCatalogSet(active, next.trim());
                    paintCatalogs();
                },
            },
            {
                label: "Delete this catalog (keep the image files)",
                disabled: isDefault || items.length < 2,
                run: async () => {
                    if (!confirm(`Delete the catalog "${name}"? Its images stay on disk.`)) return;
                    await deleteCatalogSet(active, false);
                    await loadCatalog();
                    await loadGallery();
                    paintCatalogs();
                    refreshAfterCatalogChange();
                },
            },
            {
                label: "Delete this catalog AND its images",
                disabled: isDefault || items.length < 2,
                run: async () => {
                    if (!confirm(`Delete "${name}" and every preview image in it? This cannot be undone.`)) return;
                    await deleteCatalogSet(active, true);
                    await loadCatalog();
                    await loadGallery();
                    paintCatalogs();
                    refreshAfterCatalogChange();
                },
            },
        ]);
    };

    const wipeButton = overlay.querySelector(".wipe");
    const syncWipeLabel = () => {
        wipeButton.textContent = famSel.value ? `Delete ${famSel.value} previews` : "Delete all previews";
    };
    famSel.addEventListener("change", syncWipeLabel);
    syncWipeLabel();
    wipeButton.onclick = async () => {
        const stored = Object.keys(state.previews || {}).length;
        if (famSel.value) {
            if (!confirm(`Delete every gallery image for ${famSel.value}?`)) return;
            await deleteFamilyShots(famSel.value);
        } else {
            if (!confirm(`Delete ALL ${stored} style previews? This cannot be undone.`)) return;
            await deleteAllShots();
        }
        await loadGallery();
        filter();
    };
    overlay.querySelector(".io").onclick = (ev) =>
        menu(ev, [
            {
                label: "Export custom styles + overrides",
                run: async () => {
                    const data = await exportStyles();
                    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
                    const link = document.createElement("a");
                    link.href = URL.createObjectURL(blob);
                    link.download = "neons_styles.json";
                    link.click();
                },
            },
            {
                label: `Clear all favourites (${(state.favourites || []).length})`,
                disabled: !(state.favourites || []).length,
                run: async () => {
                    if (!confirm(`Remove all ${state.favourites.length} favourites?`)) return;
                    for (const name of [...state.favourites]) await starStyle(name);
                    filter();
                },
            },
            {
                label: "Clear recently-used list",
                run: async () => {
                    await clearRecents();
                    state.recents = [];
                    filter();
                },
            },
            {
                label: "Import a style pack…",
                run: () => {
                    const picker = document.createElement("input");
                    picker.type = "file";
                    picker.accept = "application/json";
                    picker.onchange = async () => {
                        const file = picker.files?.[0];
                        if (!file) return;
                        const parsed = JSON.parse(await file.text());
                        const result = await importStyles(parsed.styles || parsed);
                        alert(`Imported ${result?.added ?? 0} styles.`);
                        await loadCatalog();
                        filter();
                    };
                    picker.click();
                },
            },
            "-",
            {
                label: "Delete gallery images for the current style",
                bad: true,
                disabled: !options.current,
                run: async () => {
                    if (!confirm(`Delete gallery images for ${options.current}?`)) return;
                    await deleteStyleShots(options.current);
                    await loadGallery();
                    filter();
                },
            },
        ]);

    const keys = (ev) => {
        if (ev.key === "Escape") {
            closeAll();
            window.removeEventListener("keydown", keys, true);
            observer.disconnect();
        } else if (ev.key === "/" && document.activeElement !== search) {
            ev.preventDefault();
            search.focus();
        }
    };
    window.addEventListener("keydown", keys, true);

    filter();
    search.focus();
}
