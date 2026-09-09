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
    from . import catalogs as catalog_sets
    from . import runs
    from .catalog import (
        FAMILY_ORDER,
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
        delete_custom,
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

    @routes.post("/neons_style/compose")
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

    @routes.post("/neons_style/roll")
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
        )
        return web.json_response({"ok": True, "names": names, "count": len(names)})

    # ---------------- catalogs (named preview sets) ----------------

    @routes.get("/neons_style/catalogs")
    async def get_catalogs(request):
        return web.json_response({"ok": True, **catalog_sets.payload()})

    @routes.post("/neons_style/catalogs/create")
    async def post_catalogs_create(request):
        """Add a catalog and switch to it."""
        body = await data(request)
        record = catalog_sets.create(body.get("name") or "")
        return web.json_response({"ok": True, "created": record, **catalog_sets.payload()})

    @routes.post("/neons_style/catalogs/select")
    async def post_catalogs_select(request):
        body = await data(request)
        catalog_sets.select(body.get("id") or "")
        return web.json_response({"ok": True, **catalog_sets.payload()})

    @routes.post("/neons_style/catalogs/rename")
    async def post_catalogs_rename(request):
        body = await data(request)
        ok = catalog_sets.rename(body.get("id") or "", body.get("name") or "")
        return web.json_response({"ok": ok, **catalog_sets.payload()})

    @routes.post("/neons_style/catalogs/delete")
    async def post_catalogs_delete(request):
        """Remove a catalog. Its image files stay on disk unless asked."""
        body = await data(request)
        ok = catalog_sets.remove(body.get("id") or "", delete_files=bool(body.get("delete_files")))
        return web.json_response({"ok": ok, **catalog_sets.payload()})

    @routes.post("/neons_style/catalogs/prompt")
    async def post_catalogs_prompt(request):
        """Add or delete one of the catalog's generation prompts."""
        body = await data(request)
        cid = body.get("id") or ""
        if body.get("delete"):
            ok = catalog_sets.delete_prompt(cid, text=body.get("text"), index=body.get("index"))
        else:
            ok = catalog_sets.add_prompt(cid, body.get("text") or "")
        return web.json_response({"ok": ok, **catalog_sets.payload()})

    # ---------------- families ----------------

    @routes.get("/neons_style/families")
    async def get_families(request):
        return web.json_response({"ok": True, "families": families_admin()})

    @routes.post("/neons_style/families/rename")
    async def post_families_rename(request):
        """Rename one of the user's own families. Every style in it is renamed
        to match, keeping its old name as an alias."""
        body = await data(request)
        ok, result, moved = rename_family(body.get("old") or "", body.get("new") or "")
        return web.json_response({
            "ok": ok, "family": result if ok else "", "moved": moved,
            "error": "" if ok else result, "families": families_admin(),
        })

    @routes.post("/neons_style/families/delete")
    async def post_families_delete(request):
        """Remove a user family; its styles move to Lonely rather than dying."""
        body = await data(request)
        ok, result, moved = delete_family(body.get("name") or "")
        return web.json_response({
            "ok": ok, "family": result if ok else "", "moved": moved,
            "error": "" if ok else result, "families": families_admin(),
        })

    # ---------------- gallery ----------------

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

    @routes.post("/neons_style/gallery/save")
    async def post_gallery_save(request):
        import folder_paths

        body = await data(request)
        style = body.get("style") or ""
        filename = body.get("filename") or ""
        if not style or style == "None" or not filename:
            return web.json_response({"ok": False, "error": "missing style or image"})
        directory = folder_paths.get_directory_by_type(body.get("type") or "output") \
            or folder_paths.get_output_directory()
        subfolder = body.get("subfolder") or ""
        full = os.path.join(directory, subfolder, filename) if subfolder else os.path.join(directory, filename)
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
        return web.json_response({"ok": True, "key": saved["key"], "file": saved["file"]})

    @routes.post("/neons_style/gallery/save_run")
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
        if not records:
            # a client that cannot name the prompt still gets the right style,
            # because the newest record is the run that just finished
            prompt_id, records = runs.latest()
        if not records:
            return web.json_response({
                "ok": False, "saved": [],
                "error": "no run recorded for this prompt — the node did not report a style",
            })

        images = [image for image in (body.get("images") or []) if image.get("filename")]
        if not images:
            return web.json_response({"ok": False, "error": "the client sent no images", "saved": []})
        image = images[0]
        directory = folder_paths.get_directory_by_type(image.get("type") or "output") \
            or folder_paths.get_output_directory()
        subfolder = image.get("subfolder") or ""
        name = image["filename"]
        full = os.path.join(directory, subfolder, name) if subfolder else os.path.join(directory, name)
        if not os.path.isfile(full):
            return web.json_response({
                "ok": False, "saved": [],
                "error": f"image not found on disk: {full}",
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
                saved.append({"node": node_id, "style": style, "key": stored["key"], "file": stored["file"]})
            else:
                skipped.append({"node": node_id, "style": style, "reason": "the gallery refused the image"})
        if not force:
            runs.forget(prompt_id)  # keep the record so a manual Save can still use it
        return web.json_response({
            "ok": True, "prompt_id": prompt_id, "saved": saved, "skipped": skipped,
        })

    @routes.post("/neons_style/gallery/cover")
    async def post_gallery_cover(request):
        body = await data(request)
        key = body.get("key") or gallery.key_for(body.get("style", ""))
        return web.json_response({"ok": gallery.set_cover(key, body.get("file", ""))})

    @routes.post("/neons_style/gallery/delete")
    async def post_gallery_delete(request):
        body = await data(request)
        key = body.get("key") or gallery.key_for(body.get("style", ""))
        if body.get("file"):
            return web.json_response({"ok": gallery.delete_shot(key, body["file"])})
        return web.json_response({"ok": gallery.delete_style(body.get("style") or key)})

    @routes.post("/neons_style/gallery/delete_family")
    async def post_gallery_delete_family(request):
        body = await data(request)
        family = (body.get("family") or "").strip()
        # no family given means every family: used by "delete all previews"
        names = [entry["name"] for entry in entries() if not family or entry["family"] == family]
        return web.json_response({"ok": True, "deleted": gallery.delete_many(names),
                                  "family": family or "all"})

    @routes.get("/neons_style/gallery/log")
    async def get_gallery_log(request):
        return web.json_response({"lines": gallery.read_log()})

    # ---------------- editing ----------------

    @routes.post("/neons_style/override")
    async def post_override(request):
        body = await data(request)
        ok, info = save_override(body.get("name") or "", **{k: v for k, v in body.items() if k != "name"})
        return web.json_response({"ok": ok, "name": info if ok else "", "error": "" if ok else info})

    @routes.post("/neons_style/override/delete")
    async def post_override_delete(request):
        body = await data(request)
        return web.json_response({"ok": delete_override(body.get("name") or "")})

    @routes.post("/neons_style/custom")
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
        )
        return web.json_response({"ok": ok, "name": info if ok else "", "error": "" if ok else info})

    @routes.post("/neons_style/custom/delete")
    async def post_custom_delete(request):
        body = await data(request)
        return web.json_response({"ok": delete_custom(body.get("name") or "")})

    @routes.post("/neons_style/style/hide")
    async def post_style_hide(request):
        body = await data(request)
        return web.json_response({"ok": hide_style(body.get("name") or "")})

    @routes.get("/neons_style/favourites")
    async def get_favourites(request):
        return web.json_response({"favourites": load_favourites(), "recents": load_recents()})

    @routes.post("/neons_style/favourite")
    async def post_favourite(request):
        body = await data(request)
        name = body.get("name") or ""
        state = toggle_favourite(name) if body.get("toggle") else set_favourite(name, bool(body.get("on", True)))
        return web.json_response({"ok": True, "name": name, "favourite": state,
                                  "favourites": load_favourites()})

    @routes.post("/neons_style/recent")
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

    @routes.post("/neons_style/style/restore")
    async def post_style_restore(request):
        body = await data(request)
        return web.json_response({"ok": restore_style(body.get("name") or "")})

    @routes.post("/neons_style/style/restore_all")
    async def post_style_restore_all(request):
        restored = restore_all()
        return web.json_response({"ok": True, "restored": restored})

    # ---------------- sharing ----------------

    @routes.get("/neons_style/export")
    async def get_export(request):
        rows = [entry for entry in entries() if entry["source"] in ("custom", "override")]
        return web.json_response({"schema": 1, "styles": rows})

    @routes.post("/neons_style/import")
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
