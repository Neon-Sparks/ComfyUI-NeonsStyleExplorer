"""Attack the node's HTTP routes the way a hostile page or request would.

    python tools/security_probe.py        (needs aiohttp, which ComfyUI ships)

Stands up a real aiohttp app carrying every route __init__.py registers, with
stub `server` and `folder_paths` modules, then checks that each thing a request
must not be able to do is refused. It exits non-zero if any check fails.

It runs against a throwaway COPY of the package, never this folder: loading the
package for real moves previews into `user/`, and some of these requests are
destructive on purpose, so pointing it at a working install would cost data.
"""

import asyncio
import importlib.util
import io
import os
import shutil
import sys
import tempfile
import types

SOURCE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.join(tempfile.mkdtemp(prefix="ns_probe_pkg_"), "package")
shutil.copytree(SOURCE, ROOT, ignore=shutil.ignore_patterns(
    ".git", "user", "previews", "tools", "tests", "screenshots", "__pycache__", "*.md"))

from aiohttp import web  # noqa: E402
from aiohttp.test_utils import TestClient, TestServer  # noqa: E402

OUTPUT = tempfile.mkdtemp(prefix="ns_probe_out_")
SECRET = os.path.join(os.path.dirname(OUTPUT), "ns_probe_secret.txt")

routes = web.RouteTableDef()
server_stub = types.ModuleType("server")
server_stub.PromptServer = type("PromptServer", (), {
    "instance": type("Instance", (), {"routes": routes, "last_prompt_id": "probe"})()})
sys.modules["server"] = server_stub

LORAS = ["krea 2/portraits/soft_light.safetensors", "loose.safetensors"]
folder_paths = types.ModuleType("folder_paths")
folder_paths.get_directory_by_type = lambda kind: OUTPUT
folder_paths.get_output_directory = lambda: OUTPUT
folder_paths.get_filename_list = lambda kind: list(LORAS) if kind == "loras" else []
folder_paths.get_full_path = lambda kind, name: None
sys.modules["folder_paths"] = folder_paths

spec = importlib.util.spec_from_file_location(
    "ns_probe_pkg", os.path.join(ROOT, "__init__.py"), submodule_search_locations=[ROOT])
package = importlib.util.module_from_spec(spec)
sys.modules["ns_probe_pkg"] = package
spec.loader.exec_module(package)

FAILED = []


def check(label, passed, detail=""):
    print(f"  {'ok     ' if passed else 'PROBLEM'} {label}{'  — ' + str(detail) if detail and not passed else ''}")
    if not passed:
        FAILED.append(label)


def seed_preview(style):
    """Give one style a real preview, so a wipe would have something to take."""
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (64, 64), (90, 120, 150)).save(buffer, "PNG")
    return package.gallery.add_shot(package.catalog.resolve(style), buffer.getvalue())


