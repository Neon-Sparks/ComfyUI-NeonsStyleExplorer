"""HTTP routes for Neons Style Explorer 2.

Registered from __init__.py with the helpers every other route in the pack
uses: *post* (a POST that refuses another site's Origin), *inside* (path
containment) and *data* (a JSON body that is always a dict).

Nothing here takes a file path from the browser except the one image a user
saves as a preview, and that one is held to ComfyUI's own output folders.
"""

import os


def register(routes, post, inside, data, web):
    from . import explorer2 as v2
    from . import nodes2

    HEADERS = {"X-Content-Type-Options": "nosniff"}

    def text(body, key, limit=400):
        value = body.get(key)
        return str(value)[:limit] if isinstance(value, (str, int, float)) else ""

    def number(body, key, fallback=0):
        try:
            return int(float(body.get(key)))
        except (TypeError, ValueError, OverflowError):
            return fallback

    def ok(**fields):
        return web.json_response({"ok": True, **fields})

    def fail(message):
        return web.json_response({"ok": False, "error": message})

    @routes.get("/neons_style2/catalog")
    async def get_catalog(request):
        """The whole catalog. It only changes when a style file does, so the
        browser keeps its copy and is told 'not modified' on every later open."""
        etag = f'"{v2.signature()}"'
        if request.headers.get("If-None-Match") == etag:
            return web.Response(status=304, headers={"ETag": etag})
        response = web.json_response(v2.payload(), headers={
            "ETag": etag, "Cache-Control": "no-cache", **HEADERS})
        response.enable_compression()
        return response

    @routes.get("/neons_style2/state")
    async def get_state(_request):
        v2.adopt_v1_previews()
        return web.json_response(v2.user_state(), headers={"Cache-Control": "no-store"})

    @routes.get("/neons_style2/preview")
    async def get_preview(request):
        size = request.query.get("size")
        path = v2.preview_path(request.query.get("id", "")[:200],
                               size if size in ("256", "384") else None)
        if not path:
            return web.Response(status=404)
        return web.FileResponse(path, headers={
            "Cache-Control": "public, max-age=31536000, immutable",
            "Content-Type": "image/jpeg", **HEADERS})

    @post("/neons_style2/compose")
    async def post_compose(request):
        """What the node would write with these settings; changes nothing."""
        body = await data(request)
        seed = number(body, "roll_seed")
        kwargs = {
            "prompt": text(body, "prompt", 20000),
            "prompt_prefix": text(body, "prompt_prefix", 4000),
            "negative": text(body, "negative", 20000),
            "styles": text(body, "styles", 2000),
            "strength": text(body, "strength", 20) or "standard",
            "output_as": text(body, "output_as", 40) or v2.OUTPUTS[0],
            "style_position": text(body, "style_position", 20) or v2.POSITIONS[0],
            "roll_seed": seed if 0 <= seed <= 0xFFFFFFFF else 0,
        }
        for kind in v2.MOD_KINDS:
            kwargs[kind] = text(body, kind, 60) or v2.NONE
        out = nodes2.run(claim=False, **kwargs)
        return ok(positive=out["positive"], negative=out["negative"], style=out["style"],
                  ids=[entry["id"] for entry, _w in out["picks"]],
                  names=[entry["name"] for entry, _w in out["picks"]],
                  mods=out["mod_names"], notes=out["notes"])

    @post("/neons_style2/favourite")
    async def post_favourite(request):
        body = await data(request)
        on = body.get("on")
        result = v2.set_favourite(text(body, "id", 200), None if on is None else bool(on))
        return fail("No such style.") if result is None else ok(on=result)

    @post("/neons_style2/collection")
    async def post_collection(request):
        body = await data(request)
        rename = body.get("rename")
        error = v2.collection_edit(
            text(body, "name", 60),
            ident=text(body, "id", 200) or None,
            on=body.get("on", True) is not False,
            delete=body.get("delete") is True,
            rename=text(body, "rename", 60) if rename is not None else None)
        return fail(error) if error else ok(collections=v2.state()["collections"])

    @post("/neons_style2/recents/clear")
    async def post_recents_clear(_request):
        v2.clear_recents()
        return ok()

    @post("/neons_style2/preview/save")
    async def post_preview_save(request):
        """File a generated image as a style's preview."""
        import folder_paths

        body = await data(request)
        entry = v2.resolve(text(body, "id", 200))
        if not entry:
            return fail("No such style.")
        if body.get("only_if_missing") is True and v2.has_preview(entry["id"]):
            return ok(kept=True, stamp=v2.previews().get(entry["id"], 0))
        kind = text(body, "type", 20) or "output"
        if kind not in ("output", "temp", "input"):
            return fail("That is not a folder images are saved in.")
        directory = folder_paths.get_directory_by_type(kind)
        full = inside(directory, text(body, "subfolder", 400), text(body, "filename", 400)) \
            if directory else None
        if not full:
            return fail("That path is outside ComfyUI's image folders.")
        if not os.path.isfile(full):
            return fail("Image not found on disk.")
        if os.path.getsize(full) > v2.MAX_IMAGE_BYTES:
            return fail("That image is too large to use as a preview.")
        with open(full, "rb") as handle:
            raw = handle.read()
        stamp = v2.save_preview(entry["id"], raw)
        return ok(stamp=stamp, id=entry["id"]) if stamp else fail("Could not read that image.")

    @post("/neons_style2/preview/delete")
    async def post_preview_delete(request):
        body = await data(request)
        return ok(removed=v2.delete_preview(text(body, "id", 200)))

    @post("/neons_style2/custom/save")
    async def post_custom_save(request):
        body = await data(request)
        entry, error = v2.save_custom(body.get("style"), replace=text(body, "replace", 60) or None)
        return fail(error) if error else ok(id=entry["id"], name=entry["name"])

    @post("/neons_style2/custom/delete")
    async def post_custom_delete(request):
        body = await data(request)
        return ok(removed=v2.delete_custom(text(body, "name", 60)))
