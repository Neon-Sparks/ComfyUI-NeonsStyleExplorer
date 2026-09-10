"""Exercise the node's HTTP routes against a stub PromptServer.

Stands up a real aiohttp app carrying the routes __init__.py registers, so the
request/response path is tested the way ComfyUI drives it — not just the Python
functions underneath.
"""

import asyncio
import importlib.util
import json
import os
import shutil
import sys
import types

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ComfyUI-NeonsStyleExplorer")
sys.path.insert(0, os.path.dirname(ROOT))

from aiohttp import web  # noqa: E402
from aiohttp.test_utils import TestClient, TestServer  # noqa: E402

# --- stub the two ComfyUI modules the package imports -----------------------
routes = web.RouteTableDef()


class _Instance:
    routes = routes
    last_prompt_id = "probe-prompt-1"


server_stub = types.ModuleType("server")
server_stub.PromptServer = type("PromptServer", (), {"instance": _Instance()})
sys.modules["server"] = server_stub

folder_paths = types.ModuleType("folder_paths")
folder_paths.get_directory_by_type = lambda kind: "/tmp"
folder_paths.get_output_directory = lambda: "/tmp"
sys.modules["folder_paths"] = folder_paths

PKG = "ns_probe"
spec = importlib.util.spec_from_file_location(
    PKG, os.path.join(ROOT, "__init__.py"), submodule_search_locations=[ROOT]
)
module = importlib.util.module_from_spec(spec)
sys.modules[PKG] = module
spec.loader.exec_module(module)

print(f"routes registered: {len(routes)}")

# two handlers on one path silently shadow each other — aiohttp takes the first
seen = {}
clashes = []
for route in routes:
    key = (route.method, route.path)
    if key in seen:
        clashes.append(key)
    seen[key] = True
print("duplicate routes:", clashes or "none")


