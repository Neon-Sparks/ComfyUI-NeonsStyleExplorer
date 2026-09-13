from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS, WEB_DIRECTORY

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]


def _routes():
    try:
        from aiohttp import web
        from server import PromptServer
    except Exception:
        return

    import os

    from . import compose as composer
    from . import gallery
    from . import bundle as bundles
    from . import catalogs as catalog_sets
    from . import runs
    from .catalog import (
        RANDOM_TOKEN,
        clear_recents,
        crawl_names,
        entries,
        load_favourites,
        load_recents,
        payload,
        push_recent,
        resolve,
        roll,
        set_favourite,
        tag_vocabulary,
        toggle_favourite,
    )
    from .store import (
        delete_override,
        hidden_styles,
        hide_style,
        restore_all,
        restore_style,
        save_custom,
        save_override,
        delete_family,
        families_admin,
        rename_family,
    )

    HERE = os.path.dirname(os.path.abspath(__file__))
    routes = PromptServer.instance.routes

    def same_origin(request):
        """Is this request coming from the ComfyUI page itself?

        ComfyUI listens on localhost, and every other page in the same browser
        can reach that server too. A browser always attaches Origin to a
        cross-site POST, so a request whose Origin names a different host did
        not come from the interface and is refused. Requests with no Origin —
        the extension's own fetches, curl, a script — are left alone.
        """
        origin = request.headers.get("Origin")
        if not origin:
            return True
        try:
            from urllib.parse import urlparse

            sent = urlparse(origin).netloc.lower()
        except Exception:
            return False
        host = (request.headers.get("Host") or "").lower()
        if not sent or not host:
            return False
        return sent == host or sent.split(":")[0] == host.split(":")[0]

    def post(path):
        """Register a POST route that only answers its own page.

        Every route below that changes something goes through here; the GET
        routes are read-only and a cross-site page cannot read their replies.
        """
        def wrap(handler):
            async def guarded(request):
                if not same_origin(request):
                    return web.json_response(
                        {"ok": False, "error": "cross-site request refused"}, status=403
                    )
                return await handler(request)

            guarded.__name__ = getattr(handler, "__name__", "guarded")
            return routes.post(path)(guarded)

        return wrap

    def inside(directory, *parts):
        """Resolve a client-supplied path and refuse anything outside *directory*.

        The image to file comes from the browser as a folder and a filename.
        Joined naively, "../.." walks straight out of ComfyUI's output folder
        and any file on the machine could be read and stored as a preview.
        """
        base = os.path.realpath(directory)
        target = os.path.realpath(os.path.join(base, *[str(part or "") for part in parts]))
        if target != base and not target.startswith(base + os.sep):
            return None
        return target

    async def data(request):
        try:
            return await request.json() or {}
        except Exception:
            return {}

    # ---------------- catalog ----------------

    @routes.get("/neons_style/catalog")
    async def get_catalog(request):
        return web.json_response(payload())

    @routes.get("/neons_style/tags")
    async def get_tags(request):
        tags = tag_vocabulary()
        return web.json_response({"tags": tags, "count": len(tags)})

    @post("/neons_style/compose")
    async def post_compose(request):
        body = await data(request)
        pool = entries()
        previews = gallery.manifest()
        styles = []
        for name in body.get("styles") or []:
            entry = roll(scope=body.get("roll_scope", "all"), previews=previews) if name == RANDOM_TOKEN else resolve(name, pool)
            if entry and entry["axis"] == "style" and entry not in styles:
                styles.append(entry)
        fmt = resolve(body.get("format"), pool)
        fmt = fmt if (fmt and fmt["axis"] == "format") else None
        finish = resolve(body.get("finish"), pool)
        finish = finish if (finish and finish["axis"] == "finish") else None
        positive, negative = composer.compose(
            close_with_medium=bool(body.get("close_with_medium", True)),
            prompt=body.get("prompt", ""),
            quality=body.get("quality", ""),
            negative=body.get("negative", ""),
            styles=styles,
            fmt=fmt,
            finish=finish,
            output_format=body.get("output_format"),
            style_position=body.get("style_position"),
            style_mix=body.get("style_mix"),
            tag_separator=body.get("tag_separator"),
            style_weight=body.get("style_weight"),
            include_style_negative=body.get("include_style_negative"),
        )
        return web.json_response({
            "ok": True,
            "positive": positive,
            "negative": negative,
            "styles": [entry["name"] for entry in styles],
        })

    @post("/neons_style/roll")
    async def post_roll(request):
        body = await data(request)
        entry = roll(
            axis=body.get("axis", "style"),
            scope=body.get("scope", "all"),
            family=body.get("family"),
            seed=body.get("seed") or None,
            previews=gallery.manifest(),
            exclude=tuple(body.get("exclude") or ()),
        )
        return web.json_response({"ok": bool(entry), "name": entry["name"] if entry else ""})

    @routes.get("/neons_style/crawl")
    async def get_crawl(request):
        """The ordered style names crawl mode walks for a scope. The client asks
        for this rather than deriving it, so the sequence matches the node's own
        fallback exactly."""
        names = crawl_names(
            scope=request.query.get("scope", "all"),
            family=request.query.get("family") or None,
            previews=gallery.manifest(),
            missing_only=request.query.get("missing_only") in ("1", "true", "True"),
            source=request.query.get("source") or "main",
        )
        return web.json_response({"ok": True, "names": names, "count": len(names)})

    # ---------------- catalogs (named preview sets) ----------------

    @routes.get("/neons_style/catalogs")
    async def get_catalogs(request):
        return web.json_response({"ok": True, **catalog_sets.payload()})

    @post("/neons_style/catalogs/create")
    async def post_catalogs_create(request):
        """Add a catalog and switch to it."""
        body = await data(request)
        record = catalog_sets.create(body.get("name") or "")
        return web.json_response({"ok": True, "created": record, **catalog_sets.payload()})

    @post("/neons_style/catalogs/select")
    async def post_catalogs_select(request):
        body = await data(request)
        catalog_sets.select(body.get("id") or "")
        return web.json_response({"ok": True, **catalog_sets.payload()})

    @post("/neons_style/catalogs/rename")
    async def post_catalogs_rename(request):
        body = await data(request)
        ok = catalog_sets.rename(body.get("id") or "", body.get("name") or "")
        return web.json_response({"ok": ok, **catalog_sets.payload()})

    @post("/neons_style/catalogs/delete")
    async def post_catalogs_delete(request):
        """Remove a catalog. Its image files stay on disk unless asked."""
        body = await data(request)
        ok = catalog_sets.remove(body.get("id") or "", delete_files=bool(body.get("delete_files")))
        return web.json_response({"ok": ok, **catalog_sets.payload()})

    @post("/neons_style/catalogs/prompt")
    async def post_catalogs_prompt(request):
        """Add or delete one of the catalog's generation prompts."""
        body = await data(request)
        cid = body.get("id") or ""
        if body.get("delete"):
            ok = catalog_sets.delete_prompt(cid, text=body.get("text"), index=body.get("index"))
        else:
            ok = catalog_sets.add_prompt(cid, body.get("text") or "")
        return web.json_response({"ok": ok, **catalog_sets.payload()})

    @routes.get("/neons_style/catalogs/export")
    async def get_catalog_export(request):
        """Download the active catalog as a shareable bundle."""
        cid = request.query.get("id") or ""
        mine = [entry for entry in entries() if entry["source"] in ("custom", "override")]
        filename, blob = bundles.export_catalog(cid or None, styles=mine)
        return web.Response(
            body=blob,
            headers={
                "Content-Type": "application/zip",
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(blob)),
            },
        )

    @post("/neons_style/catalogs/import")
    async def post_catalog_import(request):
        """Unpack a shared bundle into a new catalog."""
        reader = await request.multipart()
        raw, name = b"", ""
        while True:
            part = await reader.next()
            if part is None:
                break
            if part.name == "name":
                name = (await part.text()).strip()
            elif part.name == "bundle":
                chunks = []
                size = 0
                while True:
                    chunk = await part.read_chunk()
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > bundles.MAX_BYTES:
                        return web.json_response(
                            {"ok": False, "error": "that bundle is larger than this will accept"}
                        )
                    chunks.append(chunk)
                raw = b"".join(chunks)
        if not raw:
            return web.json_response({"ok": False, "error": "no bundle was uploaded"})
        ok, problem, info = bundles.import_bundle(raw, name=name or None)
        return web.json_response({"ok": ok, "error": problem, **info, **catalog_sets.payload()})

    # ---------------- loras ----------------

    @routes.get("/neons_lora/catalog")
    async def get_lora_catalog(request):
        """Every LoRA ComfyUI can see, grouped by its folders, with previews."""
        refresh = request.query.get("refresh") in ("1", "true", "True")
        data = loras.catalog(refresh=refresh)
        data["previews"] = loras.all_manifests()
        return web.json_response({"ok": True, **data})

    @routes.get("/neons_lora/banner")
    async def get_lora_banner(request):
        path = os.path.join(HERE, "web", "lora_banner.jpg")
        if not os.path.isfile(path):
            raise web.HTTPNotFound()
        return web.FileResponse(path, headers={"Cache-Control": "public, max-age=86400"})

    @routes.get("/neons_lora/shot")
    async def get_lora_shot(request):
        path = loras.shot_path(
            request.query.get("gallery") or "",
            request.query.get("key") or "",
            request.query.get("file"),
        )
        if not path or not os.path.isfile(path):
            raise web.HTTPNotFound()
        return web.FileResponse(path, headers={"Cache-Control": "public, max-age=604800"})

    @post("/neons_lora/save")
    async def post_lora_save(request):
        """File a generated image against a LoRA, in that LoRA's own gallery."""
        import folder_paths

        body = await data(request)
        name = body.get("lora") or ""
        filename = body.get("filename") or ""
        if not name or not filename:
            return web.json_response({"ok": False, "error": "missing lora or image"})
        directory = folder_paths.get_directory_by_type(body.get("type") or "output") \
            or folder_paths.get_output_directory()
        full = inside(directory, body.get("subfolder") or "", filename)
        if not full:
            return web.json_response({"ok": False, "error": "that path is outside the output folder"})
        if not os.path.isfile(full):
            return web.json_response({"ok": False, "error": "image not found on disk"})
        with open(full, "rb") as handle:
            raw = handle.read()
        saved = loras.add_shot(name, raw, prompt=body.get("prompt") or "")
        if not saved:
            return web.json_response({"ok": False, "error": "could not save that image"})
        return web.json_response({"ok": True, **saved})

    @post("/neons_lora/cover")
    async def post_lora_cover(request):
        body = await data(request)
        return web.json_response({"ok": loras.set_cover(
            body.get("gallery") or "", body.get("key") or "", body.get("file") or "")})

    @post("/neons_lora/shot/delete")
    async def post_lora_shot_delete(request):
        body = await data(request)
        return web.json_response({"ok": loras.delete_shot(
            body.get("gallery") or "", body.get("key") or "", body.get("file") or "")})

    @post("/neons_lora/delete")
    async def post_lora_delete(request):
        """Every image for one LoRA."""
        body = await data(request)
        return web.json_response({"ok": True, "removed": loras.delete_lora_shots(body.get("lora") or "")})

    @post("/neons_lora/triggers")
    async def post_lora_triggers(request):
        """Save (or clear) the words a LoRA wants in the prompt."""
        body = await data(request)
        name = body.get("lora") or ""
        text = loras.set_triggers(name, body.get("text") or "")
        return web.json_response({"ok": bool(name), "lora": name, "triggers": text})

    @post("/neons_lora/favourite")
    async def post_lora_favourite(request):
        body = await data(request)
        name = body.get("lora") or ""
        state = loras.toggle_favourite(name) if body.get("toggle") else \
            loras.set_favourite(name, bool(body.get("on", True)))
        return web.json_response({"ok": True, "lora": name, "favourite": state,
                                  "favourites": loras.load_favourites()})

    # ---------------- families ----------------

    @routes.get("/neons_style/families")
    async def get_families(request):
        return web.json_response({"ok": True, "families": families_admin()})

    @post("/neons_style/families/rename")
    async def post_families_rename(request):
        """Rename one of the user's own families. Every style in it is renamed
        to match, keeping its old name as an alias."""
        body = await data(request)
        ok, result, moved = rename_family(body.get("old") or "", body.get("new") or "")
        return web.json_response({
            "ok": ok, "family": result if ok else "", "moved": moved,
            "error": "" if ok else result, "families": families_admin(),
        })

    @post("/neons_style/families/delete")
    async def post_families_delete(request):
        """Remove a user family; its styles move to Lonely rather than dying."""
        body = await data(request)
        ok, result, moved = delete_family(body.get("name") or "")
        return web.json_response({
            "ok": ok, "family": result if ok else "", "moved": moved,
            "error": "" if ok else result, "families": families_admin(),
        })

    # ---------------- gallery ----------------

    @routes.get("/neons_style/entry")
    async def get_entry(request):
        """One entry in full, clause and avoid terms included.

        The catalog payload carries a light index; this is where the long text
        comes from when something actually needs it.
        """
        entry = resolve(request.query.get("name") or "")
        return web.json_response({"ok": bool(entry), "entry": entry})

    @routes.get("/neons_style/gallery/signature")
    async def get_gallery_signature(request):
        """Fingerprint of the current catalog's gallery, for cheap polling."""
        return web.json_response({"ok": True, "signature": gallery.signature()})

    @routes.get("/neons_style/gallery")
    async def get_gallery(request):
        return web.json_response({"previews": gallery.manifest()})

    @routes.get("/neons_style/shot")
    async def get_shot(request):
        key = request.query.get("key") or gallery.key_for(request.query.get("style", ""))
        path = gallery.shot_path(key, request.query.get("file"))
        if not path or not os.path.isfile(path):
            raise web.HTTPNotFound()
        return web.FileResponse(path, headers={"Cache-Control": "public, max-age=604800"})

    @routes.get("/neons_style/banner")
    async def get_banner(request):
        path = os.path.join(HERE, "web", "banner.jpg")
        if not os.path.isfile(path):
            raise web.HTTPNotFound()
        return web.FileResponse(path, headers={"Cache-Control": "public, max-age=86400"})

    @post("/neons_style/gallery/save")
    async def post_gallery_save(request):
        import folder_paths

        body = await data(request)
        style = body.get("style") or ""
        filename = body.get("filename") or ""
        if not style or style == "None" or not filename:
            return web.json_response({"ok": False, "error": "missing style or image"})
        directory = folder_paths.get_directory_by_type(body.get("type") or "output") \
            or folder_paths.get_output_directory()
        full = inside(directory, body.get("subfolder") or "", filename)
        if not full:
            return web.json_response({"ok": False, "error": "that path is outside the output folder"})
        if not os.path.isfile(full):
            return web.json_response({"ok": False, "error": "image not found on disk"})
        with open(full, "rb") as handle:
            raw = handle.read()
        saved = gallery.add_shot(
            resolve(style) or style, raw,
            prompt=body.get("prompt") or "",
            make_cover=bool(body.get("make_cover", True)),
        )
        if not saved:
            return web.json_response({"ok": False, "error": "could not save"})
        record = saved.get("record") or {}
        shots = record.get("shots") or []
        return web.json_response({
            "ok": True, "key": saved["key"], "file": saved["file"],
            "record": {"shots": shots, "cover": record.get("cover") or saved["file"],
                       "count": len(shots), "style": record.get("name") or style},
        })

    @post("/neons_style/run/record")
    async def post_run_record(request):
        """Record what a node will compose with, at the moment it is queued.

        The node itself records when it RUNS — but ComfyUI caches a node whose
        inputs have not changed, so a re-queue can execute nothing and leave the
        prompt with no record at all. The browser knows the prompt id and the
        style that prompt carries, so it files one here as well; the execution
        record overwrites it with the same answer when the node does run.
        """
        body = await data(request)
        prompt_id = str(body.get("prompt_id") or "")
        node_id = str(body.get("node") or "")
        style = str(body.get("style") or "")
        if not prompt_id or not node_id or not style:
            return web.json_response({"ok": False, "error": "prompt, node and style are required"})
        if not resolve(style):
            return web.json_response({"ok": False, "error": f"unknown style: {style}"})
        # no prompt text is accepted here: the node supplies it when it runs
        runs.record(prompt_id, node_id, style=style,
                    mode=str(body.get("mode") or "off"), queued=True)
        return web.json_response({"ok": True, "prompt_id": prompt_id, "style": style})

    @post("/neons_style/gallery/save_run")
    async def post_gallery_save_run(request):
        """Auto-gallery for one finished prompt.

        The client sends the prompt id and the images that prompt produced; the
        STYLE comes from the node's own record of that prompt, never from a
        widget. Crawl advances the dropdown as prompts are queued, so by the
        time run N finishes the widget is already several styles ahead — this is
        the only pairing that cannot drift.
        """
        import folder_paths

        body = await data(request)
        prompt_id = str(body.get("prompt_id") or "")
        records = runs.get(prompt_id)
        if not records and not prompt_id:
            # an older client cannot name the prompt; the newest record is then
            # the best available answer
            prompt_id, records = runs.latest()
        if not records:
            # NEVER guess from another prompt: that is how an image ends up on a
            # style it was not made with. Naming the prompt and finding nothing
            # means this run did not record a style, so say so.
            return web.json_response({
                "ok": False, "saved": [],
                "error": "this prompt recorded no style — nothing was saved rather than "
                         "risk filing it under another style",
            })

        images = [image for image in (body.get("images") or []) if image.get("filename")]
        if not images:
            return web.json_response({"ok": False, "error": "the client sent no images", "saved": []})
        image = images[0]
        directory = folder_paths.get_directory_by_type(image.get("type") or "output") \
            or folder_paths.get_output_directory()
        full = inside(directory, image.get("subfolder") or "", image["filename"])
        if not full:
            return web.json_response({
                "ok": False, "saved": [],
                "error": "that path is outside the output folder",
            })
        if not os.path.isfile(full):
            return web.json_response({
                "ok": False, "saved": [],
                "error": f"image not found on disk: {os.path.basename(full)}",
            })
        with open(full, "rb") as handle:
            raw = handle.read()

        # force = the Save button: file it whatever auto_gallery is set to
        force = bool(body.get("force"))
        node_filter = str(body.get("node") or "")
        saved, skipped = [], []
        for node_id, record in records.items():
            if node_filter and node_id != node_filter:
                skipped.append({"node": node_id, "reason": "another node"})
                continue
            style = record.get("style") or ""
            mode = record.get("mode") or "off"
            if not style or style == "None":
                skipped.append({"node": node_id, "reason": "no style recorded"})
                continue
            if not force and mode == "off":
                skipped.append({"node": node_id, "style": style, "reason": "auto_gallery is off"})
                continue
            if not force and mode == "first" and gallery.has_shots(style):
                skipped.append({"node": node_id, "style": style,
                                "reason": "auto_gallery is 'first' and this style already has a preview"})
                continue
            stored = gallery.add_shot(
                resolve(style) or style, raw,
                prompt=record.get("prompt") or "",
                make_cover=True,
            )
            if stored:
                record = stored.get("record") or {}
                shots = record.get("shots") or []
                saved.append({
                    "node": node_id, "style": style,
                    "key": stored["key"], "file": stored["file"],
                    # the updated record travels with the response: refetching
                    # the whole manifest after every save cost hundreds of
                    # kilobytes once a crawl was a few hundred previews in
                    "record": {
                        "shots": shots, "cover": record.get("cover") or stored["file"],
                        "count": len(shots), "style": record.get("name") or style,
                    },
                })
            else:
                skipped.append({"node": node_id, "style": style, "reason": "the gallery refused the image"})
        if not force:
            runs.forget(prompt_id)  # keep the record so a manual Save can still use it
        return web.json_response({
            "ok": True, "prompt_id": prompt_id, "saved": saved, "skipped": skipped,
        })

    @post("/neons_style/gallery/cover")
    async def post_gallery_cover(request):
        body = await data(request)
        key = body.get("key") or gallery.key_for(body.get("style", ""))
        return web.json_response({"ok": gallery.set_cover(key, body.get("file", ""))})

    @post("/neons_style/gallery/delete")
    async def post_gallery_delete(request):
        body = await data(request)
        key = body.get("key") or gallery.key_for(body.get("style", ""))
        if body.get("file"):
            return web.json_response({"ok": gallery.delete_shot(key, body["file"])})
        return web.json_response({"ok": gallery.delete_style(body.get("style") or key)})

    @post("/neons_style/gallery/delete_family")
    async def post_gallery_delete_family(request):
        body = await data(request)
        family = (body.get("family") or "").strip()
        # no family given means every family: used by "delete all previews"
        names = [entry["name"] for entry in entries() if not family or entry["family"] == family]
        return web.json_response({"ok": True, "deleted": gallery.delete_many(names),
                                  "family": family or "all"})

    # ---------------- editing ----------------

    @post("/neons_style/override")
    async def post_override(request):
        body = await data(request)
        ok, info = save_override(body.get("name") or "", **{k: v for k, v in body.items() if k != "name"})
        return web.json_response({"ok": ok, "name": info if ok else "", "error": "" if ok else info})

    @post("/neons_style/override/delete")
    async def post_override_delete(request):
        body = await data(request)
        return web.json_response({"ok": delete_override(body.get("name") or "")})

    @post("/neons_style/custom")
    async def post_custom(request):
        body = await data(request)
        ok, info = save_custom(
            body.get("name") or "",
            family=body.get("family") or "Other",
            axis=body.get("axis") or "style",
            nl=body.get("nl") or "",
            medium=body.get("medium") or "",
            negative=body.get("negative") or "",
            tags=body.get("tags"),
            tags_negative=body.get("tags_negative"),
            update=bool(body.get("update")),
            rename=body.get("rename") or "",
        )
        return web.json_response({"ok": ok, "name": info if ok else "", "error": "" if ok else info})

    @post("/neons_style/style/hide")
    async def post_style_hide(request):
        body = await data(request)
        return web.json_response({"ok": hide_style(body.get("name") or "")})

    @routes.get("/neons_style/favourites")
    async def get_favourites(request):
        return web.json_response({"favourites": load_favourites(), "recents": load_recents()})

    @post("/neons_style/favourite")
    async def post_favourite(request):
        body = await data(request)
        name = body.get("name") or ""
        state = toggle_favourite(name) if body.get("toggle") else set_favourite(name, bool(body.get("on", True)))
        return web.json_response({"ok": True, "name": name, "favourite": state,
                                  "favourites": load_favourites()})

    @post("/neons_style/recent")
    async def post_recent(request):
        body = await data(request)
        if body.get("clear"):
            clear_recents()
            return web.json_response({"ok": True, "recents": []})
        return web.json_response({"ok": True, "recents": push_recent(body.get("name") or "")})

    @routes.get("/neons_style/hidden")
    async def get_hidden(request):
        names = hidden_styles()
        return web.json_response({"hidden": names, "count": len(names)})

    @post("/neons_style/style/restore")
    async def post_style_restore(request):
        body = await data(request)
        return web.json_response({"ok": restore_style(body.get("name") or "")})

    @post("/neons_style/style/restore_all")
    async def post_style_restore_all(request):
        restored = restore_all()
        return web.json_response({"ok": True, "restored": restored})

    # ---------------- sharing ----------------

    @routes.get("/neons_style/export")
    async def get_export(request):
        rows = [entry for entry in entries() if entry["source"] in ("custom", "override")]
        return web.json_response({"schema": 1, "styles": rows})

    @post("/neons_style/import")
    async def post_import(request):
        body = await data(request)
        rows = body.get("styles") if isinstance(body, dict) else body
        added, failed = 0, []
        for raw in rows or []:
            if not isinstance(raw, dict):
                continue
            ok, info = save_custom(
                raw.get("name", ""),
                family=raw.get("family", "Other"),
                axis=raw.get("axis", "style"),
                nl=raw.get("nl", ""),
                medium=raw.get("medium", ""),
                negative=raw.get("negative", ""),
                tags=raw.get("tags"),
                tags_negative=raw.get("tags_negative"),
            )
            if ok:
                added += 1
            else:
                failed.append({"name": raw.get("name", ""), "error": info})
        return web.json_response({"ok": True, "added": added, "failed": failed})


try:
    _routes()
except Exception:  # pragma: no cover
    import traceback

    traceback.print_exc()
