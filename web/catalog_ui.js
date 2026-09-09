import { ensureCss } from "./css.js";
import {
    addCatalogPrompt,
    entryDetail,
    forgetDetail,
    gallerySignature,
    deleteFamily,
    isCustomFamily,
    loadFamilies,
    renameFamily,
    lastErrorText,
    clearRecents,
    createCatalogSet,
    deleteCatalogPrompt,
    deleteCatalogSet,
    deleteAllShots,
    deleteFamilyShots,
    deleteStyleShots,
    entryOf,
    exportStyles,
    isFavourite,
    hideStyle,
    importStyles,
    GALLERY_EVENT,
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
// preview size, as a percentage of the default card width
const ZOOMS = [25, 50, 75, 100, 125, 150, 200, 250, 300];
const ZOOM_KEY = "ns.catalog.zoom";

const VIEW_KEY = "ns.catalog.view";

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
        localStorage.setItem(VIEW_KEY, JSON.stringify(view));
    } catch (err) {
        /* private browsing, or a full quota: the browser just will not remember */
    }
}

function savedZoom() {
    const stored = Number(localStorage.getItem(ZOOM_KEY));
    return ZOOMS.includes(stored) ? stored : 100;
}

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

// A user-typed prompt goes into markup, so escape it. The apostrophe is written
// as \u0027 rather than a literal quote: a bare quote inside a character class
// confuses simple source scanners (ours included).
const HTML_ESCAPES = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "\"": "&quot;",
    "\u0027": "&#39;",
};

function escapeHtml(text) {
    return String(text ?? "").replace(/[&<>\u0022\u0027]/g, (ch) => HTML_ESCAPES[ch]);
}

/** True when a key event came from somewhere the user is typing. */
function typingIn(target) {
    const element = target instanceof Element ? target : null;
    if (!element) return false;
    return Boolean(element.closest("input, textarea, select, [contenteditable=\u0022true\u0022]"));
}

/**
 * Keep our own dialogs' keystrokes to ourselves.
 *
 * ComfyUI binds shortcuts on the canvas and on document level; a modal opened
 * over the node sits inside that, so single letters could reach the canvas
 * instead of the field being typed into. Propagation stops here — default
 * behaviour is untouched, so typing still types.
 */