async def main():
    app = web.Application()
    app.add_routes(routes)
    client = TestClient(TestServer(app))
    await client.start_server()

    async def get(path):
        resp = await client.get(path)
        return resp.status, await resp.json()

    async def post(path, body):
        resp = await client.post(path, json=body)
        text = await resp.text()
        try:
            return resp.status, json.loads(text)
        except json.JSONDecodeError:
            return resp.status, text[:300]

    status, payload = await get("/neons_style/catalogs")
    print("GET  /catalogs           ", status, payload)

    status, payload = await post("/neons_style/catalogs/prompt",
                                 {"id": "default", "text": "a woman in a city street"})
    print("POST /catalogs/prompt add", status, payload)

    status, payload = await get("/neons_style/catalogs")
    print("GET  /catalogs           ", status, payload)

    status, payload = await post("/neons_style/catalogs/prompt",
                                 {"id": "default", "text": "a woman in a city street", "delete": True})
    print("POST /catalogs/prompt del", status, payload)

    # and the no-id case the UI hits before any catalog is chosen
    status, payload = await post("/neons_style/catalogs/prompt", {"text": "no id given"})
    print("POST /prompt (no id)     ", status, payload)

    print("\n-- security: cross-site POST")
    async def post_with_origin(path, body, origin):
        resp = await client.post(path, json=body, headers={"Origin": origin})
        text = await resp.text()
        try:
            return resp.status, json.loads(text)
        except json.JSONDecodeError:
            return resp.status, text[:120]

    host_origin = f"http://{client.host}:{client.port}"
    status, payload = await post_with_origin("/neons_style/catalogs/prompt",
                                             {"text": "from another site"}, "http://evil.example")
    print(f"   Origin: evil.example  -> {status} {payload.get('error') if isinstance(payload, dict) else payload}")
    status, payload = await post_with_origin("/neons_style/catalogs/prompt",
                                             {"text": "from the interface"}, host_origin)
    print(f"   Origin: the page      -> {status} ok={payload.get('ok') if isinstance(payload, dict) else payload}")
    status, payload = await post("/neons_style/catalogs/prompt", {"text": "no origin header", "delete": False})
    print(f"   no Origin (extension) -> {status} ok={payload.get('ok')}")
    await post("/neons_style/catalogs/prompt", {"text": "from another site", "delete": True})
    await post("/neons_style/catalogs/prompt", {"text": "from the interface", "delete": True})
    await post("/neons_style/catalogs/prompt", {"text": "no origin header", "delete": True})

    print("\n-- security: path traversal on the save routes")
    for folder, filename in [("../../..", "etc/passwd"), ("..", "secrets.txt"), ("", "probe_000.png")]:
        status, payload = await post("/neons_style/gallery/save", {
            "style": "[Anime] Chibi", "subfolder": folder, "filename": filename,
        })
        print(f"   subfolder={folder!r:14} filename={filename!r:16} -> {payload.get('ok')} {payload.get('error','')}")
    import importlib as _il2
    _runs = _il2.import_module(f"{PKG}.runs")
    _runs.record("probe-sec", "1", style="[Anime] Chibi", mode="every", prompt="")
    status, payload = await post("/neons_style/gallery/save_run", {
        "prompt_id": "probe-sec",
        "images": [{"filename": "passwd", "subfolder": "../../../etc", "type": "output"}],
    })
    print(f"   save_run traversal                             -> {payload.get('ok')} {payload.get('error','')}")

    print("\n-- performance routes")
    import json as _json
    status, payload = await get("/neons_style/catalog")
    print(f"   GET /catalog          {status}  {len(_json.dumps(payload))/1048576:.2f} MB")
    print(f"      by_name entry keys: {sorted(list(payload['by_name'].values())[0])}")
    name = payload["styles"][0]
    status, payload = await get(f"/neons_style/entry?name={name.replace(' ', '%20').replace('[','%5B').replace(']','%5D')}")
    entry = payload.get("entry") or {}
    print(f"   GET /entry            {status}  ok={payload.get('ok')} nl={str(entry.get('nl'))[:60]!r}")
    status, payload = await get("/neons_style/gallery/signature")
    print(f"   GET /gallery/signature {status}  {payload}")

    print("\n-- custom style into shipped families (via HTTP)")
    for fam in ("Anime & Manga", "Photography & Film", "Traditional Painting", "My Own Thing"):
        status, payload = await post("/neons_style/custom", {
            "name": f"Route Probe {fam[:5]}", "family": fam, "axis": "style",
            "nl": "Probe rendering: flat test clause, style image.", "medium": "style image",
            "tags": ["test_tag"], "tags_negative": [],
        })
        print(f"   {fam:22} -> {status} ok={payload.get('ok')} name={payload.get('name')!r} err={payload.get('error')!r}")
    full = os.path.join(ROOT, "user/custom.json")
    if os.path.isfile(full):
        os.remove(full)

    # families: create a custom style, rename its family, delete the family
    import importlib as _il
    store = _il.import_module(f"{PKG}.store")
    catalog = _il.import_module(f"{PKG}.catalog")
    for name in ("user/custom.json",):
        full = os.path.join(ROOT, name)
        if os.path.isfile(full):
            os.remove(full)
    ok, made = store.save_custom(name="Probe Figurine", family="Material Test", axis="style",
                                 nl="Probe rendering: matte resin cast, style image.", medium="style image")
    print("\n-- families")
    print("created                  ", made)
    status, payload = await get("/neons_style/families")
    print("GET  /families           ", status, [r for r in payload["families"] if not r["shipped"]])
    status, payload = await post("/neons_style/families/rename", {"old": "Material Test", "new": "Figurine"})
    print("POST /families/rename    ", status, payload["ok"], payload["moved"],
          [e["name"] for e in catalog.entries() if e.get("source") == "custom"])
    status, payload = await post("/neons_style/families/rename", {"old": "Anime & Manga", "new": "Nope"})
    print("POST rename shipped      ", status, payload["ok"], "|", payload["error"])
    status, payload = await post("/neons_style/families/delete", {"name": "Figurine"})
    print("POST /families/delete    ", status, payload["ok"], "->", payload["family"],
          [(e["name"], e["family"]) for e in catalog.entries() if e.get("source") == "custom"])
    full = os.path.join(ROOT, "user/custom.json")
    if os.path.isfile(full):
        os.remove(full)

    # the real-world case: an index written BEFORE prompts existed, and the
    # active catalog is a named one rather than the default
    legacy = {"active": "my-krea-2", "items": [
        {"id": "default", "name": "Default", "created": 0},
        {"id": "my-krea-2", "name": "my krea 2", "created": 1788000000},
    ]}
    index_path = os.path.join(ROOT, "user", "catalogs.json")
    with open(index_path, "w", encoding="utf-8") as handle:
        json.dump(legacy, handle)
    print("\n-- legacy index, active = my-krea-2")
    status, payload = await post("/neons_style/catalogs/prompt",
                                 {"id": "my-krea-2", "text": "krea prompt"})
    print("POST add (named)         ", status, payload)
    status, payload = await get("/neons_style/catalogs")
    print("GET  /catalogs           ", status, payload)
    with open(index_path, "r", encoding="utf-8") as handle:
        print("on disk:", handle.read().replace("\n", " ")[:220])

    await client.close()


asyncio.run(main())

for path in ("user/catalogs.json",):
    full = os.path.join(ROOT, path)
    if os.path.isfile(full):
        os.remove(full)
shutil.rmtree(os.path.join(ROOT, "user", "catalogs"), ignore_errors=True)
