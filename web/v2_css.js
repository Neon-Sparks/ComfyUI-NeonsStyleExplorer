/**
 * Neons Style Explorer 2 — styles for the node panel and the browser.
 *
 * Colours come from ComfyUI's own theme variables, so the browser follows a
 * light or dark theme; the one accent is a muted ochre.
 */
const CSS = `
.ns2 { --ns2-bg: var(--comfy-menu-bg, #1f2023); --ns2-panel: var(--comfy-input-bg, #2a2b2f);
    --ns2-fg: var(--input-text, #e6e3dc); --ns2-dim: var(--descrip-text, #9a978f);
    --ns2-line: var(--border-color, #3d3e43); --ns2-accent: #c9a25e; --ns2-accent-ink: #1d1a14;
    font-family: Inter, "Segoe UI", system-ui, sans-serif; color: var(--ns2-fg); }
.ns2 button, .ns2 input, .ns2 select, .ns2 textarea { font: inherit; color: inherit; }
.ns2 button { background: var(--ns2-panel); border: 1px solid var(--ns2-line); border-radius: 6px;
    padding: 5px 10px; cursor: pointer; line-height: 1.2; }
.ns2 button:hover { border-color: var(--ns2-accent); }
.ns2 button:focus-visible, .ns2 input:focus-visible, .ns2 select:focus-visible,
.ns2 textarea:focus-visible, .ns2 [tabindex]:focus-visible { outline: 2px solid var(--ns2-accent); outline-offset: 1px; }
.ns2 button.key { background: var(--ns2-accent); border-color: var(--ns2-accent); color: var(--ns2-accent-ink); font-weight: 650; }
.ns2 button:disabled { opacity: .45; cursor: default; border-color: var(--ns2-line); }
.ns2 input[type=text], .ns2 input[type=search], .ns2 select, .ns2 textarea {
    background: var(--ns2-panel); border: 1px solid var(--ns2-line); border-radius: 6px; padding: 6px 8px; }

/* ------------------------------ node panel ------------------------------ */
.ns2-panel { box-sizing: border-box; width: 100%; height: 132px; display: flex; gap: 10px; padding: 2px 0;
    overflow: hidden; font-size: 12px; }
.ns2-thumb { flex: 0 0 124px; height: 124px; border-radius: 8px; border: 1px solid var(--ns2-line);
    overflow: hidden; position: relative; cursor: pointer; display: flex; align-items: flex-end; }
.ns2-thumb img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; display: block; }
.ns2-thumb .ns2-ph { position: relative; padding: 8px; font-size: 11px; line-height: 1.3; color: #ebe7dd; opacity: .9; }
.ns2-info { flex: 1 1 auto; min-width: 0; display: flex; flex-direction: column; gap: 4px; }
.ns2-title { font-weight: 650; font-size: 13px; line-height: 1.25; overflow: hidden; display: -webkit-box;
    -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
.ns2-sub { color: var(--ns2-dim); line-height: 1.3; overflow: hidden; display: -webkit-box;
    -webkit-line-clamp: 3; -webkit-box-orient: vertical; flex: 1 1 auto; }
.ns2-note { color: var(--ns2-accent); }
.ns2-buttons { display: flex; flex-wrap: wrap; gap: 5px; }
.ns2-buttons button { padding: 4px 8px; font-size: 12px; }

/* ------------------------------- browser -------------------------------- */
.ns2-overlay { position: fixed; inset: 0; z-index: 10000; background: rgba(0,0,0,.55); display: flex;
    align-items: center; justify-content: center; }
.ns2-window { width: min(1500px, 96vw); height: min(940px, 94vh); background: var(--ns2-bg);
    border: 1px solid var(--ns2-line); border-radius: 12px; display: grid;
    grid-template-rows: auto 1fr; overflow: hidden; box-shadow: 0 24px 70px rgba(0,0,0,.5); font-size: 13px; }
.ns2-top { display: flex; align-items: center; gap: 10px; padding: 10px 14px; border-bottom: 1px solid var(--ns2-line); }
.ns2-top h2 { margin: 0 6px 0 0; font-size: 15px; font-weight: 650; white-space: nowrap; }
.ns2-top input[type=search] { flex: 1 1 260px; min-width: 120px; }
.ns2-top .ns2-count { color: var(--ns2-dim); white-space: nowrap; }
.ns2-top label { color: var(--ns2-dim); display: flex; align-items: center; gap: 6px; white-space: nowrap; }
.ns2-body { display: grid; grid-template-columns: 232px 1fr 340px; min-height: 0; }
.ns2-side { border-right: 1px solid var(--ns2-line); overflow-y: auto; padding: 8px; }
.ns2-side h3 { margin: 12px 6px 4px; font-size: 11px; font-weight: 650; text-transform: uppercase;
    letter-spacing: .06em; color: var(--ns2-dim); }
.ns2-row { display: flex; align-items: center; gap: 6px; width: 100%; text-align: left; border: 0 !important;
    background: transparent !important; padding: 5px 8px !important; border-radius: 6px; }
.ns2-row:hover { background: var(--ns2-panel) !important; }
.ns2-row.on { background: var(--ns2-panel) !important; box-shadow: inset 3px 0 0 var(--ns2-accent); }
.ns2-row span.n { margin-left: auto; color: var(--ns2-dim); font-size: 11px; font-variant-numeric: tabular-nums; }
.ns2-row.child { padding-left: 22px !important; font-size: 12px; }
.ns2-main { display: grid; grid-template-rows: auto 1fr; min-width: 0; min-height: 0; }
/* every trait is always in view: the bar grows to fit them and never scrolls */
.ns2-traits { display: flex; flex-wrap: wrap; gap: 4px 5px; padding: 8px 12px; border-bottom: 1px solid var(--ns2-line); }
.ns2-chip { border-radius: 999px !important; padding: 2px 9px !important; font-size: 11px; }
.ns2-chip.on { background: var(--ns2-accent) !important; border-color: var(--ns2-accent) !important; color: var(--ns2-accent-ink); }
.ns2-grid { position: relative; overflow-y: auto; min-height: 0; outline: none; }
.ns2-spacer { position: relative; width: 100%; }
.ns2-empty { padding: 40px 20px; color: var(--ns2-dim); text-align: center; }
.ns2-card { position: absolute; box-sizing: border-box; border: 1px solid var(--ns2-line); border-radius: 8px;
    overflow: hidden; cursor: pointer; background: var(--ns2-panel); display: flex; flex-direction: column; }
.ns2-card:hover { border-color: var(--ns2-dim); }
.ns2-card.sel { border-color: var(--ns2-accent); box-shadow: 0 0 0 2px var(--ns2-accent); }
.ns2-card .pic { flex: 1 1 auto; position: relative; min-height: 0; overflow: hidden; }
.ns2-card .pic img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; display: block; }
.ns2-card .pic .ph { position: absolute; inset: 0; padding: 10px; font-size: 11px; line-height: 1.35; color: #ebe7dd;
    opacity: .88; overflow: hidden; }
.ns2-card .cap { flex: 0 0 auto; padding: 6px 8px; display: flex; align-items: baseline; gap: 6px; }
.ns2-card .cap b { font-weight: 600; font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1 1 auto; }
.ns2-card .star, .ns2-card .mark { position: absolute; top: 5px; border-radius: 999px; font-size: 12px; line-height: 1;
    padding: 4px 6px; background: rgba(0,0,0,.55); color: #f1ede3; border: 0; }
.ns2-card .star { right: 5px; opacity: 0; }
.ns2-card:hover .star, .ns2-card .star.on { opacity: 1; }
.ns2-card .star.on { color: var(--ns2-accent); }
.ns2-card .mark { left: 5px; background: var(--ns2-accent); color: var(--ns2-accent-ink); font-weight: 700; }
.ns2-detail { border-left: 1px solid var(--ns2-line); overflow-y: auto; padding: 12px; display: flex;
    flex-direction: column; gap: 10px; }
.ns2-big { width: 100%; aspect-ratio: 1; border-radius: 8px; border: 1px solid var(--ns2-line); overflow: hidden;
    position: relative; flex: 0 0 auto; }
.ns2-big img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: contain; background: #111; }
.ns2-big .ph { position: absolute; inset: 0; padding: 16px; color: #ebe7dd; font-size: 13px; line-height: 1.45; }
.ns2-detail h3 { margin: 0; font-size: 16px; line-height: 1.25; }
.ns2-detail .where { color: var(--ns2-dim); font-size: 12px; }
.ns2-detail .lead { font-weight: 600; line-height: 1.4; }
.ns2-detail ol { margin: 0; padding-left: 20px; line-height: 1.5; }
.ns2-detail ol li.cut { border-bottom: 1px dashed var(--ns2-line); padding-bottom: 3px; margin-bottom: 3px; }
.ns2-detail .hint { color: var(--ns2-dim); font-size: 11px; line-height: 1.4; }
.ns2-detail .tags { display: flex; flex-wrap: wrap; gap: 4px; }
.ns2-detail .tags span { font-size: 11px; padding: 1px 7px; border-radius: 999px; border: 1px solid var(--ns2-line); color: var(--ns2-dim); }
.ns2-actions { display: flex; flex-wrap: wrap; gap: 6px; }
.ns2-tray { border-top: 1px solid var(--ns2-line); padding-top: 10px; display: flex; flex-direction: column; gap: 6px; margin-top: auto; }
.ns2-tray h4 { margin: 0; font-size: 12px; font-weight: 650; }
.ns2-pick { display: grid; grid-template-columns: 1fr 86px 34px 24px; gap: 6px; align-items: center; }
.ns2-pick .nm { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ns2-pick button { padding: 2px 6px; }
.ns2-out { font-family: ui-monospace, Consolas, monospace; font-size: 11px; line-height: 1.45; color: var(--ns2-dim);
    background: var(--ns2-panel); border: 1px solid var(--ns2-line); border-radius: 6px; padding: 7px 8px;
    max-height: 120px; overflow-y: auto; white-space: pre-wrap; word-break: break-word; }
.ns2-form { position: absolute; inset: 0; background: rgba(0,0,0,.5); display: flex; align-items: center; justify-content: center; z-index: 2; }
.ns2-form .box { width: min(560px, 92%); max-height: 90%; overflow-y: auto; background: var(--ns2-bg); border: 1px solid var(--ns2-line);
    border-radius: 10px; padding: 16px; display: flex; flex-direction: column; gap: 9px; }
.ns2-form label { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--ns2-dim); }
.ns2-form textarea { min-height: 120px; resize: vertical; }
.ns2-form .err { color: #d98a7a; min-height: 16px; font-size: 12px; }
/* the same form shown on its own, over the graph (the roller's "save as style") */
.ns2-overlay > .ns2-form { position: static; background: none; width: 100%; font-size: 13px; }
.ns2-menu { position: absolute; z-index: 3; background: var(--ns2-bg); border: 1px solid var(--ns2-line); border-radius: 8px;
    padding: 5px; display: flex; flex-direction: column; gap: 2px; min-width: 190px; max-height: 300px; overflow-y: auto;
    box-shadow: 0 10px 30px rgba(0,0,0,.4); }
@media (max-width: 1100px) { .ns2-body { grid-template-columns: 190px 1fr 290px; } }
@media (prefers-reduced-motion: no-preference) { .ns2-card { transition: border-color .12s; } }
`;

export function ensureCss() {
    if (document.getElementById("ns2-css")) return;
    const style = document.createElement("style");
    style.id = "ns2-css";
    style.textContent = CSS;
    document.head.append(style);
}
