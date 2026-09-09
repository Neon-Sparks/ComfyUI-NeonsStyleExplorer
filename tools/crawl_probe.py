"""Reproduce a crawl: N prompts, each a different style, each saving a preview.

Drives the real HTTP routes with a stub PromptServer, exactly as the browser
does: the node executes (which records the style server-side), then the client
posts that prompt's image to /gallery/save_run.
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
from PIL import Image  # noqa: E402

routes = web.RouteTableDef()
OUT = "/tmp/ns_probe_out"
os.makedirs(OUT, exist_ok=True)


class _Instance:
    routes = routes
    last_prompt_id = ""


instance = _Instance()
server_stub = types.ModuleType("server")
server_stub.PromptServer = type("PromptServer", (), {"instance": instance})
sys.modules["server"] = server_stub

folder_paths = types.ModuleType("folder_paths")
folder_paths.get_directory_by_type = lambda kind: OUT
folder_paths.get_output_directory = lambda: OUT
sys.modules["folder_paths"] = folder_paths

PKG = "ns_crawl"
spec = importlib.util.spec_from_file_location(
    PKG, os.path.join(ROOT, "__init__.py"), submodule_search_locations=[ROOT]
)
module = importlib.util.module_from_spec(spec)
sys.modules[PKG] = module
spec.loader.exec_module(module)

import importlib  # noqa: E402

nodes = importlib.import_module(f"{PKG}.nodes")
catalog = importlib.import_module(f"{PKG}.catalog")
gallery = importlib.import_module(f"{PKG}.gallery")
runs = importlib.import_module(f"{PKG}.runs")

MODE = os.environ.get("MODE", "every")
STEPS = int(os.environ.get("STEPS", "4"))


def fake_image(index):
    name = f"probe_{index:03d}.png"
    Image.new("RGB", (64, 64), (index * 40 % 255, 80, 160)).save(os.path.join(OUT, name))
    return {"filename": name, "subfolder": "", "type": "output"}


async def main():
    app = web.Application()
    app.add_routes(routes)
    client = TestClient(TestServer(app))
    await client.start_server()

    walk = catalog.crawl_names("all")[:STEPS]
    print(f"crawl of {STEPS} styles, auto_gallery={MODE}")
    node = nodes.NeonsStyleExplorer()

    for index, style in enumerate(walk):
        prompt_id = f"crawl-{index}"
        instance.last_prompt_id = prompt_id          # ComfyUI sets this per prompt
        node.apply(unique_id="7", prompt="a woman in a city street",
                   style=style, crawl=True, roll_scope="all", auto_gallery=MODE)
        image = fake_image(index)
        resp = await client.post("/neons_style/gallery/save_run",
                                 json={"prompt_id": prompt_id, "images": [image]})
        body = json.loads(await resp.text())
        saved = [entry["style"] for entry in body.get("saved", [])]
        print(f"  {index + 1}. queued {style!r:52} -> saved {saved or 'NOTHING'}"
              + ("" if body.get("ok") else f"  [{body.get('error')}]"))
        # the same prompt reported twice must not double-file or steal another
        # prompt's record
        again = await client.post("/neons_style/gallery/save_run",
                                  json={"prompt_id": prompt_id, "images": [image]})
        repeat = json.loads(await again.text())
        print(f"       repeat post -> {[e['style'] for e in repeat.get('saved', [])] or 'nothing'}"
              + ("" if repeat.get("ok") else f"  [{repeat.get('error')}]"))

    manifest = gallery.manifest()
    print(f"\nmanifest holds {len(manifest)} styles: "
          f"{[record.get('style') or key for key, record in list(manifest.items())[:6]]}")
    await client.close()


asyncio.run(main())

# clean every trace of the probe
for name in ("user/catalogs.json", "user/favourites.json", "user/recents.json"):
    path = os.path.join(ROOT, name)
    if os.path.isfile(path):
        os.remove(path)
shutil.rmtree(os.path.join(ROOT, "user", "catalogs"), ignore_errors=True)
shutil.rmtree(OUT, ignore_errors=True)
for name in os.listdir(os.path.join(ROOT, "previews")):
    if name != "README.md":
        target = os.path.join(ROOT, "previews", name)
        os.remove(target) if os.path.isfile(target) else shutil.rmtree(target, ignore_errors=True)
