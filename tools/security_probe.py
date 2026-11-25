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

        print("\nstyle explorer 2")
        v2 = importlib.import_module("ns_probe_pkg.explorer2")
        shipped = v2.catalog()["styles"][0]
        from PIL import Image as _ProbeImage

        _ProbeImage.new("RGB", (64, 64), (10, 80, 120)).save(os.path.join(OUTPUT, "probe.png"))
        leaked = []
        for escape in escapes:
            status, payload = await post("/neons_style2/preview/save",
                                         {"id": shipped["id"], **escape, "type": "output"})
            if payload.get("ok"):
                leaked.append(escape)
        check("/neons_style2/preview/save cannot read outside the image folders", not leaked, leaked)
        status, payload = await post("/neons_style2/preview/save", {
            "id": shipped["id"], "filename": "probe.png", "type": "../../etc"})
        check("an invented folder type is refused", not payload.get("ok"), payload)
        status, payload = await post("/neons_style2/preview/save", {
            "id": "../../../etc/passwd", "filename": "probe.png", "type": "output"})
        check("a preview cannot be filed under an invented style", not payload.get("ok"), payload)
        status, payload = await post("/neons_style2/preview/save", {
            "id": shipped["id"], "filename": "probe.png", "type": "output"})
        landed = v2.preview_path(shipped["id"])
        check("a real image is saved, inside the previews folder",
              payload.get("ok") and landed and os.path.dirname(os.path.realpath(landed))
              == os.path.realpath(v2.PREVIEWS), payload)
        for query in ("id=../../../secret", f"id={SECRET}", "id=..%5C..%5Cx&size=256",
                      "id=", "size=../../x"):
            response = await client.get(f"/neons_style2/preview?{query}")
            check(f"GET /neons_style2/preview?{query.split('=')[0]}=<traversal> answers 404",
                  response.status == 404, response.status)
        response = await client.get(f"/neons_style2/preview?id={shipped['id']}")
        check("a preview is served as an image and never sniffed",
              response.status == 200 and response.headers.get("X-Content-Type-Options") == "nosniff"
              and response.headers.get("Content-Type") == "image/jpeg", dict(response.headers))
        status, payload = await post("/neons_style2/custom/save", {"style": {
            "name": "../../evil<script>", "lead": "x" * 100000, "parts": ["y"] * 5000,
            "tags": ["../t"]}})
        made = v2.resolve(payload.get("name") or "")
        check("a hostile own style is cut down to plain text",
              bool(made) and len(made["lead"]) <= 120 and len(made["parts"]) <= v2.MAX_OWN_PARTS
              and all(len(part) <= 100 for part in made["parts"])
              and "<" not in made["name"] and "/" not in made["id"].split(".", 1)[1], payload)
        status, payload = await post("/neons_style2/custom/delete", {"name": shipped["name"]})
        check("a shipped style cannot be deleted through the own-style route",
              not payload.get("removed") and v2.resolve(shipped["name"]) is not None, payload)
        status, payload = await post("/neons_style2/collection", {"name": "../../x", "id": shipped["id"]})
        status, payload = await post("/neons_style2/collection", {"name": "y" * 5000, "id": ["a"]})
        stored = [name for name in os.listdir(v2.USER) if not name.startswith(".")]
        check("collections live in one state file, whatever they are called",
              sorted(stored) == ["custom.json", "previews", "state.json"], stored)
        status, payload = await post("/neons_style2/compose", {
            "styles": "@all, " + "x" * 100000, "prompt": "p" * 100000, "roll_seed": "1e999",
            "strength": {"a": 1}, "lighting": ["x"], "output_as": 7})
        check("compose with hostile values answers instead of failing",
              status == 200 and payload.get("ok") and len(payload.get("positive", "")) < 30000,
              (status, str(payload)[:100]))
        response = await client.get("/neons_style2/catalog")
        etag = response.headers.get("ETag")
        again = await client.get("/neons_style2/catalog", headers={"If-None-Match": etag or "x"})
        check("an unchanged catalog is answered with 304", bool(etag) and again.status == 304,
              again.status)

        print("\nthe style roller")
        status, payload = await post("/neons_roller/roll", {"count": 10 ** 9, "seed": 5})
        rolled = [part for part in str(payload.get("words", "")).split(", ") if part]
        check("a huge count is clamped to 50", status == 200 and len(rolled) == 50, len(rolled))
        hostile = {"count": "1e999", "seed": -5, "kind": {"a": 1}, "aspect": ["x"],
                   "vocabulary": "../../etc/passwd", "output_as": None, "weight": "nan",
                   "never_include": ["a"], "always_include": "x" * 200000}
        status, payload = await post("/neons_roller/roll", hostile)
        check("hostile values roll with defaults instead of failing",
              status == 200 and payload.get("ok"), (status, str(payload)[:120]))
        check("a pinned word cannot grow past its limit",
              len(str(payload.get("words", ""))) < 6000, len(str(payload.get("words", ""))))
        status, payload = await post("/neons_roller/roll", {
            "always_include": os.path.basename(SECRET), "vocabulary": SECRET, "kind": SECRET})
        check("a path in any field is only ever text",
              "not yours" not in str(payload), str(payload)[:120])
        started = asyncio.get_event_loop().time()
        status, payload = await post("/neons_roller/roll", {
            "count": 50, "seed": 3, "never_include": ", ".join(f"w{i}(a+)+$" for i in range(5000))})
        took = asyncio.get_event_loop().time() - started
        check("a huge never_include is answered quickly", status == 200 and took < 2.0,
              f"{took:.2f}s")

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
