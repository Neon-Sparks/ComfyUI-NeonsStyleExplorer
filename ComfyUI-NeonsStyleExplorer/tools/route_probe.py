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