function keepKeysLocal(element, onEscape) {
    for (const type of ["keydown", "keyup", "keypress"]) {
        element.addEventListener(type, (ev) => {
            if (ev.key === "Escape" && type === "keydown" && onEscape) {
                ev.preventDefault();
                onEscape();
            }
            ev.stopPropagation();
        }, true);
    }
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

/**
 * Manage the families the user added. Shipped families are listed but locked:
 * renaming one would orphan a thousand entries the node ships with.
 *
 * Deleting a family never deletes styles — they move to Lonely, the holding
 * family for styles with nowhere else to be.
 */
export async function openFamilies(opts = {}) {
    ensureCss();
    document.getElementById("ns-modal")?.remove();
    const data = await loadFamilies();
    const rows = data?.families || [];

    const wrap = document.createElement("div");
    wrap.className = "ns-modal";
    wrap.id = "ns-modal";
    const card = document.createElement("div");
    card.className = "card";
    card.innerHTML = `
      <h3>Families</h3>
      <p class="hint">Rename or remove the families you added. Deleting one moves its
      styles to <b>Lonely</b> rather than deleting them. The nine shipped families cannot be changed.</p>
      <div class="ns-famlist"></div>
      <div class="err" id="ns-err"></div>
      <div class="btns"></div>
    `;
    wrap.appendChild(card);
    document.body.appendChild(wrap);
    keepKeysLocal(card, () => wrap.remove());

    const list = card.querySelector(".ns-famlist");
    function paint(current) {
        list.innerHTML = current
            .map((row) => `
              <div class="fam${row.shipped ? " locked" : ""}" data-name="${escapeHtml(row.name)}">
                <span class="n">${escapeHtml(row.name)}</span>
                <span class="c">${row.total} entr${row.total === 1 ? "y" : "ies"}${
                    row.mine ? `, ${row.mine} yours` : ""}</span>
                ${row.shipped
                    ? `<span class="tag">shipped</span>`
                    : `<button class="ren">Rename</button><button class="del bad">Delete</button>`}
              </div>`)
            .join("");
        list.querySelectorAll(".fam").forEach((element) => {
            const name = element.dataset.name;
            element.querySelector(".ren")?.addEventListener("click", () => {
                element.innerHTML = `
                  <input class="rename" value="${escapeHtml(name)}" maxlength="40">
                  <button class="save key">Save</button><button class="cancel">Cancel</button>`;
                const field = element.querySelector(".rename");
                field.focus();
                const commit = async () => {
                    const next = field.value.trim();
                    if (!next || next === name) return paint(current);
                    const result = await renameFamily(name, next);
                    if (!result?.ok) {
                        card.querySelector("#ns-err").textContent = result?.error || "could not rename";
                        return paint(current);
                    }
                    current = result.families || current;
                    paint(current);
                    opts.onChanged?.();
                };
                element.querySelector(".save").onclick = commit;
                element.querySelector(".cancel").onclick = () => paint(current);
                field.onkeydown = (ev) => {
                    if (ev.key === "Enter") commit();
                    if (ev.key === "Escape") paint(current);
                };
            });
            element.querySelector(".del")?.addEventListener("click", async () => {
                if (!confirm(`Delete the family "${name}"? Its styles move to Lonely.`)) return;
                const result = await deleteFamily(name);
                if (!result?.ok) {
                    card.querySelector("#ns-err").textContent = result?.error || "could not delete";
                    return;
                }
                current = result.families || current;
                paint(current);
                opts.onChanged?.();
            });
        });
        if (!current.some((row) => !row.shipped)) {
            list.insertAdjacentHTML("beforeend",
                `<div class="fam none">You have not added any families yet.</div>`);
        }
    }
    paint(rows);

    const close = document.createElement("button");
    close.textContent = "Close";
    close.onclick = () => wrap.remove();
    card.querySelector(".btns").appendChild(close);
    wrap.addEventListener("mousedown", (ev) => {
        if (ev.target === wrap) wrap.remove();
    });
}

/* ------------------------------------------------------------- editor */

export async function openEditor(opts = {}) {
    ensureCss();
    document.getElementById("ns-modal")?.remove();
    await loadCatalog();
    const vocab = await loadTags();

    const creating = Boolean(opts.create);
    const name = opts.name || "";
    const entry = (!creating && (await entryDetail(name)) ) || (!creating && entryOf(name)) || {};
    const source = entry.source || (creating ? "custom" : "shipped");
    const isCustom = source === "custom" || creating;
    // imported packs are not a home for your own styles, so they are not
    // offered here — they still appear in the browser's family filter
    const families = (state.catalog.family_order || ["Other"])
        .filter((family) => !(state.catalog.imported_families || []).includes(family));

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
      <label>Name${creating ? "" : ` <span class="sub">rename freely — the old name keeps working, and previews stay attached</span>`}</label>
      <input id="ns-name">
      <div class="cols">
        <div><label>Family</label>
          <select id="ns-family"></select>
          <input id="ns-newfamily" placeholder="new family name" maxlength="40" style="display:none">
        </div>
        <div><label>Axis</label><select id="ns-axis"></select></div>
        <div><label>Closing medium</label><input id="ns-medium" placeholder="anime style image"></div>
      </div>
      <label>Style clause — describe only the rendering, end with the medium</label>
      <textarea id="ns-nl" rows="4"></textarea>
      <label>Avoid terms (natural language)</label>
      <textarea id="ns-neg" rows="2"></textarea>
      <div class="cols">
        <div><label>Booru tags <span class="sub">comma separated, any tag you like</span></label>
          <input id="ns-tags" list="ns-vocab" autocomplete="off"></div>
        <div><label>Booru negative tags <span class="sub">comma separated</span></label>
          <input id="ns-ntags" list="ns-vocab" autocomplete="off"></div>
      </div>
      <datalist id="ns-vocab"></datalist>
      <div class="err" id="ns-err"></div>
      <div class="btns"></div>
    `;
    wrap.appendChild(card);
    document.body.appendChild(wrap);
    keepKeysLocal(card, () => wrap.remove());
    const $ = (sel) => card.querySelector(sel);

    const NEW_FAMILY = "+ add a new family…";
    families.forEach((family) => $("#ns-family").add(new Option(family, family)));
    $("#ns-family").add(new Option(NEW_FAMILY, NEW_FAMILY));
    const newFamily = $("#ns-newfamily");
    $("#ns-family").addEventListener("change", () => {
        const adding = $("#ns-family").value === NEW_FAMILY;
        newFamily.style.display = adding ? "block" : "none";
        if (adding) newFamily.focus();
    });
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
        // `name` identifies the entry to change; `rename` is what to call it.
        // With an editable name field those are two different things — sending
        // the typed value as the key would look up a style that does not exist.
        name: creating ? $("#ns-name").value : name,
        rename: creating ? "" : $("#ns-name").value.trim(),
        family: $("#ns-family").value === "+ add a new family…"
            ? $("#ns-newfamily").value.trim()
            : $("#ns-family").value,
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
        // The vocabulary is a suggestion list, not a gate: models understand
        // plenty of tags that are not in it, and refusing to save was stopping
        // people writing the tags they actually wanted.
        const unlisted = [...body.tags, ...body.tags_negative]
            .filter((tag) => vocab.length && !vocab.includes(tag));
        if (unlisted.length) {
            console.log(`Neons Style Explorer: saving ${unlisted.length} tag(s) not in the suggestion list`);
        }
        if (!body.family) {
            $("#ns-err").textContent = "Name the new family, or pick an existing one.";
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
        forgetDetail(name);
        forgetDetail(result.name || name);
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
          <input type="search" placeholder="Search name, family or tag   ( / )" title="Matches the name, the family and the booru tags. Press / from anywhere in the browser to jump here.">
          <select class="axis" title="Which axis to browse: styles, picture formats, or finishes laid over a style"></select>
          <select class="family" title="Narrow to one family. Choose the — my families — heading to see every style in a family you made."><option value="">All families</option></select>
          <select class="have" title="Show everything, only your favourites, what you have used recently, or by whether a preview exists">
            <option value="all">All</option>
            <option value="fav">&#9733; Favourites</option>
            <option value="recent">Recently used</option>
            <option value="has">Has preview</option>
            <option value="missing">Missing preview</option>
          </select>
          <select class="src" title="Where an entry came from: shipped with the node, the v2 set, written by you, or edited by you">
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
          <button class="roll" title="Jump to a random card from whatever is currently filtered">Roll</button>
          <button class="hidden-styles" title="Styles you deleted are hidden, not destroyed — bring any of them back">Restore deleted</button>
          <button class="new key" title="Write your own style: a clause, a family, tags. Saved to user/custom.json; shipped files are never touched.">New style</button>
          <button class="io" title="Back up or share your own styles, manage families, clear favourites and recents">Import / export</button>
          <button class="wipe">Delete family thumbs</button>
          <button class="close" title="Close the browser (Escape)">Close</button>
        </div>
        <div class="ns-prompts">
          <label class="ns-zoom">Preview size
            <select class="zoom" title="Size of the preview images in this grid"></select>
          </label>
          <span class="sep"></span>
          <span class="ttl">Prompt used for generating catalog</span>
          <span class="list"></span>
          <input class="promptbox" type="text" placeholder="type the prompt, then Enter" maxlength="800">
          <button class="addprompt">Add prompt</button>
          <button class="delprompt">Delete prompt</button>
          <span class="note"></span>
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
    // shipped families first, then the user's own under one heading — with a
    // single option that gathers every custom family together
    const ALL_CUSTOM = "\u0000custom";
    function paintFamilies() {
        const current = famSel.value;
        const order = state.catalog.family_order || [];
        const shipped = order.filter((family) => !isCustomFamily(family));
        const mine = order.filter((family) => isCustomFamily(family));
        famSel.innerHTML = `<option value="">All families</option>`;
        for (const family of shipped) famSel.add(new Option(family, family));
        if (mine.length) {
            famSel.add(new Option("— my families —", ALL_CUSTOM));
            for (const family of mine) famSel.add(new Option(`  ${family}`, family));
        }
        famSel.value = [...famSel.options].some((option) => option.value === current) ? current : "";
    }
    paintFamilies();

    const coverage = state.catalog.coverage || { total: 0, written: 0 };
    cov.textContent = `${coverage.written} / ${coverage.total} hand-written`;

    let rows = [];
    let zoom = savedZoom();
    let layout = { columns: 1, cardW: CARD_MIN, cardH: CARD_MIN + BODY_H, rows: 0 };
    const mounted = new Map();

    function filter() {
        const query = search.value.trim().toLowerCase();
        rows = namesOf(axisSel.value)
            .map((name) => ({ name, entry: entryOf(name) || {}, shots: shotsOf(name) }))
            .filter(({ name, entry, shots }) => {
                if (famSel.value === ALL_CUSTOM) {
                    if (!isCustomFamily(entry.family)) return false;
                } else if (famSel.value && entry.family !== famSel.value) {
                    return false;
                }
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
        const target = Math.max(60, Math.round(CARD_MIN * (zoom / 100)));
        // at 300% a card can be wider than the window; never ask for more
        // columns than fit, and never fewer than one
        const columns = Math.max(1, Math.min(
            Math.floor((width + CARD_GAP) / (target + CARD_GAP)) || 1,
            rows.length || 1
        ));
        // cards fill the row, but never stretch far past the size asked for —
        // otherwise 300% on a wide window lands nearer 400%
        const cardW = Math.min(
            Math.floor((width - CARD_GAP * (columns - 1)) / columns),
            Math.round(target * 1.25)
        );
        // the body keeps its type size, so it must not scale with the picture —
        // below 60% it would dwarf the thumbnail, so the grid goes picture-only
        const cardH = cardW + (zoom < 60 ? 0 : BODY_H);
        layout = { columns, cardW, cardH, rows: Math.ceil(rows.length / columns) };
        cards.style.height = `${layout.rows * (cardH + CARD_GAP)}px`;
        for (const node of mounted.values()) node.remove();
        mounted.clear();
        render();
    }

    /** Everything worth knowing about an entry, for the hover tooltip. */
    function cardTooltip(name, entry, shots) {
        const lines = [name];
        const facts = [entry.family, entry.axis];
        if (entry.medium) facts.push(`closes with "${entry.medium}"`);
        lines.push(facts.filter(Boolean).join("  ·  "));
        if (entry.nl) lines.push("", entry.nl);
        if (entry.negative) lines.push("", `avoids: ${entry.negative}`);
        const tags = (entry.tags || []).join(", ");
        if (tags) lines.push("", `tags: ${tags}`);
        if ((entry.tags_negative || []).length) {
            lines.push(`negative tags: ${entry.tags_negative.join(", ")}`);
        }
        const bits = [];
        bits.push(shots ? `${shots.count} preview${shots.count === 1 ? "" : "s"}` : "no preview yet");
        bits.push(isFavourite(name) ? "favourite" : "not a favourite");
        bits.push(entry.source === "shipped" ? "ships with the node"
            : entry.source === "custom" ? "yours"
            : entry.source === "override" ? "edited by you"
            : String(entry.source || ""));
        if ((entry.aliases || []).length) bits.push(`also known as ${entry.aliases.join(", ")}`);
        lines.push("", bits.filter(Boolean).join("  ·  "));
        lines.push("", "Click to use  ·  Edit to change  ·  ★ to favourite  ·  ✕ to delete its preview");
        return lines.join("\n");
    }

    function card(index) {
        const { name, entry, shots } = rows[index];
        const node = document.createElement("div");
        node.className = `ns-card${name === options.current ? " on" : ""}${zoom < 60 ? " compact" : ""}`;
        node.title = cardTooltip(name, entry, shots);
        // the clause arrives with the first hover, then the tooltip is complete
        node.addEventListener("mouseenter", async () => {
            if (node.dataset.full) return;
            const full = await entryDetail(name);
            if (!full) return;
            node.dataset.full = "1";
            node.title = cardTooltip(name, { ...entry, ...full }, shots);
        }, { once: false });
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
              <button class="use key" type="button" title="Select this style on the node and close the browser">Use</button>
              <button class="edit" type="button" title="Change the name, clause, family, medium and tags">Edit</button>
            </div>
          </div>
        `;
        node.querySelector(".ttl").textContent = name;
        node.querySelector(".pic").style.height = `${layout.cardW}px`;
        node.addEventListener("mouseenter", () => {
            // the clause is not in the light index; fetch it, and only paint if
            // the pointer is still on this card when it arrives
            foot.textContent = "";
            entryDetail(name).then((full) => {
                if (full && node.matches(":hover")) foot.textContent = full.nl || "";
            });
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

    // Redraw as previews arrive. Saves land one at a time during a crawl, so
    // this is coalesced rather than re-rendering the grid on every image, and
    // the scroll position is preserved so a grid you are reading does not jump.
    let scrollTimer = 0;
    let galleryTimer = 0;
    const onGallery = () => {
        clearTimeout(galleryTimer);
        galleryTimer = setTimeout(() => {
            const top = scroll.scrollTop;
            filter();
            scroll.scrollTop = top;
        }, 250);
    };
    window.addEventListener(GALLERY_EVENT, onGallery);

    // A save made anywhere else — the capture node, another browser tab — never
    // reaches this page as an event, so poll gently while the browser is open.
    // loadGallery() fires the same event, so the redraw path stays single.
    let lastSig = "";
    const poll = setInterval(async () => {
        if (document.hidden) return;
        const sig = await gallerySignature();
        if (!sig || sig === lastSig) return;   // nothing has changed: no redraw
        lastSig = sig;
        loadGallery();
    }, 10000);

    // restore the previous visit before wiring the change handlers
    const view = savedView();
    const restore = (control, value) => {
        if (value === undefined || value === null) return;
        if ([...control.options].some((option) => option.value === value)) control.value = value;
    };
    restore(axisSel, view.axis);
    restore(famSel, view.family);
    restore(haveSel, view.have);
    restore(srcSel, view.src);
    if (typeof view.search === "string") search.value = view.search;

    const remember = () => saveView({
        axis: axisSel.value, family: famSel.value, have: haveSel.value,
        src: srcSel.value, search: search.value, scroll: scroll.scrollTop,
    });
    scroll.addEventListener("scroll", () => {
        clearTimeout(scrollTimer);
        scrollTimer = setTimeout(remember, 400);
    });

    [search, axisSel, famSel, haveSel, srcSel].forEach((control) => {
        control.addEventListener("change", remember);
        control.addEventListener("input", remember);
    });

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
    overlay.querySelector(".new").onclick = () => openEditor({
        create: true,
        onSaved: (saved) => {
            filter();
            // opened from a node: hand the new style straight back to it
            if (saved && options.onPick) {
                options.onPick(saved, "style");
                closeAll();
            }
        },
    });
    overlay.querySelector(".roll").onclick = () => {
        if (!rows.length) return;
        const pick = rows[Math.floor(Math.random() * rows.length)];
        options.onPick?.(pick.name, axisSel.value);
        closeAll();
    };
    /* ------------------------------------------------ catalog picker */
    const zoomSel = overlay.querySelector(".zoom");
    zoomSel.innerHTML = ZOOMS
        .map((value) => `<option value="${value}"${value === zoom ? " selected" : ""}>${value}%</option>`)
        .join("");
    zoomSel.onchange = () => {
        zoom = Number(zoomSel.value) || 100;
        localStorage.setItem(ZOOM_KEY, String(zoom));
        for (const node of mounted.values()) node.remove();
        mounted.clear();
        measure();
        render();
        scroll.scrollTop = 0;   // the row a position pointed at no longer exists
    };

    const catSel = overlay.querySelector(".catset");

    /* ------------------------------------ the catalog's generation prompts */
    const promptList = overlay.querySelector(".ns-prompts .list");
    const delPromptButton = overlay.querySelector(".delprompt");
    let activePrompt = "";

    function currentSet() {
        return state.catalogs.items.find((item) => item.id === state.catalogs.active);
    }

    function paintPrompts() {
        const prompts = currentSet()?.prompts || [];
        if (!prompts.includes(activePrompt)) activePrompt = prompts[0] || "";
        promptList.innerHTML = prompts.length
            ? prompts
                  .map((text, index) =>
                      `<button class="p${text === activePrompt ? " on" : ""}" data-i="${index}"
                               title="Click to select, then Delete prompt">${escapeHtml(text)}</button>`)
                  .join("")
            : `<span class="none">none saved yet — add the prompt these previews were generated with</span>`;
        promptList.querySelectorAll(".p").forEach((button, index) => {
            button.onclick = () => {
                activePrompt = prompts[index];
                paintPrompts();
            };
        });
        delPromptButton.disabled = !prompts.length;
    }

    // An inline field rather than window.prompt(): the browser silently
    // suppresses dialogs once a page has opened a few of them, and a swallowed
    // prompt() looks exactly like "saving is broken".
    const promptBox = overlay.querySelector(".promptbox");
    const addPromptButton = overlay.querySelector(".addprompt");
    const promptNote = overlay.querySelector(".note");

    function note(text, bad = false) {
        promptNote.textContent = text || "";
        promptNote.classList.toggle("bad", Boolean(bad));
        if (text) setTimeout(() => { promptNote.textContent = ""; }, 2600);
    }

    function editing(on) {
        promptBox.style.display = on ? "block" : "none";
        addPromptButton.textContent = on ? "Save prompt" : "Add prompt";
        if (on) promptBox.focus();
        else promptBox.value = "";
    }
    editing(false);

    async function commitPrompt() {
        const text = promptBox.value.trim();
        if (!text) {
            editing(false);
            return;
        }
        const result = await addCatalogPrompt(state.catalogs.active, text);
        if (result?.ok) {
            activePrompt = text;
            editing(false);
            paintPrompts();
            note("saved");
        } else {
            note(lastErrorText("could not save that prompt"), true);
        }
    }

    addPromptButton.onclick = () => {
        if (promptBox.style.display === "none") editing(true);
        else commitPrompt();
    };
    promptBox.onkeydown = (ev) => {
        if (ev.key === "Enter") {
            ev.preventDefault();
            commitPrompt();
        } else if (ev.key === "Escape") {
            ev.preventDefault();
            ev.stopPropagation();   // keep Escape from closing the browser
            editing(false);
        }
    };

    delPromptButton.onclick = async () => {
        if (!activePrompt) return;
        const result = await deleteCatalogPrompt(state.catalogs.active, activePrompt);
        if (result?.ok) {
            activePrompt = "";
            paintPrompts();
            note("removed");
        } else {
            note(lastErrorText("could not remove that prompt"), true);
        }
    };

    function paintCatalogs() {
        const { active, items } = state.catalogs;
        catSel.innerHTML = items
            .map((item) => `<option value="${item.id}"${item.id === active ? " selected" : ""}>`
                + `${item.name}${item.shots ? ` (${item.shots})` : ""}</option>`)
            .join("");
    }
    paintCatalogs();
    paintPrompts();

    async function switchTo(id) {
        await useCatalogSet(id);
        paintCatalogs();
        paintPrompts();
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
        paintPrompts();
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
                    paintPrompts();
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
                    paintPrompts();
                    refreshAfterCatalogChange();
                },
            },
        ]);
    };

    const wipeButton = overlay.querySelector(".wipe");
    const syncWipeLabel = () => {
        const label = famSel.value === ALL_CUSTOM ? "my families" : famSel.value;
        wipeButton.textContent = label ? `Delete ${label} previews` : "Delete all previews";
    };
    famSel.addEventListener("change", syncWipeLabel);
    syncWipeLabel();
    wipeButton.onclick = async () => {
        const stored = Object.keys(state.previews || {}).length;
        if (famSel.value && famSel.value !== ALL_CUSTOM) {
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
                label: "Manage my families…",
                run: () => openFamilies({ onChanged: async () => {
                    await loadCatalog();
                    paintFamilies();
                    filter();
                } }),
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
            clearTimeout(galleryTimer);
            clearInterval(poll);
            window.removeEventListener(GALLERY_EVENT, onGallery);
        } else if (ev.key === "/" && document.activeElement !== search && !typingIn(ev.target)) {
            ev.preventDefault();
            search.focus();
        }
    };
    window.addEventListener("keydown", keys, true);

    filter();
    // put the view back where it was: the grid has to exist and be measured
    // before a scroll offset means anything, hence the double frame
    if (view.scroll) {
        requestAnimationFrame(() => requestAnimationFrame(() => {
            scroll.scrollTop = Math.min(view.scroll, scroll.scrollHeight);
        }));
    }
    search.focus();
}