async def main():
    app = web.Application()
    app.add_routes(routes)
    style = package.catalog.written_names("style")[0]
    seeded = seed_preview(style)
    hidden_before = package.catalog.load_hidden()
    with open(SECRET, "w", encoding="utf-8") as handle:
        handle.write("not yours")

    async with TestClient(TestServer(app)) as client:
        async def post(path, body, headers=None):
            response = await client.post(path, json=body, headers=headers or {})
            try:
                payload = await response.json()
            except Exception:
                payload = {}
            return response.status, payload

        posts = sorted({route.resource.canonical for route in app.router.routes()
                        if route.method == "POST"})
        gets = sorted({route.resource.canonical for route in app.router.routes()
                       if route.method == "GET"})
        print(f"{len(posts)} POST routes, {len(gets)} GET routes\n")

        print("cross-site requests")
        refused = []
        for path in posts:
            status, _ = await post(path, {}, {"Origin": "https://evil.example"})
            if status != 403:
                refused.append(f"{path} -> {status}")
        check(f"all {len(posts)} POST routes refuse another site's Origin", not refused, refused)
        host = f"127.0.0.1:{client.port}"
        status, _ = await post("/neons_style/roll", {}, {"Origin": f"http://{host}", "Host": host})
        check("the page's own Origin is accepted", status == 200, status)
        status, _ = await post("/neons_style/roll", {}, {"Origin": "null"})
        check("an opaque 'null' Origin (sandboxed frame, file://) is refused", status == 403, status)

        print("\npaths out of the output folder")
        escapes = [
            {"subfolder": "..", "filename": os.path.basename(SECRET)},
            {"subfolder": "../..", "filename": "anything"},
            {"subfolder": "", "filename": f"../{os.path.basename(SECRET)}"},
            {"subfolder": "", "filename": SECRET},
            {"subfolder": "..\\", "filename": os.path.basename(SECRET)},
        ]
        for extra, path in (({"style": style}, "/neons_style/gallery/save"),
                            ({"lora": LORAS[0]}, "/neons_lora/save")):
            leaked = []
            for escape in escapes:
                status, payload = await post(path, {**extra, **escape, "type": "output"})
                if payload.get("ok"):
                    leaked.append(escape)
            check(f"{path} cannot read outside the output folder", not leaked, leaked)

        print("\nnames the server did not list")
        status, payload = await post("/neons_lora/save", {
            "lora": "../../etc/shadow", "filename": "x.png", "subfolder": "", "type": "output"})
        check("saving against an invented LoRA is refused", not payload.get("ok"), payload)
        status, payload = await post("/neons_lora/text", {"lora": "not/a/real.safetensors", "text": "x"})
        check("trigger words for an invented LoRA are refused", not payload.get("ok"), payload)
        status, payload = await post("/neons_lora/favourite", {"lora": "not/a/real.safetensors", "on": True})
        check("starring an invented LoRA is refused", not payload.get("ok"), payload)
        status, payload = await post("/neons_model/text", {"model": "checkpoints/none.safetensors", "text": "x"})
        check("notes for an invented model are refused", not payload.get("ok"), payload)
        status, payload = await post("/neons_model/favourite", {"model": "checkpoints/none.safetensors"})
        check("starring an invented model is refused", not payload.get("ok"), payload)

        print("\nserving previews")
        for path in ("/neons_style/shot?key=../../../secret&file=../../x.jpg",
                     "/neons_lora/shot?gallery=../..&key=x&file=../../x.jpg",
                     "/neons_model/shot?gallery=..%5C..&key=x&file=..%5C..%5Cx.jpg",
                     f"/neons_lora/shot?gallery=x&key=x&file={SECRET}"):
            response = await client.get(path)
            check(f"GET {path.split('?')[0]} with a traversal answers 404",
                  response.status == 404, response.status)

        print("\nmalformed bodies")
        crashed = []
        for path in posts:
            if path.endswith("/catalogs/import"):      # multipart, not JSON
                continue
            for body in ([1, 2], "text", None, 7):
                response = await client.post(path, json=body)
                if response.status >= 500:
                    crashed.append(f"{path} <- {body!r}: {response.status}")
        check("no POST route answers a non-object body with a server error", not crashed, crashed[:6])

        print()
        print("requests that say nothing")
        # every POST route has just been sent an empty body, several times
        check("an empty request cannot wipe the gallery",
              package.gallery.has_shots(style) and bool(seeded))
        status, payload = await post("/neons_style/gallery/delete_family", {"family": ""})
        check("deleting every preview has to be asked for outright",
              not payload.get("ok") and package.gallery.has_shots(style), payload)
        status, payload = await post("/neons_style/gallery/delete_family", {"family": "", "all": True})
        check("and still works when it is", payload.get("ok") and not package.gallery.has_shots(style),
              payload)

    os.remove(SECRET)
    shutil.rmtree(os.path.dirname(ROOT), ignore_errors=True)
    shutil.rmtree(OUTPUT, ignore_errors=True)
    print(f"\nsecurity probe: {'clean' if not FAILED else str(len(FAILED)) + ' problem(s)'}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
