const CSS = `
/* =========================== node panel =========================== */
/* The container itself is click-through so the node still drags from
   anywhere; only the controls take pointer events. */
/* every height here is set explicitly from panel.js, so nothing depends on a
   percentage resolving against an auto-height parent */
.ns-panel { width:100%; box-sizing:border-box; display:flex; flex-direction:column; gap:6px;
    font-family:Inter,"Segoe UI",sans-serif; pointer-events:none; overflow:hidden; }
.ns-stage { flex:0 0 auto; display:flex; align-items:center; justify-content:center; }
.ns-thumb { position:relative; flex:0 0 auto;
    border-radius:12px; overflow:hidden; background:#0c0d11;
    border:1px solid rgba(255,255,255,.09); box-shadow:0 8px 22px rgba(0,0,0,.35);
    cursor:pointer; pointer-events:auto; }
.ns-thumb img { position:absolute; inset:0; width:100%; height:100%; object-fit:contain;
    display:block; background:#0c0d11; pointer-events:none; -webkit-user-drag:none; user-select:none; }
.ns-thumb .ns-none { position:absolute; inset:0; display:flex; flex-direction:column; gap:4px;
    align-items:center; justify-content:center; text-align:center; padding:34px 14px 40px;
    color:#8f959f; font-size:12px; background:radial-gradient(circle at 50% 20%,#1b1d24,#0f1014); }
.ns-thumb .ns-name { position:absolute; left:0; right:0; bottom:0; padding:20px 10px 8px;
    background:linear-gradient(transparent,rgba(0,0,0,.88)); color:#fff; font-size:12px;
    font-weight:650; line-height:1.3; }
.ns-thumb .ns-chip { position:absolute; top:7px; left:7px; padding:2px 7px; border-radius:999px;
    font-size:10px; font-weight:700; background:rgba(0,0,0,.62); color:#dfe3ea;
    border:1px solid rgba(255,255,255,.14); }
.ns-shots { flex:0 0 auto; display:flex; gap:6px; overflow-x:auto; overflow-y:visible; padding:5px 2px 2px;
    pointer-events:auto; }
.ns-shots:empty { display:none; }
.ns-arrow { position:absolute; top:50%; transform:translateY(-50%); width:26px; height:34px; padding:0;
    display:none; align-items:center; justify-content:center; font-size:13px; line-height:1;
    border:1px solid rgba(255,255,255,.14); background:rgba(10,12,16,.62); color:#e7ebf2;
    border-radius:7px; cursor:pointer; opacity:.45; transition:opacity .12s, background .12s; z-index:3; }
.ns-thumb:hover .ns-arrow { opacity:1; }
.ns-arrow:hover { background:rgba(20,24,32,.9); }
.ns-arrow:disabled { opacity:.18; cursor:default; }
.ns-arrow.prev { left:6px; }
.ns-arrow.next { right:6px; }
.ns-shot { position:relative; flex:0 0 auto; }
.ns-shots .pick { display:block; width:36px; height:36px; padding:0; border-radius:7px;
    border:1px solid rgba(255,255,255,.12); background:#14161c; overflow:hidden; cursor:pointer; }
.ns-shot.on .pick { border-color:#7aa2ff; }
/* inside the tile: the strip scrolls, so anything hanging outside gets clipped */
.ns-shots .drop { position:absolute; top:1px; right:1px; width:14px; height:14px; padding:0; line-height:12px;
    font-size:9px; border-radius:50%; border:1px solid rgba(255,255,255,.25); background:rgba(30,16,20,.85);
    color:#f0b4b4; cursor:pointer; opacity:.75; transition:opacity .12s; }
.ns-shot:hover .drop { opacity:1; }
.ns-shots img { width:100%; height:100%; object-fit:cover; display:block; pointer-events:none; -webkit-user-drag:none; }
.ns-bar button.fav.on { color:#ffd66e; border-color:#6a5a2a; }
.ns-bar button:disabled { opacity:.4; cursor:default; }
/* overlaid on the preview, not in the flow: the panel height is measured, and a
   line that appears and disappears must not move the buttons */
.ns-say { position:absolute; left:0; right:0; top:0; display:none; z-index:4;
    padding:4px 8px; font-size:10px; line-height:1.35; color:#8de39b;
    background:rgba(6,8,12,.88); border-bottom:1px solid rgba(255,255,255,.08);
    overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.ns-say.bad { color:#f5b0b0; }
.ns-bar { flex:0 0 auto; display:flex; flex-wrap:wrap; gap:5px; pointer-events:auto; }
.ns-bar button { flex:1 1 76px; height:27px; padding:0 8px; font-size:11px; border-radius:7px;
    border:1px solid rgba(255,255,255,.12); background:#191b21; color:#e7e9ee; cursor:pointer;
    white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.ns-bar button:hover { background:#23262e; }
.ns-bar button.key { background:#2f5fd0; border-color:#5480ee; color:#fff; font-weight:600; }
.ns-bar button.key:hover { background:#3a6ce0; }
.ns-bar button.icon { flex:0 0 32px; padding:0; }
.ns-out { flex:0 0 auto; display:grid; grid-template-rows:auto minmax(0,1fr); gap:3px; pointer-events:auto; overflow:hidden; }
.ns-out header { display:flex; align-items:center; gap:8px; font-size:10px; letter-spacing:.06em;
    text-transform:uppercase; color:#8f959f; }
.ns-out header .sp { flex:1; }
.ns-out header button { height:20px; padding:0 7px; font-size:10px; border-radius:5px;
    border:1px solid rgba(255,255,255,.12); background:#191b21; color:#dcdfe5; cursor:pointer; }
.ns-out pre { margin:0; overflow:auto; white-space:pre-wrap; word-break:break-word;
    background:#0d0e12; border:1px solid rgba(255,255,255,.08); border-radius:9px; padding:7px 9px;
    font:11px/1.45 ui-monospace,SFMono-Regular,Menlo,monospace; color:#ccd1d9; }
.ns-out pre .neg { display:block; margin-top:6px; color:#e09a9a; }

/* ========================== catalog overlay ======================= */
.ns-overlay { position:fixed; inset:0; z-index:2147483646; background:#0e0f13; color:#e7e9ee;
    font-family:Inter,"Segoe UI",sans-serif; display:flex; flex-direction:column; }
.ns-scroll { flex:1 1 auto; min-height:0; overflow:auto; position:relative; }
.ns-banner { width:100%; display:block; }
.ns-banner img { width:100%; height:auto; max-height:none; object-fit:contain; display:block; }
.ns-tools { position:sticky; top:0; z-index:5; display:flex; flex-wrap:wrap; align-items:center;
    gap:8px; padding:10px 16px; background:rgba(18,19,24,.97); backdrop-filter:blur(8px);
    border-bottom:1px solid #262a34; }
.ns-tools strong { font-size:14px; letter-spacing:.01em; }
.ns-tools .n { font-size:12px; color:#868c96; }
.ns-tools input[type=search], .ns-tools select { height:32px; border-radius:8px; border:1px solid #333846;
    background:#0f1116; color:#e7e9ee; padding:0 10px; font-size:13px; }
.ns-tools input[type=search] { flex:1 1 200px; min-width:150px; }
.ns-cat { display:flex; align-items:center; gap:5px; font-size:11px; color:#8b93a1; white-space:nowrap; }
.ns-cat select { max-width:190px; }
.ns-sep { width:1px; align-self:stretch; margin:0 2px; background:rgba(255,255,255,.09); }
.ns-tools button.catnew { border-color:#3b5a8a; color:#bcd4ff; }
.ns-tools button { height:32px; padding:0 12px; border-radius:8px; border:1px solid #333846;
    background:#1b1e26; color:#e7e9ee; cursor:pointer; font-size:12px; }
.ns-tools button:hover { background:#242833; }
.ns-tools button.key { background:#2f5fd0; border-color:#5480ee; }
.ns-prompts { display:flex; align-items:center; gap:8px; flex-wrap:wrap; padding:7px 12px;
    border-bottom:1px solid rgba(255,255,255,.07); background:#15171d; }
.ns-modal label .sub { font-weight:400; color:#6b7280; font-size:10px; margin-left:4px; }
.ns-modal #ns-newfamily { margin-top:5px; }
.ns-famlist { display:flex; flex-direction:column; gap:6px; max-height:46vh; overflow:auto; margin:6px 0 10px; }
.ns-famlist .fam { display:flex; align-items:center; gap:8px; padding:6px 9px; border-radius:8px;
    border:1px solid #2a2d36; background:#15171d; font-size:12px; color:#d7dbe2; }
.ns-famlist .fam.locked { opacity:.6; }
.ns-famlist .fam.none { justify-content:center; color:#6b7280; font-style:italic; }
.ns-famlist .fam .n { font-weight:600; }
.ns-famlist .fam .c { color:#7b8290; font-size:11px; margin-right:auto; }
.ns-famlist .fam .tag { font-size:10px; color:#7b8290; border:1px solid #2f333d; border-radius:999px; padding:1px 7px; }
.ns-famlist .fam button { font-size:11px; padding:3px 9px; border-radius:7px; border:1px solid #333642;
    background:#1b1e26; color:#cfd3da; cursor:pointer; }
.ns-famlist .fam button.bad { color:#f0a0a0; border-color:#4a2b30; }
.ns-famlist .fam button.key { background:#2f5fd0; border-color:#5480ee; color:#fff; }
.ns-famlist .fam input.rename { flex:1; padding:4px 8px; font-size:12px; border-radius:7px;
    border:1px solid #3b5a8a; background:#10131a; color:#e7ebf2; }
.ns-card.compact .body { display:none; }
.ns-card.compact .pic .star, .ns-card.compact .pic .killshot { transform:scale(.8); }
.ns-zoom { display:flex; align-items:center; gap:5px; font-size:11px; color:#8b93a1; white-space:nowrap; }
.ns-zoom select { font-size:11px; }
.ns-prompts .sep { width:1px; align-self:stretch; background:rgba(255,255,255,.09); }
.ns-prompts .ttl { font-size:11px; font-weight:600; color:#8b93a1; letter-spacing:.2px; white-space:nowrap; }
.ns-prompts .list { display:flex; align-items:center; gap:6px; flex:1 1 260px; flex-wrap:wrap; min-width:0; }
.ns-prompts .none { font-size:11px; color:#5c626e; font-style:italic; }
.ns-prompts .p { max-width:100%; padding:3px 9px; border-radius:999px; border:1px solid #333642;
    background:#1b1e26; color:#cfd3da; font-size:11px; cursor:pointer; text-align:left;
    overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.ns-prompts .p:hover { background:#222630; }
.ns-prompts .p.on { border-color:#5480ee; background:#1e2740; color:#dce6ff; }
.ns-prompts button.addprompt, .ns-prompts button.delprompt { font-size:11px; padding:3px 10px;
    border-radius:7px; border:1px solid #333642; background:#1b1e26; color:#cfd3da; cursor:pointer; }
.ns-prompts button.addprompt { border-color:#3b5a8a; color:#bcd4ff; }
.ns-prompts button.delprompt:disabled { opacity:.35; cursor:default; }
.ns-prompts .promptbox { display:none; flex:1 1 240px; min-width:160px; padding:4px 8px; font-size:11px;
    border-radius:7px; border:1px solid #3b5a8a; background:#10131a; color:#e7ebf2; }
.ns-prompts .note { font-size:10px; color:#7fd08a; min-width:0; }
.ns-prompts .note.bad { color:#f0a0a0; }
.ns-viewport { position:relative; padding:14px 16px 24px; }
.ns-cards { position:relative; }
.ns-card { position:absolute; box-sizing:border-box; background:#161922; border:1px solid #262a34;
    border-radius:12px; overflow:hidden; cursor:pointer; display:flex; flex-direction:column; }
.ns-card:hover { border-color:#5480ee; }
.ns-card.on { border-color:#7aa2ff; box-shadow:inset 0 0 0 1px #7aa2ff; }
.ns-card .pic { position:relative; flex:0 0 auto; width:100%; background:#0d0e12; }
/* a draggable image turns a click into a drag, which is why cards with a
   preview could not be selected; take the image out of hit-testing entirely */
.ns-card .pic img { position:absolute; inset:0; width:100%; height:100%; object-fit:cover; display:block;
    pointer-events:none; -webkit-user-drag:none; user-select:none; }
.ns-card .pic .empty { position:absolute; inset:0; display:flex; align-items:center; justify-content:center;
    color:#585e68; font-size:11px; }
.ns-card .pic .cnt { position:absolute; right:6px; bottom:6px; padding:1px 6px; border-radius:999px;
    background:rgba(0,0,0,.66); font-size:10px; color:#dfe3ea; }
.ns-card .pic .star { position:absolute; top:5px; left:5px; width:22px; height:22px; padding:0; line-height:20px;
    font-size:13px; border-radius:50%; border:1px solid rgba(255,255,255,.16); background:rgba(0,0,0,.55);
    color:#cfd3da; cursor:pointer; opacity:0; transition:opacity .12s; }
.ns-card .pic .star { opacity:.6; }
.ns-card:hover .pic .star, .ns-card .pic .star.on { opacity:1; }
.ns-card .pic .star.on { color:#ffd66e; border-color:#6a5a2a; }
.ns-card .pic .killshot { position:absolute; top:5px; right:5px; width:22px; height:22px; padding:0; line-height:20px;
    font-size:11px; border-radius:50%; border:1px solid rgba(255,255,255,.16); background:rgba(0,0,0,.55);
    color:#f0b4b4; cursor:pointer; opacity:0; transition:opacity .12s; }
.ns-card .pic .killshot { opacity:.6; }
.ns-card:hover .pic .killshot { opacity:1; }
.ns-card .body { flex:1 1 auto; display:grid; grid-template-rows:minmax(0,1fr) auto; gap:6px;
    padding:8px 9px 9px; min-height:0; }
.ns-card .ttl { font-size:12px; font-weight:640; line-height:1.3; overflow:hidden;
    display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; word-break:break-word; }
.ns-card .meta { display:flex; align-items:center; gap:5px; }
.ns-card .pill { font-size:9px; letter-spacing:.04em; text-transform:uppercase; padding:2px 6px;
    border-radius:999px; background:#212632; color:#a9b1bf; white-space:nowrap; }
.ns-card .pill.v2 { background:#382d20; color:#e7d2b3; }
.ns-card .pill.custom { background:#1f3b2a; color:#bfe6c9; }
.ns-card .pill.override { background:#1f2c42; color:#bdd4f5; }
.ns-card .pill.draft { background:#3a2626; color:#f0bcbc; }
.ns-card .meta .sp { flex:1; }
.ns-card .meta button { font-size:10px; padding:3px 8px; border-radius:999px; border:1px solid #333846;
    background:#1b1e26; color:#ccd1d9; cursor:pointer; }
.ns-foot { flex:0 0 auto; display:flex; align-items:center; gap:10px; padding:8px 16px;
    border-top:1px solid #262a34; background:#121318; font-size:11px; color:#8f959f; min-height:34px; }
.ns-foot .clause { flex:1; color:#ccd1d9; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }

/* ============================== modal ============================= */
.ns-modal { position:fixed; inset:0; z-index:2147483647; background:rgba(5,6,9,.68); display:flex;
    align-items:center; justify-content:center; font-family:Inter,"Segoe UI",sans-serif; }
.ns-modal .card { width:min(780px,94vw); max-height:92vh; overflow:auto; background:#14161c;
    color:#e7e9ee; border:1px solid #2a2e39; border-radius:14px; padding:18px 20px;
    box-shadow:0 24px 60px rgba(0,0,0,.55); }
.ns-modal h3 { margin:0 0 4px; font-size:17px; }
.ns-modal p.hint { margin:0 0 12px; font-size:12px; color:#868c96; }
.ns-modal label { display:block; font-size:11px; letter-spacing:.05em; text-transform:uppercase;
    color:#8f959f; margin:12px 0 4px; }
.ns-modal input, .ns-modal select, .ns-modal textarea { width:100%; box-sizing:border-box;
    padding:8px 10px; border-radius:8px; border:1px solid #333846; background:#0f1116; color:#e7e9ee;
    font:13px/1.45 Inter,"Segoe UI",sans-serif; }
.ns-modal textarea { resize:vertical; }
.ns-modal .cols { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:10px; }
.ns-modal .err { min-height:16px; margin-top:10px; color:#e58a8a; font-size:12px; }
.ns-modal .btns { display:flex; flex-wrap:wrap; gap:8px; margin-top:14px; }
.ns-modal .btns button { height:34px; padding:0 14px; border-radius:8px; border:1px solid #333846;
    background:#1b1e26; color:#e7e9ee; cursor:pointer; font-size:13px; }
.ns-modal .btns button.key { background:#2f5fd0; border-color:#5480ee; }
.ns-modal .btns button.bad { background:#39201f; border-color:#6a3130; color:#f0c4c4; }
.ns-menu { position:fixed; z-index:2147483647; min-width:200px; padding:5px; border-radius:10px;
    background:#191b22; border:1px solid #2d313b; box-shadow:0 16px 38px rgba(0,0,0,.5); }
.ns-menu button { display:block; width:100%; text-align:left; padding:7px 10px; font-size:12px;
    border:0; border-radius:6px; background:transparent; color:#e0e3e9; cursor:pointer; }
.ns-menu button:hover { background:#262a34; }
.ns-menu button.bad { color:#f0a8a8; }
.ns-menu hr { border:0; border-top:1px solid #2b2f39; margin:4px 2px; }
`;

export function ensureCss() {
    let el = document.getElementById("ns-style-css");
    if (!el) {
        el = document.createElement("style");
        el.id = "ns-style-css";
        document.head.appendChild(el);
    }
    if (el.dataset.v !== "13") {
        el.textContent = CSS;
        el.dataset.v = "13";
    }
}
