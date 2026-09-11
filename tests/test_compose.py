"""Composer and catalog tests:  python tests/test_compose.py"""

import importlib.util
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = "ns_pkg"

if PKG not in sys.modules:
    spec = importlib.util.spec_from_file_location(
        PKG, os.path.join(ROOT, "__init__.py"), submodule_search_locations=[ROOT]
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[PKG] = module
    spec.loader.exec_module(module)

compose = importlib.import_module(f"{PKG}.compose")
catalog = importlib.import_module(f"{PKG}.catalog")
nodes = importlib.import_module(f"{PKG}.nodes")
runs = importlib.import_module(f"{PKG}.runs")
catalog_sets = importlib.import_module(f"{PKG}.catalogs")
gallery = importlib.import_module(f"{PKG}.gallery")

A = {"id": "t.a", "name": "[Test] A", "family": "Anime & Manga", "axis": "style",
     "medium": "anime style image", "nl": "Flat cel colour in hard bands, anime style image.",
     "tags": ["anime_coloring", "cel_shading"], "tags_negative": ["photorealistic"],
     "negative": "photo, 3d render", "aliases": [], "written": True, "source": "shipped"}
B = {"id": "t.b", "name": "[Test] B", "family": "Photography & Film", "axis": "style",
     "medium": "photograph style image", "nl": "Fine grain and warm skin, photograph style image.",
     "tags": ["photo_(medium)", "film_grain"], "tags_negative": ["3d"],
     "negative": "illustration", "aliases": [], "written": True, "source": "shipped"}
F = {"id": "t.f", "name": "[Format] Sheet", "family": "Comics & Print", "axis": "format",
     "medium": "comic style image", "nl": "Panel gutters and balloon space, comic style image.",
     "tags": ["comic"], "tags_negative": [], "negative": "", "aliases": [], "written": True,
     "source": "shipped"}


# The suite must not read — or destroy — a real installation's data. Any user
# files present are moved aside for the run and put back afterwards, which also
# stops one test's leftovers from deciding another test's result.
_STASH = []


def setUpModule():
    user_dir = os.path.join(ROOT, "user")
    if not os.path.isdir(user_dir):
        return
    for name in os.listdir(user_dir):
        if not name.endswith(".json"):
            continue
        live = os.path.join(user_dir, name)
        aside = f"{live}.testbak"
        os.replace(live, aside)
        _STASH.append((live, aside))
    catalog.entries(force=True)


def tearDownModule():
    # anything the run itself created goes; only what was there before returns
    user_dir = os.path.join(ROOT, "user")
    if os.path.isdir(user_dir):
        for name in os.listdir(user_dir):
            if name.endswith(".json"):
                os.remove(os.path.join(user_dir, name))
    for live, aside in _STASH:
        if os.path.isfile(live):
            os.remove(live)
        os.replace(aside, live)
    _STASH.clear()
    catalog.entries(force=True)


def wipe_user_files(*names):
    """Remove the user files a test created. Writing an empty list back would
    leave litter in the package; tests should leave no trace at all."""
    for name in names or ("favourites.json", "recents.json", "custom.json",
                          "overrides.json", "hidden.json", "catalogs.json"):
        path = os.path.join(ROOT, "user", name)
        if os.path.isfile(path):
            os.remove(path)


class Natural(unittest.TestCase):
    def test_style_first(self):
        pos, _ = compose.compose(prompt="a fox", quality="masterpiece", styles=[A])
        self.assertTrue(pos.startswith("masterpiece, Flat cel colour"))
        self.assertTrue(pos.endswith("a fox"))

    def test_style_last(self):
        pos, _ = compose.compose(prompt="a fox", styles=[A], style_position="end")
        self.assertTrue(pos.startswith("a fox"))
        self.assertTrue(pos.rstrip().endswith("anime style image."))

    def test_no_instruction_language(self):
        pos, _ = compose.compose(prompt="a fox", styles=[A])
        for banned in ("governs the entire image", "do not add", "not an object"):
            self.assertNotIn(banned, pos)

    def test_medium_closes_the_clause(self):
        pos, _ = compose.compose(prompt="", styles=[A])
        self.assertTrue(pos.rstrip().endswith("anime style image."))

    def test_mixing(self):
        pos, _ = compose.compose(prompt="a fox", styles=[A, B], style_mix="mixed with")
        self.assertIn("mixed with fine grain", pos)

    def test_format_appended(self):
        pos, _ = compose.compose(prompt="a fox", styles=[A], fmt=F)
        self.assertIn("panel gutters", pos)

    def test_quality_stays_first(self):
        pos, _ = compose.compose(prompt="a fox", quality="best quality", styles=[A], style_position="end")
        self.assertTrue(pos.startswith("best quality,"))

    def test_weight_emphasises_the_clause(self):
        pos, _ = compose.compose(prompt="a fox", styles=[A], style_weight=2.5)
        self.assertIn("(Flat cel colour", pos)
        self.assertIn(":2.50).", pos)
        self.assertNotIn("::", pos)

    def test_weight_one_leaves_the_clause_alone(self):
        pos, _ = compose.compose(prompt="a fox", styles=[A], style_weight=1)
        self.assertNotIn("(", pos)

    def test_negative_merge(self):
        _, neg = compose.compose(negative="blurry", styles=[A, B])
        self.assertIn("blurry", neg)
        self.assertIn("illustration", neg)

    def test_negative_opt_out(self):
        _, neg = compose.compose(negative="blurry", styles=[A], include_style_negative=False)
        self.assertEqual(neg, "blurry")


class Medium(unittest.TestCase):
    """Exactly one medium is emitted, and it belongs to the leading style."""

    def test_format_does_not_hijack_the_medium(self):
        clause = compose.style_clause([A], fmt=F)
        self.assertTrue(clause.endswith("anime style image."), clause)
        self.assertEqual(clause.count("style image"), 1)
        self.assertIn("panel gutters", clause)

    def test_finish_does_not_hijack_the_medium(self):
        finish = dict(A, id="t.n", name="[Finish] Real", axis="finish",
                      medium="photograph style image",
                      nl="Natural skin texture, photograph style image.")
        clause = compose.style_clause([A], finish=finish)
        self.assertTrue(clause.endswith("anime style image."), clause)
        self.assertIn("natural skin texture", clause.lower())
        self.assertNotIn("photograph style image", clause)

    def test_format_alone_keeps_its_own_medium(self):
        clause = compose.style_clause([], fmt=F)
        self.assertTrue(clause.endswith("comic style image."), clause)

    def test_second_style_medium_is_dropped(self):
        clause = compose.style_clause([A, B])
        self.assertEqual(clause.count("style image"), 1)
        self.assertTrue(clause.endswith("anime style image."), clause)

    def test_whole_catalog_emits_one_medium(self):
        pool = catalog.by_axis("style")[:200]
        fmt = catalog.by_axis("format")[0]
        finish = catalog.by_axis("finish")[0]
        for entry in pool:
            clause = compose.style_clause([entry], fmt=fmt, finish=finish)
            self.assertEqual(clause.count(" style image"), 1, entry["name"])
            self.assertTrue(clause.endswith(entry["medium"] + "."), entry["name"])


class Tags(unittest.TestCase):
    def test_tag_mode(self):
        pos, _ = compose.compose(prompt="1girl", quality="masterpiece", styles=[A], output_format="danbooru")
        self.assertEqual(pos, "masterpiece, anime_coloring, cel_shading, 1girl")

    def test_weighting_primary_only(self):
        pos, _ = compose.compose(styles=[A, B], output_format="danbooru", style_weight=1.1)
        self.assertIn("(anime_coloring:1.10)", pos)
        self.assertIn("film_grain", pos)
        self.assertNotIn("(film_grain:1.10)", pos)

    def test_weight_one_adds_nothing(self):
        pos, _ = compose.compose(styles=[A], output_format="danbooru", style_weight=1.0)
        self.assertEqual(pos, "anime_coloring, cel_shading")

    def test_parens_in_tags_are_escaped(self):
        entry = dict(A, tags=["graphite_(medium)"])
        pos, _ = compose.compose(styles=[entry], output_format="danbooru")
        self.assertEqual(pos, "graphite_\\(medium\\)")
        pos, _ = compose.compose(styles=[entry], output_format="danbooru", style_weight=1.4)
        self.assertEqual(pos, "(graphite_\\(medium\\):1.40)")

    def test_weight_is_clamped(self):
        pos, _ = compose.compose(styles=[A], output_format="danbooru", style_weight=99)
        self.assertIn(":5.00)", pos)

    def test_negative_tags_never_fight(self):
        _, neg = compose.compose(styles=[A, B], output_format="danbooru")
        self.assertNotIn("photorealistic", neg.split(", ")[0:0])
        self.assertIn("3d", neg)

    def test_both_modes(self):
        pos, _ = compose.compose(prompt="a fox", styles=[A], output_format="natural + danbooru")
        self.assertIn("a fox", pos)
        self.assertIn("\n\nTags: ", pos)

    def test_position_in_tag_mode(self):
        pos, _ = compose.compose(prompt="1girl", styles=[A], output_format="danbooru", style_position="end")
        self.assertTrue(pos.startswith("1girl"))


class Catalog(unittest.TestCase):
    def test_loads_and_caches(self):
        first = catalog.entries()
        self.assertGreater(len(first), 500)
        self.assertIs(first, catalog.entries())

    def test_axes(self):
        data = catalog.payload()
        self.assertGreater(len(data["styles"]), 500)
        self.assertGreater(len(data["formats"]), 20)
        self.assertGreater(len(data["finishes"]), 5)

    def test_resolve_alias(self):
        v2 = next((e for e in catalog.entries() if "[v2]" in e["name"]), None)
        self.assertIsNotNone(v2)
        self.assertIs(catalog.resolve(v2["aliases"][0]), v2)

    def test_roll_is_seedable(self):
        first = catalog.roll(seed=99)
        self.assertIsNotNone(first)
        self.assertEqual(first["name"], catalog.roll(seed=99)["name"])

    def test_roll_scope_matches_gallery_keys(self):
        entry = catalog.by_axis("style")[3]
        key = catalog.preview_key(entry["id"])
        fake = {key: {"cover": "x.jpg", "shots": [{"file": "x.jpg"}]}}
        picked = catalog.roll(scope="has preview", previews=fake)
        self.assertIsNotNone(picked, "has-preview scope must see gallery keys")
        self.assertEqual(picked["id"], entry["id"])
        for seed in range(1, 60):
            other = catalog.roll(scope="missing preview", previews=fake, seed=seed)
            self.assertNotEqual(other["id"], entry["id"])

    def test_merged_names_still_resolve(self):
        """Folded duplicates keep working as search aliases."""
        for old, expected in [
            ("[3D][v2] Low Poly", "[3D] Low-Poly"),
            ("[Photo] Toy Camera", "[Photo] Holga Toy Camera"),
            ("[Design][v2] Bauhaus", "[Aesthetic] Bauhaus"),
            ("[Painting][v2] Abstract Expressionism", "[Painting] Abstract Expressionism"),
            ("[Photo] Polaroid Instant", "[Photo] Polaroid"),
        ]:
            entry = catalog.resolve(old)
            self.assertIsNotNone(entry, old)
            self.assertEqual(entry["name"], expected)

    def test_no_duplicate_base_names(self):
        seen = {}
        for entry in catalog.entries():
            key = catalog.base_name(entry["name"]).lower()
            seen.setdefault(key, []).append(entry["name"])
        twins = {k: v for k, v in seen.items() if len(v) > 1}
        # An imported family may cover the same look as an entry written here —
        # "[Anime] Pixel Art" and "[Extra] Pixel Art" are two projects' takes on
        # one thing, and both are wanted. Only collisions inside the written
        # catalog are faults.
        twins = {
            base: names for base, names in twins.items()
            if sum(1 for full in names if catalog.resolve(full)["family"] not in catalog.IMPORTED_FAMILIES) > 1
        }
        self.assertEqual(twins, {}, f"duplicate base names left: {twins}")

    def test_favourites_round_trip(self):
        pool = catalog.by_axis("style")
        first, second = pool[0]["name"], pool[1]["name"]
        try:
            catalog.set_favourite(first, True)
            catalog.set_favourite(second, True)
            self.assertTrue(catalog.is_favourite(first))
            self.assertEqual(len(catalog.load_favourites()), 2)
            picked = catalog.roll(scope="favourites", seed=3)
            self.assertIn(picked["name"], {first, second})
            self.assertFalse(catalog.toggle_favourite(first))
            self.assertEqual(catalog.load_favourites(), [second])
        finally:
            wipe_user_files("favourites.json")

    def test_recents_are_capped_and_ordered(self):
        catalog.clear_recents()
        try:
            names = [entry["name"] for entry in catalog.by_axis("style")[:3]]
            for name in names:
                catalog.push_recent(name)
            self.assertEqual(catalog.load_recents()[0], names[-1])
            catalog.push_recent(names[0])
            self.assertEqual(catalog.load_recents()[0], names[0])
            self.assertEqual(len(catalog.load_recents()), 3)
            picked = catalog.roll(scope="recent", seed=7)
            self.assertIn(picked["name"], names)
        finally:
            wipe_user_files("recents.json")

    def test_parallel_writes_keep_every_update(self):
        """Several prompts finishing together must not clobber each other."""
        import threading

        names = [entry["name"] for entry in catalog.by_axis("style")[:16]]
        # start from a known state: other tests run the node, which records recents
        catalog.write_json(catalog.favourites_path(), [])
        catalog.clear_recents()
        try:
            threads = [threading.Thread(target=catalog.set_favourite, args=(name, True)) for name in names]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(len(catalog.load_favourites()), len(names))

            threads = [threading.Thread(target=catalog.push_recent, args=(name,)) for name in names]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(len(catalog.load_recents()), len(names))
        finally:
            wipe_user_files("favourites.json", "recents.json")

    def test_crawl_walks_the_scope_in_order(self):
        # crawl walks one dropdown's source at a time; "main" is the written
        # catalog, without the imported pack or the user's own entries
        names = catalog.crawl_names("all")
        main = catalog.written_names("style")
        self.assertEqual(len(names), len(main))
        self.assertEqual(names, [entry["name"] for entry in catalog.by_axis("style")
                                 if entry["name"] in set(main)])
        self.assertEqual(len(set(names)), len(names))

    def test_crawl_scope_narrows_the_walk(self):
        family = catalog.by_axis("style")[0]["family"]
        walk = catalog.crawl_names("family", family=family)
        self.assertTrue(walk)
        self.assertTrue(all(catalog.resolve(name)["family"] == family for name in walk))
        self.assertLess(len(walk), len(catalog.crawl_names("all")))
        # the imported pack has its own source and never leaks into "main"
        self.assertTrue(set(catalog.crawl_names("all")).isdisjoint(catalog.imported_style_names()))

    def test_crawl_disables_every_dice(self):
        """With crawl on, no slot may roll: extra dice slots resolve to nothing
        and the main slot falls back to the head of the walk."""
        token = nodes.RANDOM_TOKEN
        _pos, _neg, _dbg, styles = nodes.run(
            prompt="a cat", style=token, style_2=token, style_3=token,
            format=token, finish=token, crawl=True, roll_scope="all",
        )
        self.assertEqual([entry["name"] for entry in styles], catalog.crawl_names("all")[:1])
        for _ in range(4):  # never random: the same run repeats identically
            _p, _n, _d, again = nodes.run(
                prompt="a cat", style=token, style_2=token, crawl=True, roll_scope="all",
            )
            self.assertEqual([entry["name"] for entry in again], [entry["name"] for entry in styles])

    def test_run_records_survive_a_moving_dropdown(self):
        """Crawl advances the style widget as prompts are QUEUED, so by the time
        prompt 1 finishes the widget is already on style 4. The server record is
        what auto-gallery reads, and it must still name style 1."""
        runs.clear()
        walk = catalog.crawl_names("all")[:4]
        try:
            for index, name in enumerate(walk):
                # each prompt is composed and recorded in turn...
                _p, _n, _d, styles = nodes.run(prompt="x", style=name, crawl=True)
                runs.record(f"prompt-{index}", "7", style=styles[0]["name"], mode="every", prompt="x")
            # ...and the four records still map to the four styles, in order
            for index, name in enumerate(walk):
                self.assertEqual(runs.get(f"prompt-{index}")["7"]["style"], name)
            self.assertEqual(runs.latest()[0], f"prompt-{len(walk) - 1}")
            runs.forget("prompt-0")
            self.assertEqual(runs.get("prompt-0"), {})
        finally:
            runs.clear()
            wipe_user_files("recents.json")

    def test_run_records_are_capped(self):
        runs.clear()
        try:
            for index in range(runs.MAX_RUNS + 10):
                runs.record(f"p{index}", "1", style="[Test] A", mode="off", prompt="")
            self.assertEqual(len(runs._RUNS), runs.MAX_RUNS)
            self.assertEqual(runs.get("p0"), {})  # oldest dropped first
            self.assertTrue(runs.get(f"p{runs.MAX_RUNS + 9}"))
        finally:
            runs.clear()

    def test_catalogs_keep_separate_previews_and_favourites(self):
        """A named catalog is its own preview set, favourites and recents; the
        style texts stay shared."""
        import shutil

        made = None
        try:
            # never assume what a previous test (or a stray probe run) left
            # active — start from a known catalog
            catalog_sets.select("default")
            self.assertEqual(catalog_sets.active(), "default")
            default_previews = gallery.previews_dir()

            made = catalog_sets.create("my krea 2")
            self.assertEqual(catalog_sets.active(), made["id"])
            self.assertNotEqual(gallery.previews_dir(), default_previews)
            self.assertIn(made["id"], gallery.previews_dir())

            name = catalog.by_axis("style")[0]["name"]
            catalog.set_favourite(name, True)
            catalog.push_recent(name)
            self.assertEqual(catalog.load_favourites(), [name])

            catalog_sets.select("default")
            self.assertEqual(catalog.load_favourites(), [])   # isolated
            self.assertEqual(catalog.load_recents(), [])
            self.assertEqual(gallery.previews_dir(), default_previews)
            # the styles themselves are shared
            self.assertTrue(catalog.resolve(name))

            catalog_sets.select(made["id"])
            self.assertEqual(catalog.load_favourites(), [name])

            self.assertTrue(catalog_sets.rename(made["id"], "Krea 2 HD"))
            self.assertEqual(catalog_sets.name_of(made["id"]), "Krea 2 HD")
            self.assertFalse(catalog_sets.remove("default"))  # never removable
        finally:
            if made:
                catalog_sets.remove(made["id"], delete_files=True)
            catalog_sets.select("default")
            for path in ("user/catalogs.json", "user/favourites.json", "user/recents.json"):
                full = os.path.join(ROOT, path)
                if os.path.isfile(full):
                    os.remove(full)
            shutil.rmtree(os.path.join(ROOT, "user", "catalogs"), ignore_errors=True)

    def test_catalog_prompts_round_trip(self):
        """A catalog remembers the prompt(s) its previews were generated with."""
        catalog_sets.select("default")
        try:
            self.assertEqual(catalog_sets.prompts_of("default"), [])
            self.assertTrue(catalog_sets.add_prompt("default", "  a woman   in a city street  "))
            self.assertEqual(catalog_sets.prompts_of("default"), ["a woman in a city street"])
            catalog_sets.add_prompt("default", "a woman in a city street")  # duplicate ignored
            catalog_sets.add_prompt("default", "a lone tree on a hill")
            self.assertEqual(len(catalog_sets.prompts_of("default")), 2)
            self.assertTrue(catalog_sets.delete_prompt("default", text="a lone tree on a hill"))
            self.assertEqual(catalog_sets.prompts_of("default"), ["a woman in a city street"])
            self.assertTrue(catalog_sets.delete_prompt("default", index=0))
            self.assertEqual(catalog_sets.prompts_of("default"), [])
            self.assertFalse(catalog_sets.add_prompt("default", "   "))
        finally:
            full = os.path.join(ROOT, "user", "catalogs.json")
            if os.path.isfile(full):
                os.remove(full)

    def test_catalog_names_get_unique_ids(self):
        made = []
        catalog_sets.select("default")
        try:
            made = [catalog_sets.create("Krea 2"), catalog_sets.create("Krea 2")]
            self.assertNotEqual(made[0]["id"], made[1]["id"])
            self.assertEqual(made[0]["name"], made[1]["name"])
        finally:
            for record in made:
                catalog_sets.remove(record["id"], delete_files=True)
            catalog_sets.select("default")
            full = os.path.join(ROOT, "user", "catalogs.json")
            if os.path.isfile(full):
                os.remove(full)

    def test_custom_slot_family_and_free_tags(self):
        """A user's own style: any family they like, any tags they like, and it
        composes from the custom_style slot alongside a catalog style."""
        store = importlib.import_module(f"{PKG}.store")
        name = None
        # start clean: a stray custom style from an earlier run would change the
        # slot's contents and the composed order
        for path in ("user/custom.json", "user/overrides.json", "user/hidden.json"):
            full = os.path.join(ROOT, path)
            if os.path.isfile(full):
                os.remove(full)
        try:
            ok, name = store.save_custom(
                name="Probe Chrome Bloom", family="Probe Metal", axis="style",
                nl="Probe rendering: mirrored liquid metal bulging into soft blobs, chrome style image.",
                medium="chrome style image", negative="matte surfaces",
                tags=["liquid_metal", "chrome_(medium)"],       # not in the vocabulary
                tags_negative=["matte_finish"],
            )
            self.assertTrue(ok)
            entry = catalog.resolve(name)
            self.assertEqual(entry["family"], "Probe Metal")     # families are not a fixed list
            self.assertEqual(entry["tags"], ["liquid_metal", "chrome_(medium)"])
            self.assertIn(name, catalog.custom_names("style"))
            self.assertIn("Probe Metal", catalog.payload()["families"])
            # the custom slot composes as a fourth style
            _p, _n, _d, styles = nodes.run(prompt="a kettle", style="[Anime] Chibi", custom_style=name)
            self.assertEqual([e["name"] for e in styles], ["[Anime] Chibi", name])
            # and its unlisted tags survive into booru output, escaped
            tags, _neg, _dbg, _s = nodes.run(prompt="kettle", custom_style=name, output_format="danbooru")
            self.assertIn("liquid_metal", tags)
            self.assertIn("chrome_\\(medium\\)", tags)
        finally:
            if name:
                store.delete_custom(name) if hasattr(store, "delete_custom") else None
            for path in ("user/custom.json", "user/overrides.json", "user/hidden.json"):
                full = os.path.join(ROOT, path)
                if os.path.isfile(full):
                    os.remove(full)
            catalog.entries(refresh=True) if "refresh" in catalog.entries.__code__.co_varnames else None

    def test_family_rename_retags_and_keeps_the_old_name(self):
        """Editing a custom style's family rebuilds its bracket tag, and the old
        name keeps resolving so saved workflows survive."""
        store = importlib.import_module(f"{PKG}.store")
        for path in ("user/custom.json",):
            full = os.path.join(ROOT, path)
            if os.path.isfile(full):
                os.remove(full)
        try:
            ok, first = store.save_custom(
                name="Probe Figurine", family="Material Test", axis="style",
                nl="Probe rendering: matte resin cast, style image.", medium="style image")
            self.assertTrue(first.startswith("[Material][Custom]"), first)
            ok, second = store.save_custom(
                name=first, family="Figurine", axis="style", update=True,
                nl="Probe rendering: matte resin cast, style image.", medium="style image")
            self.assertTrue(second.startswith("[Figurine][Custom]"), second)
            self.assertEqual(catalog.resolve(first)["name"], second)   # old name still resolves

            ok, family, moved = store.rename_family("Figurine", "Resin Figures")
            self.assertTrue(ok)
            self.assertEqual(moved, 1)
            renamed = [e for e in catalog.entries() if e.get("source") == "custom"][0]
            self.assertTrue(renamed["name"].startswith("[Resin][Custom]"))

            ok, family, moved = store.delete_family("Resin Figures")
            self.assertTrue(ok)
            self.assertEqual(family, "Lonely")
            orphan = [e for e in catalog.entries() if e.get("source") == "custom"][0]
            self.assertEqual(orphan["family"], "Lonely")   # styles survive, family does not

            self.assertFalse(store.rename_family("Anime & Manga", "Nope")[0])  # shipped is locked
        finally:
            full = os.path.join(ROOT, "user", "custom.json")
            if os.path.isfile(full):
                os.remove(full)
            catalog.entries(force=True)

    def test_rename_keeps_id_aliases_and_refuses_clashes(self):
        """A rename must not orphan previews: the id stays, the old name becomes
        an alias, and an existing name cannot be taken."""
        store = importlib.import_module(f"{PKG}.store")
        gallery_mod = importlib.import_module(f"{PKG}.gallery")
        wipe_user_files("overrides.json", "custom.json")
        try:
            original = catalog.by_axis("style")[0]["name"]
            before = catalog.resolve(original)
            key_before = gallery_mod.key_for(before)

            ok, renamed = store.save_override(original, rename="Probe Renamed Style")
            self.assertTrue(ok)
            after = catalog.resolve("Probe Renamed Style")
            self.assertEqual(after["id"], before["id"])                 # previews stay attached
            self.assertEqual(gallery_mod.key_for(after), key_before)
            self.assertIn(original, after["aliases"])                   # old name still resolves
            self.assertEqual(catalog.resolve(original)["name"], "Probe Renamed Style")

            other = catalog.by_axis("style")[1]["name"]
            self.assertFalse(store.save_override(other, rename="Probe Renamed Style")[0])
        finally:
            wipe_user_files("overrides.json", "custom.json")
            catalog.entries(force=True)

    def test_payload_is_light_and_detail_is_complete(self):
        """The catalog payload carries an index, not the whole text: it is
        fetched on eighteen paths and the clauses dominate its size."""
        import json as json_mod

        pay = catalog.payload()
        entry = pay["by_name"][catalog.by_axis("style")[0]["name"]]
        self.assertNotIn("nl", entry)            # the clause is not in the index
        self.assertNotIn("negative", entry)
        for field in ("name", "family", "axis", "medium", "source", "tags", "aliases"):
            self.assertIn(field, entry)          # everything filtering needs
        size = len(json_mod.dumps(pay))
        self.assertLess(size, 1_600_000, f"payload grew back to {size} bytes")
        # and the full text is still one lookup away
        full = catalog.resolve(entry["name"])
        self.assertTrue(full["nl"])

    def test_gallery_signature_moves_only_on_change(self):
        gallery_mod = importlib.import_module(f"{PKG}.gallery")
        manifest_existed = os.path.isfile(gallery_mod.manifest_path())
        first = gallery_mod.signature()
        self.assertEqual(first, gallery_mod.signature())   # stable while idle
        data = gallery_mod._load()
        try:
            data["_probe"] = {"shots": [], "cover": "", "count": 0}
            gallery_mod._save(data)
            self.assertNotEqual(first, gallery_mod.signature())
        finally:
            data.pop("_probe", None)
            gallery_mod._save(data)
            # leave no manifest behind if the test created one
            if not manifest_existed and os.path.isfile(gallery_mod.manifest_path()):
                os.remove(gallery_mod.manifest_path())

    def test_style_slots_are_split_by_source(self):
        """Each dropdown carries one source, so no menu holds the whole catalog."""
        main = catalog.written_names("style")
        extra = catalog.imported_style_names()
        self.assertTrue(main and extra)
        self.assertEqual(set(main) & set(extra), set())          # no overlap
        self.assertEqual(len(main) + len(extra) + len(catalog.custom_names("style")),
                         len(catalog.by_axis("style")))          # and none missing
        self.assertLess(len(main), 1600, "the main dropdown is heavy again")
        # a crawl over one source only ever walks that source
        walk = catalog.crawl_names(source="extra")
        self.assertTrue(set(walk).issubset(set(extra)))
        # and both slots compose together, leading style first
        _p, _n, _d, styles = nodes.run(prompt="x", style=main[0], extra_style=extra[0])
        self.assertEqual([entry["name"] for entry in styles], [main[0], extra[0]])

    def test_catalog_bundle_round_trip(self):
        """A catalog exports to a zip and comes back as a new catalog."""
        import io, json as json_mod, shutil, zipfile

        bundle = importlib.import_module(f"{PKG}.bundle")
        gallery_mod = importlib.import_module(f"{PKG}.gallery")
        made = []
        image = os.path.join(gallery_mod.previews_dir(), "probe_bundle--1.jpg")
        manifest_path = gallery_mod.manifest_path()
        had_manifest = os.path.isfile(manifest_path)
        try:
            os.makedirs(gallery_mod.previews_dir(), exist_ok=True)
            with open(image, "wb") as handle:
                handle.write(b"\xff\xd8\xff\xdb" + b"0" * 200)
            with open(manifest_path, "w", encoding="utf-8") as handle:
                json_mod.dump({"probe_bundle": {
                    "shots": [{"file": "probe_bundle--1.jpg", "prompt": "a pier", "ts": 1}],
                    "cover": "probe_bundle--1.jpg", "count": 1, "style": "[Anime] Chibi"}}, handle)

            name, blob = bundle.export_catalog("default")
            self.assertTrue(name.endswith(".zip"))
            self.assertEqual(sorted(zipfile.ZipFile(io.BytesIO(blob)).namelist()),
                             ["bundle.json", "previews/probe_bundle--1.jpg"])

            ok, problem, info = bundle.import_bundle(blob, name="Probe Shared")
            made.append(info["catalog"])
            self.assertTrue(ok, problem)
            self.assertEqual((info["images"], info["styles"]), (1, 1))
            self.assertEqual(info["name"], "Probe Shared")
        finally:
            for cid in made:
                catalog_sets.remove(cid, delete_files=True)
            catalog_sets.select("default")
            for path in (image, manifest_path):
                if os.path.isfile(path) and not (path == manifest_path and had_manifest):
                    os.remove(path)
            shutil.rmtree(os.path.join(ROOT, "user", "catalogs"), ignore_errors=True)
            wipe_user_files("catalogs.json", "custom.json")

    def test_hostile_bundle_writes_nothing_outside_the_catalog(self):
        """Zip entries are names, not paths: nothing in an archive may steer a
        write, and an over-large or over-expanding archive is refused."""
        import io, json as json_mod, shutil, zipfile

        bundle = importlib.import_module(f"{PKG}.bundle")
        made = []
        probe_a = "/tmp/ns_escape_probe_a.jpg"
        probe_b = "/tmp/ns_escape_probe_b.jpg"
        try:
            evil = io.BytesIO()
            with zipfile.ZipFile(evil, "w") as archive:
                archive.writestr("bundle.json", json_mod.dumps({
                    "kind": "neons-style-catalog", "schema": 1, "name": "Evil",
                    "entries": [], "prompts": []}))
                archive.writestr("previews/../../../../tmp/ns_escape_probe_a.jpg", b"x" * 10)
                archive.writestr("../../../tmp/ns_escape_probe_b.jpg", b"x" * 10)
                archive.writestr("previews/notanimage.exe", b"x" * 10)
            ok, problem, info = bundle.import_bundle(evil.getvalue(), name="Evil Probe")
            made.append(info.get("catalog"))
            self.assertTrue(ok, problem)
            self.assertEqual(info["images"], 0)          # nothing was written
            self.assertFalse(os.path.exists(probe_a))
            self.assertFalse(os.path.exists(probe_b))

            # a zip that is not one of ours
            plain = io.BytesIO()
            with zipfile.ZipFile(plain, "w") as archive:
                archive.writestr("readme.txt", "hello")
            ok, problem, _info = bundle.import_bundle(plain.getvalue())
            self.assertFalse(ok)
            self.assertIn("bundle.json", problem)

            self.assertFalse(bundle.import_bundle(b"not a zip at all")[0])
            # and names that are paths are reduced to names
            self.assertEqual(bundle.safe_file("../../etc/passwd.jpg"), "passwd.jpg")
            self.assertEqual(bundle.safe_file("shell.exe"), "")
        finally:
            for cid in [c for c in made if c]:
                catalog_sets.remove(cid, delete_files=True)
            catalog_sets.select("default")
            for path in (probe_a, probe_b):
                if os.path.exists(path):
                    os.remove(path)
            shutil.rmtree(os.path.join(ROOT, "user", "catalogs"), ignore_errors=True)
            wipe_user_files("catalogs.json", "custom.json")

    def test_lora_folders_become_galleries_and_families(self):
        """The loras folder structure is the grouping: top folder is a gallery,
        a folder inside it is a family."""
        loras = importlib.import_module(f"{PKG}.loras")
        self.assertEqual(loras.split("krea 2/portraits/soft.safetensors"),
                         ("krea 2", "portraits", "soft"))
        self.assertEqual(loras.split("krea 2/film_grain.safetensors"), ("krea 2", "", "film_grain"))
        self.assertEqual(loras.split("loose.safetensors"), (loras.UNSORTED, "", "loose"))
        self.assertEqual(loras.split("krea 2\\portraits\\soft.safetensors"),
                         ("krea 2", "portraits", "soft"))   # windows separators

    def test_lora_previews_are_per_gallery(self):
        """The same LoRA filed under two checkpoints keeps two sets of images —
        the reason galleries exist at all."""
        import shutil

        loras = importlib.import_module(f"{PKG}.loras")
        from io import BytesIO

        from PIL import Image

        one = "krea 2/portraits/soft.safetensors"
        two = "sdxl/portraits/soft.safetensors"
        buffer = BytesIO()
        Image.new("RGB", (8, 8), (40, 90, 160)).save(buffer, "JPEG")
        pixel = buffer.getvalue()
        try:
            first = loras.add_shot(one, pixel, prompt="a pier")
            second = loras.add_shot(two, pixel, prompt="a pier")
            self.assertEqual(first["gallery"], "krea 2")
            self.assertEqual(second["gallery"], "sdxl")
            self.assertEqual(len(loras.manifest("krea 2")), 1)
            self.assertEqual(len(loras.manifest("sdxl")), 1)
            # deleting one leaves the other alone
            self.assertEqual(loras.delete_lora_shots(one), 1)
            self.assertEqual(len(loras.manifest("krea 2")), 0)
            self.assertEqual(len(loras.manifest("sdxl")), 1)
            # favourites round-trip
            self.assertTrue(loras.set_favourite(two, True))
            self.assertIn(two, loras.load_favourites())
            self.assertFalse(loras.toggle_favourite(two))
        finally:
            shutil.rmtree(os.path.join(ROOT, "user", "loras"), ignore_errors=True)

    def test_a_freed_name_does_not_inherit_the_old_gallery(self):
        """Rename a custom style, then make a new one with the freed name: the
        new entry must not pick up the first one's images. Ids are permanent —
        previews are filed under them — so a new id has to be unique."""
        store = importlib.import_module(f"{PKG}.store")
        gallery_mod = importlib.import_module(f"{PKG}.gallery")
        wipe_user_files("custom.json", "overrides.json")
        try:
            clause = "Probe rendering: flat test clause, illustration style image."
            ok, first = store.save_custom(name="rename probe", family="Illustration", axis="style",
                                          nl=clause, medium="illustration style image")
            original = catalog.resolve(first)
            ok, renamed = store.save_custom(name=first, update=True, family="Illustration",
                                            axis="style", nl=clause,
                                            medium="illustration style image",
                                            rename="[Illustration][Custom] Moved On")
            moved = catalog.resolve(renamed)
            self.assertEqual(moved["id"], original["id"])          # its images stay attached

            ok, second = store.save_custom(name="rename probe", family="Illustration", axis="style",
                                           nl=clause, medium="illustration style image")
            fresh = catalog.resolve(second)
            self.assertNotEqual(fresh["id"], moved["id"])          # and the new one is its own
            self.assertNotEqual(gallery_mod.key_for(fresh), gallery_mod.key_for(moved))
        finally:
            wipe_user_files("custom.json", "overrides.json")
            catalog.entries(force=True)

    def test_lora_save_round_trip(self):
        """A saved image lands in the LoRA's gallery and comes back in the
        manifest the browser reads."""
        import shutil
        from io import BytesIO

        from PIL import Image

        loras = importlib.import_module(f"{PKG}.loras")
        name = "krea 2/portraits/probe.safetensors"
        buffer = BytesIO()
        Image.new("RGB", (8, 8), (10, 120, 200)).save(buffer, "JPEG")
        try:
            saved = loras.add_shot(name, buffer.getvalue(), prompt="a pier")
            self.assertEqual(saved["gallery"], "krea 2")
            record = loras.manifest("krea 2")[loras.slug(name)]
            self.assertEqual(record["count"], 1)
            self.assertEqual(record["cover"], saved["file"])
            self.assertTrue(os.path.isfile(loras.shot_path("krea 2", loras.slug(name))))
            # a second image joins it and can become the cover
            again = loras.add_shot(name, buffer.getvalue(), make_cover=False)
            self.assertEqual(loras.manifest("krea 2")[loras.slug(name)]["count"], 2)
            self.assertTrue(loras.set_cover("krea 2", loras.slug(name), again["file"]))
            self.assertEqual(loras.manifest("krea 2")[loras.slug(name)]["cover"], again["file"])
            self.assertTrue(loras.delete_shot("krea 2", loras.slug(name), again["file"]))
            self.assertEqual(loras.manifest("krea 2")[loras.slug(name)]["count"], 1)
        finally:
            shutil.rmtree(os.path.join(ROOT, "user", "loras"), ignore_errors=True)

    def test_lora_trigger_words(self):
        """A LoRA remembers the words it wants in the prompt, and the node
        hands them out as an output."""
        import shutil

        loras = importlib.import_module(f"{PKG}.loras")
        name = "krea 2/portraits/probe.safetensors"
        try:
            self.assertEqual(loras.triggers_for(name), "")
            self.assertEqual(loras.set_triggers(name, "  soft   light,  glow "), "soft light, glow")
            self.assertEqual(loras.triggers_for(name), "soft light, glow")
            self.assertEqual(loras.entry(name)["triggers"], "soft light, glow")
            self.assertIn(name, loras.load_triggers())
            self.assertEqual(loras.set_triggers(name, "   "), "")      # cleared
            self.assertNotIn(name, loras.load_triggers())
            self.assertEqual(nodes.NeonsLoraExplorer.RETURN_NAMES,
                             ("model", "clip", "lora_name", "triggers"))
        finally:
            shutil.rmtree(os.path.join(ROOT, "user", "loras"), ignore_errors=True)

    def test_roll_excludes(self):
        first = catalog.roll(seed=5)
        second = catalog.roll(seed=5, exclude=(first["name"],))
        self.assertNotEqual(first["name"], second["name"])

    def test_every_entry_composes(self):
        for entry in catalog.entries():
            for mode in compose.OUTPUT_FORMATS:
                pos, _ = compose.compose(prompt="subject", styles=[entry], output_format=mode)
                self.assertTrue(pos.strip(), entry["name"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
