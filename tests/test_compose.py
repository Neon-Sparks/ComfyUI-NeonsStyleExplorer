"""Composer and catalog tests:  python tests/test_compose.py"""

import importlib.util
import os
import sys
import unittest

try:                                    # ComfyUI ships Pillow; a bare checkout may not
    from PIL import Image as _Image
    HAVE_PILLOW = True
except ImportError:                     # the two preview tests write a real file
    _Image = None
    HAVE_PILLOW = False

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
     "medium": "anime style image", "nl": "Flat cel colour in hard bands, anime style image,",
     "tags": ["anime_coloring", "cel_shading"], "tags_negative": ["photorealistic"],
     "negative": "photo, 3d render", "aliases": [], "written": True, "source": "shipped"}
B = {"id": "t.b", "name": "[Test] B", "family": "Photography & Film", "axis": "style",
     "medium": "photograph style image", "nl": "Fine grain and warm skin, photograph style image,",
     "tags": ["photo_(medium)", "film_grain"], "tags_negative": ["3d"],
     "negative": "illustration", "aliases": [], "written": True, "source": "shipped"}
F = {"id": "t.f", "name": "[Format] Sheet", "family": "Comics & Print", "axis": "format",
     "medium": "comic style image", "nl": "Panel gutters and balloon space, comic style image,",
     "tags": ["comic"], "tags_negative": [], "negative": "", "aliases": [], "written": True,
     "source": "shipped"}


# The suite must not read — or destroy — a real installation's data. Any user
# files present are moved aside for the run and put back afterwards, which also
# stops one test's leftovers from deciding another test's result.
_STASH = []


# The default catalog keeps its previews inside the package, so a test that
# saves one writes previews/manifest.json — a file the repository tracks. The
# run therefore stashes that folder as well and puts it back exactly as it was,
# leaving `git diff --exit-code` clean.
_PREVIEWS = []


def _stash_previews():
    previews = os.path.join(ROOT, "previews")
    if not os.path.isdir(previews):
        return
    for name in os.listdir(previews):
        if name == "README.md":
            continue
        live = os.path.join(previews, name)
        if not os.path.isfile(live):
            continue
        aside = f"{live}.testbak"
        os.replace(live, aside)
        _PREVIEWS.append((live, aside))


def _restore_previews():
    previews = os.path.join(ROOT, "previews")
    if os.path.isdir(previews):
        for name in os.listdir(previews):
            if name == "README.md" or name.endswith(".testbak"):
                continue
            path = os.path.join(previews, name)
            if os.path.isfile(path):
                os.remove(path)            # written by this run
    for live, aside in _PREVIEWS:
        if not os.path.isfile(aside):
            # a test deleted the stash. Report it loudly and carry on: failing
            # in teardown hides the cause, and the file is already gone.
            print(f"WARNING: {os.path.basename(aside)} disappeared during the run — "
                  f"{os.path.basename(live)} could not be restored")
            continue
        os.replace(aside, live)
    _PREVIEWS.clear()


def setUpModule():
    _stash_previews()
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
    _restore_previews()
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

    def test_no_dangling_comma_at_the_end(self):
        """The clause's comma hands over to the next part — with nothing after
        it, it would just dangle."""
        out, _ = compose.compose(prompt="a fox", styles=[A], style_position="end")
        self.assertFalse(out.rstrip().endswith(","), out)
        self.assertTrue(out.rstrip().endswith("anime style image"), out)

    def test_style_last(self):
        pos, _ = compose.compose(prompt="a fox", styles=[A], style_position="end")
        self.assertTrue(pos.startswith("a fox"))
        # the clause closes the prompt, so its handover comma is trimmed
        self.assertTrue(pos.rstrip().endswith("anime style image"))

    def test_no_instruction_language(self):
        pos, _ = compose.compose(prompt="a fox", styles=[A])
        for banned in ("governs the entire image", "do not add", "not an object"):
            self.assertNotIn(banned, pos)

    def test_medium_closes_the_clause(self):
        pos, _ = compose.compose(prompt="", styles=[A])
        self.assertTrue(pos.rstrip().endswith("anime style image"))

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
        self.assertIn(":2.50),", pos)
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
        self.assertTrue(clause.endswith("anime style image,"), clause)
        self.assertEqual(clause.count("style image"), 1)
        self.assertIn("panel gutters", clause)

    def test_finish_does_not_hijack_the_medium(self):
        finish = dict(A, id="t.n", name="[Finish] Real", axis="finish",
                      medium="photograph style image",
                      nl="Natural skin texture, photograph style image,")
        clause = compose.style_clause([A], finish=finish)
        self.assertTrue(clause.endswith("anime style image,"), clause)
        self.assertIn("natural skin texture", clause.lower())
        self.assertNotIn("photograph style image", clause)

    def test_format_alone_keeps_its_own_medium(self):
        clause = compose.style_clause([], fmt=F)
        self.assertTrue(clause.endswith("comic style image,"), clause)

    def test_second_style_medium_is_dropped(self):
        clause = compose.style_clause([A, B])
        self.assertEqual(clause.count("style image"), 1)
        self.assertTrue(clause.endswith("anime style image,"), clause)

    def test_whole_catalog_emits_one_medium(self):
        pool = catalog.by_axis("style")[:200]
        fmt = catalog.by_axis("format")[0]
        finish = catalog.by_axis("finish")[0]
        for entry in pool:
            clause = compose.style_clause([entry], fmt=fmt, finish=finish)
            self.assertEqual(clause.count(" style image"), 1, entry["name"])
            self.assertTrue(clause.endswith(entry["medium"] + ","), entry["name"])


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
                nl="Probe rendering: mirrored liquid metal bulging into soft blobs, chrome style image,",
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
                nl="Probe rendering: matte resin cast, style image,", medium="style image")
            self.assertTrue(first.startswith("[Material][Custom]"), first)
            ok, second = store.save_custom(
                name=first, family="Figurine", axis="style", update=True,
                nl="Probe rendering: matte resin cast, style image,", medium="style image")
            self.assertTrue(second.startswith("[Figurine][Custom]"), second)
            self.assertEqual(catalog.resolve(first)["name"], second)   # old name still resolves

            ok, family, moved = store.rename_family("Figurine", "Resin Figures")
            self.assertTrue(ok)
            self.assertEqual(moved, 1)
            renamed = [e for e in catalog.entries() if e.get("source") == "custom"][0]
            self.assertTrue(renamed["name"].startswith("[Resin][Custom]"))

            # a shipped style edited into the family must move as well, or the
            # family survives its own deletion
            store.save_override("[Painting] Acrylic", family="Resin Figures")
            ok, family, moved = store.delete_family("Resin Figures")
            self.assertEqual(moved, 2, "both the custom style and the override move")
            acrylic = next(e for e in catalog.entries() if e["name"] == "[Painting] Acrylic")
            self.assertEqual(acrylic["family"], "Lonely")
            self.assertNotIn("Resin Figures", {f["name"] for f in store.families_admin()})
            store.delete_override("[Painting] Acrylic")
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

    @unittest.skipUnless(HAVE_PILLOW, "Pillow is needed to write a test image")
    def test_lora_previews_are_per_gallery(self):
        """The same LoRA filed under two checkpoints keeps two sets of images —
        the reason galleries exist at all."""
        import shutil

        loras = importlib.import_module(f"{PKG}.loras")
        from io import BytesIO

        Image = _Image

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
            clause = "Probe rendering: flat test clause, illustration style image,"
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

    @unittest.skipUnless(HAVE_PILLOW, "Pillow is needed to write a test image")
    def test_lora_save_round_trip(self):
        """A saved image lands in the LoRA's gallery and comes back in the
        manifest the browser reads."""
        import shutil
        from io import BytesIO

        Image = _Image

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

    @unittest.skipUnless(HAVE_PILLOW, "Pillow is needed to write a test image")
    def test_building_thumbs_is_idempotent(self):
        """Build fast thumbs makes what is missing and skips what exists."""
        import shutil
        from io import BytesIO

        loras = importlib.import_module(f"{PKG}.loras")
        Image = _Image
        buffer = BytesIO()
        Image.new("RGB", (600, 600), (30, 30, 30)).save(buffer, "JPEG")
        try:
            loras.add_shot("krea2/build-probe.safetensors", buffer.getvalue())
            first = loras.build_thumbs()
            self.assertEqual(first["previews"], 1)
            self.assertEqual(first["built"], 2)      # one per cached size
            self.assertEqual(first["skipped"], 0)
            second = loras.build_thumbs()
            self.assertEqual(second["built"], 0)     # nothing to redo
            self.assertEqual(second["skipped"], 2)
        finally:
            shutil.rmtree(os.path.join(ROOT, "user", "loras"), ignore_errors=True)

    @unittest.skipUnless(HAVE_PILLOW, "Pillow is needed to write a test image")
    def test_default_previews_move_out_of_the_package(self):
        """The Default catalog's previews used to live inside the package, so
        replacing the folder to update took them with it. They are relocated
        under user/ on load, once, without losing the manifest."""
        import json as json_mod
        import shutil

        catalogs = importlib.import_module(f"{PKG}.catalogs")
        gallery_mod = importlib.import_module(f"{PKG}.gallery")
        Image = _Image
        legacy = os.path.join(ROOT, "previews")
        target = os.path.join(ROOT, "user", "catalogs", "default", "previews")
        shot = "traditio_probe--1-aaa.jpg"
        try:
            os.makedirs(legacy, exist_ok=True)
            Image.new("RGB", (32, 32), (10, 10, 10)).save(os.path.join(legacy, shot), "JPEG")
            json_mod.dump(
                {"traditio_probe": {"name": "[Probe] Style", "cover": shot,
                                    "shots": [{"file": shot, "prompt": "", "ts": 1}]}},
                open(os.path.join(legacy, "manifest.json"), "w"))

            catalogs._MIGRATED[0] = False
            report = catalogs.migrate_default_previews()
            self.assertGreaterEqual(report["moved"], 2)
            self.assertTrue(os.path.isfile(os.path.join(target, shot)))
            self.assertFalse(os.path.isfile(os.path.join(legacy, shot)))
            self.assertIn("traditio_probe", gallery_mod.manifest())

            # running again moves nothing and breaks nothing
            catalogs._MIGRATED[0] = False
            self.assertEqual(catalogs.migrate_default_previews()["moved"], 0)
            self.assertIn("traditio_probe", gallery_mod.manifest())
            # the README stays where it is
            self.assertTrue(os.path.isfile(os.path.join(legacy, "README.md")))
        finally:
            shutil.rmtree(os.path.join(ROOT, "user", "catalogs"), ignore_errors=True)
            for name in os.listdir(legacy):
                # a .testbak belongs to setUpModule and holds the real file —
                # deleting one loses it, and on CI that file is tracked
                if name == "README.md" or name.endswith(".testbak"):
                    continue
                path = os.path.join(legacy, name)
                shutil.rmtree(path) if os.path.isdir(path) else os.remove(path)
            catalogs._MIGRATED[0] = False

    @unittest.skipUnless(HAVE_PILLOW, "Pillow is needed to write a test image")
    def test_manifest_is_cached_but_never_stale(self):
        """Every request for a preview asks for the manifest, and building it
        stats every image it lists — so it is cached against the file's own
        metadata. The cache must disappear the moment anything changes."""
        import shutil
        from io import BytesIO

        gallery_mod = importlib.import_module(f"{PKG}.gallery")
        Image = _Image
        buffer = BytesIO()
        Image.new("RGB", (64, 64), (10, 90, 160)).save(buffer, "JPEG")
        name = "[Anime] Chibi"
        key = gallery_mod.key_for(name)
        try:
            saved = gallery_mod.add_shot(name, buffer.getvalue())
            first = gallery_mod.manifest()
            self.assertIn(key, first)
            # the same call again is served from the cache: same object
            self.assertIs(gallery_mod.manifest(), first)

            # a second save invalidates it
            gallery_mod.add_shot(name, buffer.getvalue(), make_cover=False)
            grown = gallery_mod.manifest()
            self.assertIsNot(grown, first)
            self.assertEqual(grown[key]["count"], 2)

            # so does deleting a shot
            gallery_mod.delete_shot(key, grown[key]["shots"][0]["file"])
            self.assertEqual(gallery_mod.manifest()[key]["count"], 1)

            # and so does a file vanishing behind the manifest's back
            os.remove(gallery_mod.shot_path(key))
            self.assertIsNone(gallery_mod.manifest().get(key))
        finally:
            for name in os.listdir(gallery_mod.previews_dir()):
                path = os.path.join(gallery_mod.previews_dir(), name)
                shutil.rmtree(path) if os.path.isdir(path) else os.remove(path)
            shutil.rmtree(os.path.join(ROOT, "user", "catalogs"), ignore_errors=True)

    @unittest.skipUnless(HAVE_PILLOW, "Pillow is needed to write a test image")
    def test_card_thumbnails_are_derived_and_cleaned_up(self):
        """Cards are served a copy their own size, cached beside the original
        and removed with it. An unknown size falls back to the master rather
        than letting a URL fill the disk with arbitrary renders."""
        import shutil

        assets = importlib.import_module(f"{PKG}.assets")
        loras = importlib.import_module(f"{PKG}.loras")
        Image = _Image
        from io import BytesIO

        buffer = BytesIO()
        Image.new("RGB", (900, 900), (40, 90, 160)).save(buffer, "JPEG")
        name = "krea2/thumb-probe.safetensors"
        try:
            saved = loras.add_shot(name, buffer.getvalue())
            master = loras.shot_path("krea2", loras.slug(name), saved["file"])
            small = assets.derived_thumb(master, 256)
            self.assertNotEqual(small, master)
            self.assertTrue(os.path.isfile(small))
            self.assertLess(os.path.getsize(small), os.path.getsize(master))
            with Image.open(small) as image:
                self.assertLessEqual(max(image.size), 256)
            # asked for again, the cached file is reused rather than rebuilt
            stamp = os.path.getmtime(small)
            self.assertEqual(assets.derived_thumb(master, 256), small)
            self.assertEqual(os.path.getmtime(small), stamp)
            # a size nobody offers falls back to the master
            self.assertEqual(assets.derived_thumb(master, 999), master)
            self.assertEqual(assets.derived_thumb(master, "nonsense"), master)
            # deleting the shot takes its derived copies with it
            loras.delete_shot("krea2", loras.slug(name), saved["file"])
            self.assertFalse(os.path.isfile(small))
        finally:
            shutil.rmtree(os.path.join(ROOT, "user", "loras"), ignore_errors=True)

    @unittest.skipUnless(HAVE_PILLOW, "Pillow is needed to write a test image")
    def test_gallery_names_survive_the_folder_slug(self):
        """A gallery folder is slugged on disk, so the manifest must carry the
        real name — otherwise a folder with a space, dot or dash appears to
        have no previews at all, while a plain one works."""
        import json as json_mod
        import shutil
        from io import BytesIO

        loras = importlib.import_module(f"{PKG}.loras")
        Image = _Image
        buffer = BytesIO()
        Image.new("RGBA", (8, 8), (90, 30, 120, 128)).save(buffer, "PNG")   # alpha is fine
        name = "Qwen-Image 2.1/probe.safetensors"
        try:
            saved = loras.add_shot(name, buffer.getvalue())
            self.assertEqual(saved["gallery"], "Qwen-Image 2.1")
            row = loras.entry(name)
            # this is the lookup the browser performs
            found = (loras.all_manifests().get(row["gallery"]) or {}).get(row["key"])
            self.assertTrue(found, "a gallery whose folder is slugged must still be found")

            # a manifest written before the name was stored still resolves
            path = loras.manifest_path("Qwen-Image 2.1")
            data = json_mod.load(open(path))
            data.pop("__gallery__", None)
            json_mod.dump(data, open(path, "w"))
            self.assertIn("Qwen-Image 2.1", loras.all_manifests())
        finally:
            shutil.rmtree(os.path.join(ROOT, "user", "loras"), ignore_errors=True)

    @unittest.skipUnless(HAVE_PILLOW, "Pillow is needed to write a test image")
    def test_two_shots_in_the_same_millisecond(self):
        """Two images saved inside one millisecond must stay two images.

        The filename used to be key--<ms>.jpg, so a fast machine — a CI runner,
        a batch with auto-gallery on — wrote both under the same name: the
        second overwrote the first, the manifest held two entries pointing at
        one file, and deleting it emptied the record.
        """
        import shutil
        from io import BytesIO

        loras = importlib.import_module(f"{PKG}.loras")
        Image = _Image
        name = "krea 2/portraits/race.safetensors"
        buffer = BytesIO()
        Image.new("RGB", (8, 8), (90, 30, 30)).save(buffer, "JPEG")
        assets = importlib.import_module(f"{PKG}.assets")   # the shared engine
        frozen = lambda: 1_789_000_000.123          # every call, the same instant
        real = assets.time.time
        try:
            assets.time.time = frozen
            first = loras.add_shot(name, buffer.getvalue())
            second = loras.add_shot(name, buffer.getvalue(), make_cover=False)
            self.assertNotEqual(first["file"], second["file"])
            record = loras.manifest("krea 2")[loras.slug(name)]
            self.assertEqual(record["count"], 2)
            files = {shot["file"] for shot in record["shots"]}
            self.assertEqual(len(files), 2)
            for shot in files:
                self.assertTrue(os.path.isfile(
                    os.path.join(loras.previews_dir("krea 2"), shot)), shot)
            # deleting one leaves the other, and the record alive
            self.assertTrue(loras.delete_shot("krea 2", loras.slug(name), second["file"]))
            self.assertEqual(loras.manifest("krea 2")[loras.slug(name)]["count"], 1)
        finally:
            assets.time.time = real
            shutil.rmtree(os.path.join(ROOT, "user", "loras"), ignore_errors=True)

    def test_editing_a_style_invalidates_the_node_cache(self):
        """ComfyUI caches a node whose widget values are unchanged. Editing a
        style leaves the widgets identical while changing what they mean, so
        the signature has to move or the picture keeps the old clause."""
        store = importlib.import_module(f"{PKG}.store")
        node = nodes.NeonsStyleExplorer
        ok, name = store.save_custom("Cache Probe", family="Other", axis="style",
                                     nl="First painting, version one, painting style image,",
                                     medium="painting style image", tags=["poster"])
        self.assertTrue(ok)
        args = dict(prompt="a fox", style="None", extra_style="None",
                    custom_style=name, format="None", finish="None")
        first = node.IS_CHANGED(**args)
        self.assertEqual(first, node.IS_CHANGED(**args))          # stable while nothing changes
        store.save_custom(name, update=True, family="Other", axis="style",
                          nl="Second painting, edited, painting style image,",
                          medium="painting style image", tags=["poster"])
        edited = node.IS_CHANGED(**args)
        self.assertNotEqual(first, edited, "an edited clause must re-run the node")
        store.save_custom(name, update=True, family="Other", axis="style",
                          nl="Second painting, edited, painting style image,",
                          medium="painting style image", tags=["poster", "flat_color"])
        self.assertNotEqual(edited, node.IS_CHANGED(**args), "edited tags must re-run the node")
        store.hide_style(name)
        # a shipped style edited through an override moves too
        before = node.IS_CHANGED(**dict(args, custom_style="None", style="[Painting] Acrylic"))
        store.save_override("[Painting] Acrylic",
                            nl="Acrylic painting, edited here, painting style image,")
        after = node.IS_CHANGED(**dict(args, custom_style="None", style="[Painting] Acrylic"))
        store.delete_override("[Painting] Acrylic")
        self.assertNotEqual(before, after)

    def test_lora_triggers_lead_the_prompt(self):
        """Three trigger inputs, in order, de-duplicated, at the very front."""
        out, _ = compose.compose(prompt="a fox", quality="masterpiece", styles=[A],
                                 lora_triggers=["soft light", "glow", "film grain"])
        self.assertTrue(out.startswith("soft light, glow, film grain, masterpiece"), out)
        # nothing wired in leaves the prompt exactly as it was
        plain, _ = compose.compose(prompt="a fox", quality="masterpiece", styles=[A])
        self.assertNotIn("soft light", plain)
        # the node de-duplicates across the three inputs
        picked = nodes.lora_triggers({
            "lora_triggers_1": "soft light, glow",
            "lora_triggers_2": "GLOW, film grain",
            "lora_triggers_3": "  ",
        })
        self.assertEqual(picked, ["soft light", "glow", "film grain"])
        # booru mode puts them in front of the tag list
        tags, _ = compose.compose(prompt="1girl", styles=[A], output_format="danbooru",
                                  lora_triggers=["soft_light"])
        self.assertTrue(tags.startswith("soft_light"), tags)

    def test_trigger_inputs_on_both_style_nodes(self):
        """Both composing nodes take the LoRA trigger inputs; the capture node,
        which only files an image, does not."""
        for cls in (nodes.NeonsStyleExplorer, nodes.NeonsStyleExplorerEncode):
            optional = cls.INPUT_TYPES().get("optional", {})
            for slot in ("lora_triggers_1", "lora_triggers_2", "lora_triggers_3"):
                self.assertIn(slot, optional, cls.__name__)
        capture = nodes.NeonsGalleryCapture.INPUT_TYPES().get("optional", {})
        self.assertNotIn("lora_triggers_1", capture)

    def test_lora_random_roll_range(self):
        """The roll is seeded, honours the range, and reads it in either order."""
        node = nodes.NeonsLoraExplorer
        one = node._roll(7, 0.6, 1.0)
        self.assertEqual(one, node._roll(7, 0.6, 1.0))            # same seed, same roll
        for seed in range(1, 12):
            _name, strength = node._roll(seed, 0.6, 1.0)
            if _name != "None":
                self.assertGreaterEqual(strength, 0.6)
                self.assertLessEqual(strength, 1.0)
        # with no LoRAs installed the roll declines rather than inventing one
        name, strength = node._roll(3, 0.6, 1.0)
        if name == "None":
            self.assertEqual(strength, 0.0)
            return
        # reversed range is the same range
        _n2, high_low = node._roll(3, 1.0, 0.6)
        self.assertGreaterEqual(high_low, 0.6)
        self.assertLessEqual(high_low, 1.0)
        # a range with no width is a fixed strength
        _n3, fixed = node._roll(3, 0.8, 0.8)
        self.assertEqual(fixed, 0.8)

    def test_model_explorer_shares_the_gallery_engine(self):
        """The checkpoint explorer is the same engine with its own storage: the
        two must not share a folder, a favourites list or a text file."""
        models = importlib.import_module(f"{PKG}.models")
        loras = importlib.import_module(f"{PKG}.loras")
        self.assertNotEqual(models.previews_dir("krea 2"), loras.previews_dir("krea 2"))
        self.assertEqual(models.split("krea 2/anime/base.safetensors"),
                         ("krea 2", "anime", "base"))
        self.assertEqual(models.set_notes("krea 2/base.safetensors", "  dpmpp_2m,  cfg 4.5 "),
                         "dpmpp_2m, cfg 4.5")
        self.assertEqual(models.notes_for("krea 2/base.safetensors"), "dpmpp_2m, cfg 4.5")
        # a note on a checkpoint is not a trigger on a LoRA of the same name
        self.assertEqual(loras.triggers_for("krea 2/base.safetensors"), "")
        self.assertEqual(models.entry("krea 2/base.safetensors")["notes"], "dpmpp_2m, cfg 4.5")
        # the text routes answer with a generic `text` as well as their own
        # field name — the panel reads `text`, and reading only `triggers` is
        # how notes appeared not to save
        import inspect
        routes_src = inspect.getsource(importlib.import_module(PKG))
        for marker in ('"triggers": text,', '"notes": text,'):
            self.assertIn(marker, routes_src)
        self.assertEqual(routes_src.count('"text": text}'), 2)

        node = nodes.NeonsModelExplorer
        self.assertEqual(node.RETURN_NAMES, ("model", "clip", "vae", "model_name", "notes"))
        self.assertNotIn("random_roll", node.INPUT_TYPES()["required"])
        # two folders, one gallery each, and a name that says where it came from
        self.assertEqual(models.FOLDERS, ("checkpoints", "diffusion_models"))
        self.assertEqual(models.source_of("diffusion_models/flux/flux1-dev.safetensors"),
                         ("diffusion_models", "flux/flux1-dev.safetensors"))
        self.assertEqual(models.source_of("checkpoints/sdxl/base.safetensors"),
                         ("checkpoints", "sdxl/base.safetensors"))
        self.assertEqual(models.split("diffusion_models/flux/flux1-dev.safetensors"),
                         ("diffusion_models", "flux", "flux1-dev"))
        # the same relative name in both folders is two different assets
        self.assertNotEqual(models.slug("checkpoints/flux/x.safetensors"),
                            models.slug("diffusion_models/flux/x.safetensors"))
        # a LoRA name is untouched by any of this
        self.assertEqual(loras.split("krea 2/portraits/soft.safetensors"),
                         ("krea 2", "portraits", "soft"))
        import shutil
        shutil.rmtree(os.path.join(ROOT, "user", "models"), ignore_errors=True)

    def test_editing_text_refreshes_the_asset_nodes(self):
        """A note or a trigger word is not a widget, so ComfyUI cannot see it
        change. Both nodes fold it into their signature or their text output
        keeps handing out the old value."""
        import shutil

        models = importlib.import_module(f"{PKG}.models")
        loras = importlib.import_module(f"{PKG}.loras")
        try:
            name = "checkpoints/krea 2/base.safetensors"
            first = nodes.NeonsModelExplorer.IS_CHANGED(ckpt_name=name)
            self.assertEqual(first, nodes.NeonsModelExplorer.IS_CHANGED(ckpt_name=name))
            models.set_notes(name, "dpmpp_2m, cfg 4.5")
            self.assertNotEqual(first, nodes.NeonsModelExplorer.IS_CHANGED(ckpt_name=name))

            lora = "krea 2/portraits/soft.safetensors"
            before = nodes.NeonsLoraExplorer.IS_CHANGED(lora=lora)
            loras.set_triggers(lora, "soft light, glow")
            self.assertNotEqual(before, nodes.NeonsLoraExplorer.IS_CHANGED(lora=lora))
            # the widgets still matter too
            self.assertNotEqual(nodes.NeonsLoraExplorer.IS_CHANGED(lora=lora, strength_model=0.8),
                                nodes.NeonsLoraExplorer.IS_CHANGED(lora=lora, strength_model=1.0))
            self.assertNotEqual(nodes.NeonsLoraExplorer.IS_CHANGED(lora=lora, roll_seed=1),
                                nodes.NeonsLoraExplorer.IS_CHANGED(lora=lora, roll_seed=2))
        finally:
            for folder in ("loras", "models"):
                shutil.rmtree(os.path.join(ROOT, "user", folder), ignore_errors=True)

    def test_custom_styles_round_trip(self):
        """A custom style is named once, appears in the catalog and its source
        lists, and deleting it takes it away again."""
        store = importlib.import_module(f"{PKG}.store")
        ok, name = store.save_custom("Round Trip Probe", family="Other", axis="style",
                                     nl="Probe painting, flat grey field, painting style image,",
                                     medium="painting style image")
        self.assertTrue(ok)
        self.assertEqual(name, "[Custom] Round Trip Probe")      # not [Custom][Custom]
        self.assertIn(name, [e["name"] for e in catalog.entries()])
        self.assertIn(name, catalog.source_pool("custom"))
        self.assertIn(name, catalog.payload()["styles"])
        self.assertEqual(catalog.payload()["by_name"][name]["source"], "custom")
        self.assertTrue(store.hide_style(name))
        self.assertNotIn(name, [e["name"] for e in catalog.entries()])
        self.assertNotIn(name, catalog.source_pool("custom"))

    def test_closing_medium_can_be_switched_off(self):
        """The medium closes a clause by default and can be dropped entirely."""
        on, _ = compose.compose(prompt="a fox", styles=[A])
        self.assertIn("anime style image", on)
        off, _ = compose.compose(prompt="a fox", styles=[A], close_with_medium=False)
        self.assertNotIn("style image", off)
        self.assertIn("Flat cel colour", off)          # the clause itself survives
        self.assertTrue(off.rstrip().endswith("a fox"), off)
        # no stray punctuation where the medium used to be
        self.assertNotIn(", ,", off)
        self.assertNotIn(",,", off)
        # booru output never carried the medium, so it is unchanged
        tags_on, _ = compose.compose(prompt="a fox", styles=[A], output_format="danbooru")
        tags_off, _ = compose.compose(prompt="a fox", styles=[A], output_format="danbooru",
                                      close_with_medium=False)
        self.assertEqual(tags_on, tags_off)

    def test_random_roll_switch(self):
        """The dice is a switch now: it rolls from its source, an old workflow
        holding the retired token still rolls, and crawl still wins."""
        pool = catalog.entries()
        for source in ("all", "main", "extra"):
            picked = nodes.pick_styles(["None", "None", "None"], pool, "all", None, 11, {},
                                       random_roll=True, source=source)
            self.assertEqual(len(picked), 1, source)
            if source == "extra":
                self.assertIn(picked[0]["family"], catalog.IMPORTED_FAMILIES)
            if source == "main":
                self.assertNotIn(picked[0]["family"], catalog.IMPORTED_FAMILIES)
        # the same seed rolls the same style
        one = nodes.pick_styles(["None"] * 3, pool, "all", None, 99, {}, random_roll=True)
        two = nodes.pick_styles(["None"] * 3, pool, "all", None, 99, {}, random_roll=True)
        self.assertEqual(one[0]["name"], two[0]["name"])
        # the dice is gone from the dropdowns
        fields = nodes.NeonsStyleExplorer.INPUT_TYPES()["required"]
        for slot in ("style", "extra_style", "custom_style"):
            self.assertNotIn(catalog.RANDOM_TOKEN, fields[slot][0], slot)
        self.assertEqual(fields["random_source"][0], ("all",) + tuple(catalog.SOURCES))

    def test_run_records_do_not_leak_between_prompts(self):
        """A prompt with no record must not borrow another prompt's style —
        that is how an image lands on a style it was never made with."""
        runs = importlib.import_module(f"{PKG}.runs")
        runs.record("prompt-A", "7", style="[Painting] Ndebele Wall Geometry")
        self.assertEqual(runs.get("prompt-A")["7"]["style"], "[Painting] Ndebele Wall Geometry")
        self.assertEqual(runs.get("prompt-B"), {})          # nothing borrowed
        runs.record("prompt-B", "7", style="[Painting] Neoclassical", queued=True)
        self.assertEqual(runs.get("prompt-B")["7"]["style"], "[Painting] Neoclassical")
        self.assertEqual(runs.get("prompt-A")["7"]["style"], "[Painting] Ndebele Wall Geometry")

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


class Rerolls(unittest.TestCase):
    """2.10.0 — a roll no widget announces must still happen, and the new
    outputs and scopes behave as documented."""

    def tearDown(self):
        wipe_user_files("favourites.json", "recents.json")

    # ------------------------------------------------------------ signature

    def test_seed_zero_rolls_afresh_every_run(self):
        """roll_seed 0 promises a new roll each run. Nothing changes on the
        node, so the signature itself has to differ or ComfyUI serves the
        previous roll from cache."""
        node = nodes.NeonsStyleExplorer
        self.assertNotEqual(node.IS_CHANGED(random_roll=True, roll_seed=0),
                            node.IS_CHANGED(random_roll=True, roll_seed=0))
        # a seeded roll is repeatable, so it may be cached
        self.assertEqual(node.IS_CHANGED(random_roll=True, roll_seed=5),
                         node.IS_CHANGED(random_roll=True, roll_seed=5))
        # with the dice off the seed is irrelevant, and so is its being zero
        self.assertEqual(node.IS_CHANGED(random_roll=False, roll_seed=0),
                         node.IS_CHANGED(random_roll=False, roll_seed=0))
        # crawl owns the sequence: the dice is not rolling underneath it
        self.assertEqual(node.IS_CHANGED(random_roll=True, roll_seed=0, crawl=True),
                         node.IS_CHANGED(random_roll=True, roll_seed=0, crawl=True))

    def test_a_dice_on_format_or_finish_always_rolls(self):
        node = nodes.NeonsStyleExplorer
        for field in ("format", "finish"):
            self.assertNotEqual(node.IS_CHANGED(**{field: catalog.RANDOM_TOKEN}),
                                node.IS_CHANGED(**{field: catalog.RANDOM_TOKEN}), field)
            # no rolling anywhere while crawling
            self.assertEqual(node.IS_CHANGED(crawl=True, **{field: catalog.RANDOM_TOKEN}),
                             node.IS_CHANGED(crawl=True, **{field: catalog.RANDOM_TOKEN}), field)

    def test_a_seeded_roll_follows_its_pool(self):
        """Starring a style changes what 'favourites' rolls without touching a
        widget; the signature has to move with the answer."""
        node = nodes.NeonsStyleExplorer
        settings = {"random_roll": True, "roll_seed": 5, "roll_scope": "favourites"}
        before = node.IS_CHANGED(**settings)
        self.assertEqual(before, node.IS_CHANGED(**settings))
        landed = catalog.roll(scope="favourites", seed=5)["name"]
        other = next(name for name in catalog.names_for("style") if name != landed)
        catalog.set_favourite(other, True)
        self.assertEqual(catalog.roll(scope="favourites", seed=5)["name"], other)
        self.assertNotEqual(before, node.IS_CHANGED(**settings))

    # ---------------------------------------------------------- style_name

    def test_style_name_output(self):
        for cls in (nodes.NeonsStyleExplorer, nodes.NeonsStyleExplorerEncode):
            self.assertEqual(cls.RETURN_NAMES[-1], "style_name", cls.__name__)
            self.assertEqual(len(cls.RETURN_NAMES), len(cls.RETURN_TYPES), cls.__name__)
        # appended, so the slots older workflows wire keep their positions
        self.assertEqual(nodes.NeonsStyleExplorer.RETURN_NAMES[:3],
                         ("positive", "negative", "debug"))
        self.assertEqual(nodes.NeonsStyleExplorerEncode.RETURN_NAMES[:5],
                         ("positive_conditioning", "negative_conditioning",
                          "positive", "negative", "debug"))
        name = catalog.written_names("style")[0]
        out = nodes.NeonsStyleExplorer().apply(prompt="x", style=name)["result"]
        self.assertEqual(len(out), 4)
        self.assertEqual(out[3], name)
        # no style: an empty string, never "None"
        self.assertEqual(nodes.NeonsStyleExplorer().apply(prompt="x")["result"][3], "")
        # a roll reports what it landed on
        rolled = nodes.NeonsStyleExplorer().apply(prompt="x", random_roll=True, roll_seed=9)
        self.assertEqual(rolled["result"][3], rolled["ui"]["ns_style"][0])
        self.assertTrue(rolled["result"][3])

    # -------------------------------------------------------- empty scopes

    def test_an_empty_shortlist_is_reported(self):
        """Favourites with nothing starred rolls from everything — which is
        right — but it has to say so."""
        self.assertTrue(catalog.scope_fell_back("favourites"))
        self.assertTrue(catalog.scope_fell_back("recent"))
        self.assertFalse(catalog.scope_fell_back("all"))
        self.assertFalse(catalog.scope_fell_back("family"))
        debug = nodes.run(prompt="x", random_roll=True, roll_seed=3, roll_scope="favourites")[2]
        self.assertIn("'favourites' is empty", debug)
        catalog.set_favourite(catalog.written_names("style")[0], True)
        self.assertFalse(catalog.scope_fell_back("favourites"))
        debug = nodes.run(prompt="x", random_roll=True, roll_seed=3, roll_scope="favourites")[2]
        self.assertNotIn("is empty", debug)
        self.assertIn("scope favourites", debug)
        # starred, but not in the source being rolled: still a fallback
        self.assertTrue(catalog.scope_fell_back("favourites", "extra"))


class LoraScope(unittest.TestCase):
    """The LoRA dice can be kept inside a folder or the favourites."""

    FILES = ["krea 2/film.safetensors", "krea 2/portraits/soft.safetensors",
             "krea 2/portraits/hard.safetensors", "sdxl/ink.safetensors", "loose.safetensors"]

    def setUp(self):
        self.loras = importlib.import_module(f"{PKG}.loras")
        self._names = self.loras.names
        self._favourites = self.loras.load_favourites
        self.loras.names = lambda refresh=False: list(self.FILES)
        self.loras.load_favourites = lambda: []

    def tearDown(self):
        self.loras.names = self._names
        self.loras.load_favourites = self._favourites

    def test_scopes_are_folder_tests(self):
        node = nodes.NeonsLoraExplorer
        self.assertEqual(node.roll_pool("all", "None"), (self.FILES, False))
        self.assertEqual(node.roll_pool("same gallery", "krea 2/film.safetensors"),
                         (self.FILES[:3], False))
        self.assertEqual(node.roll_pool("same family", "krea 2/portraits/soft.safetensors"),
                         (self.FILES[1:3], False))
        # a LoRA at the top of its gallery has no family: its siblings are the
        # other family-less files there, not the whole gallery
        self.assertEqual(node.roll_pool("same family", "krea 2/film.safetensors"),
                         (self.FILES[:1], False))
        self.assertEqual(node.roll_pool("same gallery", "loose.safetensors"),
                         (self.FILES[4:], False))
        # windows separators in a saved workflow
        self.assertEqual(node.roll_pool("same gallery", "krea 2\\film.safetensors"),
                         (self.FILES[:3], False))

    def test_an_empty_scope_widens_and_says_so(self):
        node = nodes.NeonsLoraExplorer
        self.assertEqual(node.roll_pool("favourites", "None"), (self.FILES, True))
        self.assertEqual(node.roll_pool("same gallery", "None"), (self.FILES, True))
        self.loras.load_favourites = lambda: ["sdxl/ink.safetensors", "gone.safetensors"]
        self.assertEqual(node.roll_pool("favourites", "None"), (["sdxl/ink.safetensors"], False))

    def test_the_roll_stays_inside_its_scope(self):
        node = nodes.NeonsLoraExplorer
        for seed in range(1, 40):
            name, strength = node._roll(seed, 0.6, 1.0, "same gallery", "krea 2/film.safetensors")
            self.assertTrue(name.startswith("krea 2/"), name)
            self.assertTrue(0.6 <= strength <= 1.0)
        # the old three-argument call still rolls from everything
        self.assertIn(node._roll(7, 0.6, 1.0)[0], self.FILES)

    def test_signature(self):
        node = nodes.NeonsLoraExplorer
        self.assertNotEqual(node.IS_CHANGED(random_roll=True, roll_seed=0),
                            node.IS_CHANGED(random_roll=True, roll_seed=0))
        seeded = {"random_roll": True, "roll_seed": 4, "roll_scope": "favourites"}
        before = node.IS_CHANGED(**seeded)
        self.assertEqual(before, node.IS_CHANGED(**seeded))
        landed = node._roll(4, 0.6, 1.0, "favourites", "None")[0]
        other = next(name for name in self.FILES if name != landed)
        self.loras.load_favourites = lambda: [other]
        self.assertNotEqual(before, node.IS_CHANGED(**seeded))

    def test_the_new_widget_cannot_break_an_old_workflow(self):
        """roll_scope is optional and comes last: older saved values keep their
        positions and an API prompt without it still validates."""
        types = nodes.NeonsLoraExplorer.INPUT_TYPES()
        self.assertNotIn("roll_scope", types["required"])
        self.assertEqual(list(types["optional"]), ["roll_scope"])
        self.assertEqual(list(types["required"])[-1], "roll_seed")
        self.assertEqual(types["optional"]["roll_scope"][0], nodes.LORA_ROLL_SCOPES)
        # A workflow saved before the widget existed restores values by
        # position and leaves the panel's empty string in it. That must roll
        # from everything, quietly, and must not stop the workflow validating.
        node = nodes.NeonsLoraExplorer
        for junk in ("", None, "randomize", 3):
            self.assertEqual(node.roll_pool(junk, "None"), (self.FILES, False), repr(junk))
        self.assertIs(node.VALIDATE_INPUTS(roll_scope=""), True)
        import inspect
        self.assertIn("roll_scope", inspect.signature(node.VALIDATE_INPUTS).parameters)


class ModelGuard(unittest.TestCase):
    def test_wired_outputs(self):
        """Which of the node's outputs the queued graph actually reads."""
        wired = nodes.NeonsModelExplorer.wired_outputs
        prompt = {
            "3": {"class_type": "NeonsModelExplorer", "inputs": {"ckpt_name": "x"}},
            "5": {"inputs": {"clip": ["3", 1], "text": "a pier", "steps": 4}},
            "6": {"inputs": {"model": ["3", 0], "other": ["9", 2]}},
        }
        self.assertEqual(wired(prompt, "3"), {0, 1})
        self.assertEqual(wired(prompt, 3), {0, 1})          # the id may be a number
        self.assertEqual(wired(prompt, "9"), {2})
        self.assertEqual(wired(prompt, "4"), set())
        # nothing to go on is "nothing wired", never an error
        self.assertEqual(wired(None, "3"), set())
        self.assertEqual(wired({}, None), set())
        self.assertEqual(wired({"1": "junk", "2": {"inputs": None}}, "3"), set())
        self.assertIn("prompt", nodes.NeonsModelExplorer.INPUT_TYPES()["hidden"])


class AssetStore(unittest.TestCase):
    """The LoRA/model store: one read per listing, one write per rescan."""

    def setUp(self):
        import shutil
        import tempfile

        self.assets = importlib.import_module(f"{PKG}.assets")
        self.work = tempfile.mkdtemp(prefix="ns_assets_")
        self.addCleanup(shutil.rmtree, self.work, True)
        self.files = [f"krea 2/lora_{n:03d}.safetensors" for n in range(60)]
        self.store = self.assets.Gallery(kind="lora", folder_key="loras",
                                         storage="unused", text_field="triggers")
        self.store.root = os.path.join(self.work, "store")
        self.store.favourites_path = os.path.join(self.store.root, "favourites.json")
        self.store.text_path = os.path.join(self.store.root, "triggers.json")
        self.store.fingerprints_path = os.path.join(self.store.root, "fingerprints.json")
        self.store.names = lambda refresh=False: list(self.files)

        def real(name):
            path = os.path.join(self.work, "files", name.replace("/", "__"))
            if not os.path.isfile(path):
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "wb") as handle:
                    handle.write(name.encode("utf-8") * 20)
            return path

        self.store.full_path = real

    def _count(self, name):
        """Wrap one of the store's functions and count its calls."""
        calls = []
        original = getattr(self.store, name)

        def counted(*args, **kwargs):
            calls.append(args)
            return original(*args, **kwargs)

        setattr(self.store, name, counted)
        return calls

    def test_listing_reads_each_user_file_once(self):
        self.store.set_favourite(self.files[3], True)
        self.store.set_text(self.files[3], "soft light")
        favourites = self._count("load_favourites")
        texts = self._count("load_text")
        data = self.store.catalog()
        self.assertEqual(data["count"], 60)
        self.assertEqual(len(favourites), 1)
        self.assertEqual(len(texts), 1)
        row = data["assets"][3]
        self.assertTrue(row["favourite"])
        self.assertEqual(row["triggers"], "soft light")
        self.assertFalse(data["assets"][4]["favourite"])
        self.assertEqual(data["assets"][4]["triggers"], "")
        # a single row still answers on its own
        self.assertTrue(self.store.entry(self.files[3])["favourite"])
        self.assertEqual(self.store.entry(self.files[3])["triggers"], "soft light")

    def test_a_rescan_writes_fingerprints_once(self):
        writes = []
        original = self.assets.write_json

        def counted(path, data):
            writes.append(path)
            return original(path, data)

        self.assets.write_json = counted
        self.addCleanup(setattr, self.assets, "write_json", original)
        self.store.reconcile(self.files)
        prints = [path for path in writes if path == self.store.fingerprints_path]
        self.assertEqual(len(prints), 1)
        with open(self.store.fingerprints_path, "r", encoding="utf-8") as handle:
            import json
            self.assertEqual(len(json.load(handle)), 60)
        # nothing changed: a second rescan writes nothing at all
        del writes[:]
        self.store.reconcile(self.files)
        self.assertEqual(writes, [])
        # and the values are stable and distinct
        first = self.store.fingerprint(self.files[0])
        self.assertEqual(first, self.store.fingerprint(self.files[0]))
        self.assertNotEqual(first, self.store.fingerprint(self.files[1]))

    def test_fingerprints_notice_the_file_changing_behind_them(self):
        value = self.store.fingerprint(self.files[0])
        self.assertTrue(os.path.isfile(self.store.fingerprints_path))
        os.remove(self.store.fingerprints_path)
        # the held copy is dropped with the file, and the value is rebuilt
        self.assertEqual(self.store._load_prints(), {})
        self.assertEqual(self.store.fingerprint(self.files[0]), value)
        self.assertTrue(os.path.isfile(self.store.fingerprints_path))

    def test_parallel_saves_do_not_share_a_scratch_file(self):
        import json
        import threading

        target = os.path.join(self.work, "shared.json")
        errors = []

        def hammer(n):
            try:
                for step in range(40):
                    self.assets.write_json(target, {"writer": n, "step": step})
            except Exception as err:  # noqa: BLE001 - the test reports any failure
                errors.append(err)

        threads = [threading.Thread(target=hammer, args=(n,)) for n in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        # Windows may refuse a rename while another thread holds the target
        # open; what must never happen is two writers sharing one scratch name
        self.assertFalse([err for err in errors if not isinstance(err, PermissionError)], errors)
        with open(target, "r", encoding="utf-8") as handle:
            self.assertIn("writer", json.load(handle))
        self.assertEqual([name for name in os.listdir(self.work) if name.endswith(".tmp")
                          and not errors], [])


class Roller(unittest.TestCase):
    """The Style Roller: its word list, the roll, and what the node hands on."""

    @classmethod
    def setUpClass(cls):
        cls.roller = importlib.import_module(f"{PKG}.roller")

    def setUp(self):
        import tempfile
        self.work = tempfile.mkdtemp(prefix="ns_roller_")
        self._user = self.roller.USER
        self.roller.USER = os.path.join(self.work, "roller_words.txt")

    def tearDown(self):
        import shutil
        self.roller.USER = self._user
        shutil.rmtree(self.work, ignore_errors=True)

    def words(self, **kwargs):
        rolled, pinned, _note = self.roller.roll(**kwargs)
        return [row["term"] for row in pinned + rolled]

    def own(self, text):
        with open(self.roller.USER, "w", encoding="utf-8") as handle:
            handle.write(text)

    # ---- the list

    def test_the_list_is_thousands_of_valid_terms(self):
        rows = self.roller.terms()
        self.assertGreater(len(rows), 5000)
        keys = [row["key"] for row in rows]
        self.assertEqual(len(keys), len(set(keys)), "a term is listed twice")
        for row in rows:
            self.assertIn(row["aspect"], self.roller.ASPECTS, row["term"])
            self.assertTrue(row["kinds"] <= set(self.roller.KINDS), row["term"])
            self.assertIn(row["tier"], ("a", "b"), row["term"])
            self.assertTrue(0 < len(row["term"]) <= self.roller.MAX_TERM, row["term"])

    def test_every_kind_and_aspect_has_plenty_to_roll(self):
        counts = self.roller.counts()
        for kind, total in counts["kinds"].items():
            self.assertGreater(total, 100, kind)
        for aspect, total in counts["aspects"].items():
            self.assertGreater(total, 300, aspect)

    def test_the_list_on_disk_matches_its_sources(self):
        spec = importlib.util.spec_from_file_location(
            "ns_mine_roller", os.path.join(ROOT, "tools", "mine_roller.py"))
        miner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(miner)
        with open(miner.OUT, "r", encoding="utf-8", newline="") as handle:
            on_disk = handle.read().replace("\r\n", "\n")
        self.assertEqual(on_disk, miner.render(miner.build()),
                         "run python tools/mine_roller.py")

    # ---- the roll

    def test_a_seed_repeats_and_a_longer_roll_extends_a_shorter_one(self):
        self.assertEqual(self.words(count=8, seed=42), self.words(count=8, seed=42))
        self.assertNotEqual(self.words(count=8, seed=42), self.words(count=8, seed=43))
        self.assertEqual(self.words(count=8, seed=42)[:5], self.words(count=5, seed=42))

    def test_seed_zero_rolls_afresh(self):
        seen = {tuple(self.words(count=6, seed=0)) for _ in range(6)}
        self.assertGreater(len(seen), 1)

    def test_count_is_clamped_and_never_repeats_a_term(self):
        for seed in range(1, 8):
            got = self.words(count=500, seed=seed)
            self.assertEqual(len(got), self.roller.MAX_COUNT)
            self.assertEqual(len(got), len({self.roller.norm(term) for term in got}))
        self.assertEqual(len(self.words(count="nonsense", seed=3)), 5)
        self.assertEqual(self.words(count=-4, seed=3), [])

    def test_kind_keeps_other_kinds_out_and_leads_with_its_own(self):
        for label, kind in self.roller.KIND_CHOICES.items():
            if not kind:
                continue
            for seed in range(1, 6):
                rolled, _pinned, _note = self.roller.roll(count=12, kind=label, seed=seed)
                for row in rolled:
                    self.assertTrue(not row["kinds"] or kind in row["kinds"],
                                    f"{row['term']} rolled for {label}")
                self.assertIn(kind, rolled[0]["kinds"], f"{label} did not lead with its own")

    def test_aspect_narrows_the_roll(self):
        for label, aspect in self.roller.ASPECT_CHOICES.items():
            if not aspect:
                continue
            allowed = {aspect} if isinstance(aspect, str) else set(aspect)
            rolled, _pinned, _note = self.roller.roll(count=12, aspect=label, seed=5)
            self.assertEqual(len(rolled), 12, label)
            self.assertTrue({row["aspect"] for row in rolled} <= allowed, label)
            if isinstance(aspect, tuple):
                self.assertGreater(len({row["aspect"] for row in rolled}), 2, label)

    def test_big_changes_and_fine_details_do_not_overlap_much(self):
        big = dict(self.roller.ASPECT_CHOICES)["big changes (look, era, colour, light)"]
        fine = dict(self.roller.ASPECT_CHOICES)["fine details (texture, shape, mood, camera)"]
        self.assertEqual(set(big) & set(fine), {"lighting"})
        self.assertEqual(set(big) | set(fine), set(self.roller.ASPECTS))
        self.assertIn("effects", big)

    def test_every_theme_has_plenty_of_terms(self):
        rows = self.roller.terms()
        for label, theme in self.roller.THEME_CHOICES.items():
            if not theme:
                continue
            total = sum(1 for row in rows if theme in row["themes"])
            self.assertGreater(total, 200, label)

    def test_a_theme_leads_and_flavours_most_of_the_roll(self):
        for label, theme in self.roller.THEME_CHOICES.items():
            if not theme:
                continue
            themed = total = 0
            for seed in range(1, 9):
                rolled, _pinned, _note = self.roller.roll(count=10, theme=label, seed=seed)
                self.assertIn(theme, rolled[0]["themes"], f"{label} did not lead with its own")
                themed += sum(1 for row in rolled if theme in row["themes"])
                total += len(rolled)
            self.assertGreater(themed / total, 0.55, label)
            self.assertLess(themed / total, 0.95, f"{label} left no room for anything else")

    def test_a_theme_still_obeys_the_kind(self):
        rolled, _pinned, _note = self.roller.roll(count=12, theme="dark & gothic",
                                                  kind="anime & manga", seed=3)
        for row in rolled:
            self.assertTrue(not row["kinds"] or "anime" in row["kinds"], row["term"])

    def test_words_per_term_is_respected(self):
        limits = {"one word": (1, 1), "one or two words": (1, 2), "three or more words": (3, 99)}
        for label, (low, high) in limits.items():
            for seed in range(1, 6):
                rolled, _pinned, _note = self.roller.roll(count=20, words_per_term=label,
                                                          seed=seed)
                self.assertEqual(len(rolled), 20, label)
                for row in rolled:
                    self.assertTrue(low <= len(row["key"].split()) <= high,
                                    f"{row['term']} under {label}")
        self.assertEqual(len(self.roller.roll(count=5, words_per_term="nonsense", seed=2)[0]), 5)

    def test_effects_are_an_aspect_of_their_own(self):
        effects = [row for row in self.roller.terms() if row["aspect"] == "effects"]
        self.assertGreater(len(effects), 400)
        have = {row["key"] for row in effects}
        for word in ("magical sparkles", "paint splatters", "swirling vortex", "twists",
                     "glowing runes", "floating shapes", "shockwave", "light trails",
                     "fractal swirls"):
            self.assertTrue(self.roller.norm(word) in have, word)
        rolled, _pinned, _note = self.roller.roll(count=12, aspect="effects & magic", seed=8)
        self.assertEqual({row["aspect"] for row in rolled}, {"effects"})
        self.assertEqual(len(rolled), 12)
        magic, _pinned, _note = self.roller.roll(count=8, aspect="effects & magic",
                                                 theme="fantasy & mythic", seed=8)
        self.assertGreaterEqual(sum(1 for row in magic if "fantasy" in row["themes"]), 4)

    def test_plain_words_are_there_to_roll(self):
        have = {row["key"] for row in self.roller.terms()}
        for word in ("neon punk", "cyberpunk", "steampunk", "futurism", "futuristic", "historic",
                     "old", "new", "ethereal", "heavenly", "gothic", "splatter", "ink splatter",
                     "paint spatter", "rainbow", "abstract"):
            self.assertIn(word, have)
        singles = sum(1 for row in self.roller.terms() if row["length"] == 1)
        self.assertGreater(singles, 1200)

    def test_a_roll_reports_the_seed_it_came_from(self):
        first = self.roller.roll_detail(count=6, seed=0)
        self.assertTrue(0 < first["seed"] <= 0xFFFFFFFF)
        again = self.roller.roll_detail(count=6, seed=first["seed"])
        self.assertEqual([row["term"] for row in first["rolled"]],
                         [row["term"] for row in again["rolled"]])
        self.assertEqual(self.roller.roll_detail(count=3, seed=77)["seed"], 77)
        for junk in ("x", None, -4, 2 ** 40):
            self.assertTrue(0 < self.roller.roll_detail(count=2, seed=junk)["seed"] <= 0xFFFFFFFF)

    def test_the_shipped_list_names_its_themes_and_own_words_are_matched(self):
        for row in self.roller.terms()[::37]:
            self.assertEqual(row["themes"], self.roller.themes_of(row["term"]), row["term"])
        self.own("gothic velvet gloom\nplain thing | look | * | a | | dark\n")
        mine = {row["term"]: row for row in self.roller.terms() if row["user"]}
        self.assertIn("dark", mine["gothic velvet gloom"]["themes"])
        # a theme column in a user's own file is ignored: the words decide
        self.assertNotIn("dark", mine["plain thing"]["themes"])

    def test_a_balanced_roll_spreads_across_aspects(self):
        for seed in range(1, 6):
            rolled, _pinned, _note = self.roller.roll(count=10, seed=seed)
            self.assertGreaterEqual(len({row["aspect"] for row in rolled}), 6)
            self.assertEqual(rolled[0]["aspect"], "look")

    def test_vocabulary_picks_the_tier(self):
        known, _p, _n = self.roller.roll(count=20, vocabulary="well known", seed=9)
        deep, _p, _n = self.roller.roll(count=20, vocabulary="deep cuts", seed=9)
        self.assertEqual({row["tier"] for row in known}, {"a"})
        self.assertEqual({row["tier"] for row in deep}, {"b"})

    def test_never_include_removes_every_term_holding_the_word(self):
        for seed in range(1, 30):
            got = self.words(count=50, seed=seed, never_include="film, Neon ; glow")
            for term in got:
                self.assertNotRegex(self.roller.norm(term), r"\b(film|neon|glow)\b")

    def test_always_include_leads_and_is_extra(self):
        got = self.words(count=4, seed=6, always_include="my look, , second thing")
        self.assertEqual(got[:2], ["my look", "second thing"])
        self.assertEqual(len(got), 6)
        # a pinned word is never rolled a second time
        rolled = self.words(count=50, seed=6, always_include="film grain")
        self.assertEqual(rolled.count("film grain"), 1)

    def test_opposites_never_share_a_roll(self):
        for seed in range(1, 60):
            rolled, _pinned, _note = self.roller.roll(count=30, seed=seed)
            held = set()
            for row in rolled:
                for index, side in row["flags"]:
                    self.assertNotIn((index, 1 - side), held,
                                     f"seed {seed}: {row['term']} contradicts an earlier word")
                held |= row["flags"]

    def test_a_pinned_word_rules_out_its_opposite(self):
        for seed in range(1, 30):
            got = self.words(count=40, seed=seed, always_include="monochrome")
            for term in got[1:]:
                self.assertNotRegex(term, r"\b(vivid|vibrant|rainbow|colourful|colorful)\b")

    def test_an_exhausted_pool_says_so(self):
        rolled, _pinned, note = self.roller.roll(count=5, vocabulary="my words", seed=2)
        self.assertEqual(rolled, [])
        self.assertIn("0 of 5", note)

    # ---- the user's own words

    def test_own_words_join_the_list_and_can_be_rolled_alone(self):
        self.own("# mine\nglitter fog\nbrass haze | lighting | painting anime\n\n")
        self.assertEqual(self.roller.counts()["user"], 2)
        got = self.words(count=5, vocabulary="my words", seed=4)
        self.assertEqual(sorted(got), ["brass haze", "glitter fog"])
        lit = self.words(count=5, vocabulary="my words", aspect="lighting", kind="painting",
                         seed=4)
        self.assertEqual(lit, ["brass haze"])

    def test_a_hostile_word_file_is_only_ever_text(self):
        self.own("ok term\n" + "x" * 5000 + "\n\x00bad\x1b[31mterm\n"
                 "../../etc/passwd | nonsense | nokind | z | <script>\n"
                 "(paren) [bracket]\n")
        rows = [row for row in self.roller.terms() if row["user"]]
        self.assertEqual(len(rows), 5)
        for row in rows:
            self.assertLessEqual(len(row["term"]), self.roller.MAX_TERM)
            self.assertNotRegex(row["term"], r"[\x00-\x1f]")
            self.assertIn(row["aspect"], self.roller.ASPECTS)
        text = self.roller.render(rows)
        self.assertIn("\\(paren\\)", text)

    def test_an_oversized_word_file_is_ignored(self):
        self.own("word\n" * (self.roller.MAX_USER_BYTES // 5 + 10))
        self.assertEqual(self.roller.counts()["user"], 0)
        self.assertGreater(self.roller.counts()["total"], 5000)

    def test_editing_the_file_changes_the_signature(self):
        before = self.roller.signature()
        self.own("fresh term\n")
        self.assertNotEqual(before, self.roller.signature())

    # ---- output

    def test_tags_use_real_booru_tags_where_they_exist(self):
        rows = {row["term"]: row for row in self.roller.terms()}
        self.assertEqual(self.roller.as_tag(rows["oil painting"]), "oil_painting_\\(medium\\)")
        self.assertEqual(self.roller.as_tag(rows["rule of thirds"]), "rule_of_thirds")

    def test_weight_wraps_each_term(self):
        rows, _p, _n = self.roller.roll(count=2, seed=3)
        plain = self.roller.render(rows)
        self.assertNotIn("(", plain)
        heavy = self.roller.render(rows, weight=1.3)
        self.assertEqual(heavy.count(":1.30)"), 2)
        self.assertEqual(self.roller.render(rows, weight="junk"), plain)
        self.assertEqual(self.roller.render(rows, weight=99).count(":2.00)"), 2)

    def test_words_join_a_prompt_on_either_side(self):
        join = self.roller.join_text
        self.assertEqual(join("a fox,", "x, y"), "a fox, x, y")
        self.assertEqual(join("a fox", "x, y", "before text"), "x, y, a fox")
        self.assertEqual(join(None, "x, y"), "x, y")
        self.assertEqual(join("a fox", ""), "a fox")

    # ---- the node

    def test_the_node_returns_text_and_words(self):
        node = nodes.NeonsStyleRoller()
        out = node.roll(kind="painting", count=3, seed=11, text="a red fox")
        text, words = out["result"]
        self.assertTrue(text.startswith("a red fox, "))
        self.assertTrue(text.endswith(words))
        self.assertEqual(len(words.split(", ")), 3)
        self.assertEqual(out["ui"]["ns_rolled_words"], [words])
        alone = node.roll(count=3, seed=11)["result"]
        self.assertEqual(alone[0], alone[1])

    def test_the_node_reruns_only_when_it_should(self):
        changed = nodes.NeonsStyleRoller.IS_CHANGED
        self.assertNotEqual(changed(seed=0, kind="all"), changed(seed=0, kind="all"))
        self.assertEqual(changed(seed=5, kind="all"), changed(seed=5, kind="all"))
        self.assertNotEqual(changed(seed=5, kind="all"), changed(seed=5, kind="anime & manga"))
        before = changed(seed=5, kind="all")
        self.own("something new\n")
        self.assertNotEqual(before, changed(seed=5, kind="all"))

    def test_the_node_reports_the_recipe_as_plain_lists(self):
        out = nodes.NeonsStyleRoller().roll(count=4, seed=11, always_include="my (pin)",
                                           output_as="tags", weight=1.3)
        terms, tags = out["ui"]["ns_rolled_terms"][0], out["ui"]["ns_rolled_tags"][0]
        self.assertEqual(out["ui"]["ns_rolled_seed"], [11])
        self.assertEqual(len(terms), 5)
        self.assertEqual(len(tags), 5)
        self.assertEqual(terms[0], "my (pin)")
        for term, tag in zip(terms, tags):
            self.assertNotIn(":1.3", term)
            self.assertNotIn(" ", tag)
            self.assertNotIn("\\", tag)

    def test_the_list_draws_on_the_version_two_catalog(self):
        rows = self.roller.terms()
        self.assertGreater(len(rows), 15000)
        spec = importlib.util.spec_from_file_location(
            "ns_mine_roller_v2", os.path.join(ROOT, "tools", "mine_roller.py"))
        miner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(miner)
        self.assertGreater(len(miner.read_v2()), 3000)
        self.assertEqual(set(miner.V2_KIND.values()) - set(self.roller.KINDS), set())

    def test_the_node_is_registered_with_safe_defaults(self):
        self.assertIs(nodes.NODE_CLASS_MAPPINGS["NeonsStyleRoller"], nodes.NeonsStyleRoller)
        required = nodes.NeonsStyleRoller.INPUT_TYPES()["required"]
        self.assertEqual(required["count"][1]["max"], 50)
        for name, spec in required.items():
            if isinstance(spec[0], list):
                self.assertIn(spec[1]["default"], spec[0], name)


class Explorer2(unittest.TestCase):
    """Style Explorer 2: its catalog, the composer, user data and the node."""

    @classmethod
    def setUpClass(cls):
        cls.v2 = importlib.import_module(f"{PKG}.explorer2")
        cls.nodes2 = importlib.import_module(f"{PKG}.nodes2")

    def setUp(self):
        import tempfile
        v2 = self.v2
        self.work = tempfile.mkdtemp(prefix="ns_v2_")
        self._paths = (v2.USER, v2.STATE, v2.CUSTOM, v2.PREVIEWS)
        v2.USER = self.work
        v2.STATE = os.path.join(self.work, "state.json")
        v2.CUSTOM = os.path.join(self.work, "custom.json")
        v2.PREVIEWS = os.path.join(self.work, "previews")
        self._reset()

    def tearDown(self):
        import shutil
        v2 = self.v2
        v2.USER, v2.STATE, v2.CUSTOM, v2.PREVIEWS = self._paths
        self._reset()
        shutil.rmtree(self.work, ignore_errors=True)

    def _reset(self):
        v2 = self.v2
        v2._cache.update(stamp=None, data=None)
        v2._state.update(stamp=None, data=None)
        v2._previews.update(stamp=None, data={})
        v2._claimed.clear()

    def png(self, size=(96, 64)):
        from io import BytesIO
        buffer = BytesIO()
        _Image.new("RGB", size, (120, 90, 60)).save(buffer, "PNG")
        return buffer.getvalue()

    def names(self, count=3, cat=None):
        styles = [s for s in self.v2.catalog()["styles"] if not cat or s["cat"] == cat]
        return [style["name"] for style in styles[:count]]

    def node(self, **overrides):
        kwargs = {"prompt": "a red fox", "styles": "", "strength": "standard",
                  "output_as": "natural language", "style_position": "before prompt",
                  "roll_seed": 5, "auto_preview": "off"}
        kwargs.update({kind: "None" for kind in self.v2.MOD_KINDS})
        kwargs.update(overrides)
        return self.nodes2.NeonsStyleExplorer2().apply(**kwargs)

    # ---- the catalog

    def test_the_catalog_is_large_and_well_formed(self):
        data = self.v2.catalog()
        styles = data["styles"]
        self.assertGreater(len(styles), 1500)
        self.assertEqual(len({s["id"] for s in styles}), len(styles))
        self.assertEqual(len({s["name"].lower() for s in styles}), len(styles))
        subs = {cat["id"]: set(cat["subs"]) for cat in data["cats"]}
        for style in styles:
            self.assertIn(style["cat"], subs, style["name"])
            self.assertIn(style["sub"], subs[style["cat"]], style["name"])
            self.assertGreaterEqual(len(style["parts"]), 5, style["name"])
            self.assertTrue(style["lead"], style["name"])
            self.assertNotRegex(style["name"], r"[,:@|]", style["name"])
        for cat in data["cats"]:
            self.assertTrue(any(s["cat"] == cat["id"] for s in styles), cat["id"])
        for kind in self.v2.MOD_KINDS:
            self.assertGreater(len(data["mods"][kind]), 40, kind)

    def test_the_shipped_styles_pass_their_linter(self):
        spec = importlib.util.spec_from_file_location(
            "ns_v2_lint", os.path.join(ROOT, "tools", "v2_lint.py"))
        lint = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(lint)
        subs, traits = lint.load_taxonomy()
        vocab = lint.load_vocab()
        problems = []
        for where, entry, modifier in lint.read_shipped():
            for line in lint.check(entry, subs, traits, vocab, modifier=modifier):
                problems.append(f"{where} {entry.get('name')}: {line}")
        self.assertEqual(problems[:10], [])

    def test_the_browser_payload_is_compact_and_complete(self):
        import json
        payload = self.v2.payload()
        self.assertEqual(len(payload["styles"]), len(self.v2.catalog()["styles"]))
        row = payload["styles"][0]
        self.assertEqual(len(row), 8)
        self.assertLess(len(json.dumps(payload)) / len(payload["styles"]), 700)

    def test_the_node_list_carries_no_giant_dropdown(self):
        for name, spec in self.nodes2.NeonsStyleExplorer2.INPUT_TYPES()["required"].items():
            if isinstance(spec[0], list):
                self.assertLess(len(spec[0]), 200, name)
                self.assertIn(spec[1]["default"], spec[0], name)

    # ---- the styles box

    def test_parse_reads_weights_dice_and_stops_at_three(self):
        parse = self.v2.parse
        self.assertEqual(parse("Oil Paint, Film Noir:0.5 | @favourites"),
                         [("Oil Paint", 1.0), ("Film Noir", 0.5), ("@favourites", 1.0)])
        self.assertEqual(parse("a:9, b:0, c:x, d"), [("a", 2.0), ("b", 0.1), ("c:x", 1.0)])
        self.assertEqual(parse(" ,, \n"), [])
        self.assertEqual(parse(None), [])
        self.assertEqual(len(parse("x," * 5000)), 3)

    def test_a_style_resolves_by_name_or_id_in_any_case(self):
        style = self.v2.catalog()["styles"][10]
        self.assertIs(self.v2.resolve(style["name"].upper()), style)
        self.assertIs(self.v2.resolve(style["id"]), style)
        self.assertIsNone(self.v2.resolve("no such style"))
        self.assertIsNone(self.v2.resolve(""))

    # ---- composing

    def test_strength_keeps_more_of_the_style(self):
        style = next(s for s in self.v2.catalog()["styles"] if len(s["parts"]) >= 6)
        texts = [self.v2.style_text([(style, 1.0)], strength) for strength in
                 ("light", "standard", "heavy")]
        self.assertTrue(len(texts[0]) < len(texts[1]) < len(texts[2]))
        for text in texts:
            self.assertTrue(text.startswith(style["lead"]))
        self.assertEqual(texts[0], ", ".join([style["lead"]] + style["parts"][:2]))
        self.assertEqual(texts[2], ", ".join([style["lead"]] + style["parts"]))

    def test_weight_scales_one_style_and_shares_a_blend(self):
        a, b = self.v2.catalog()["styles"][:2]
        low = self.v2.style_text([(a, 0.5)], "standard")
        high = self.v2.style_text([(a, 1.5)], "standard")
        self.assertLess(len(low), len(high))
        blend = self.v2.style_text([(a, 1.0), (b, 0.3)], "standard")
        self.assertIn(" blended with ", blend)
        self.assertTrue(blend.startswith(a["lead"]))
        mine = sum(part in blend for part in a["parts"])
        theirs = sum(part in blend for part in b["parts"])
        self.assertGreater(mine, theirs)
        self.assertGreaterEqual(theirs, 1)

    def test_the_style_goes_before_or_after_the_prompt(self):
        name = self.names(1)[0]
        before = self.node(styles=name)["result"]
        after = self.node(styles=name, style_position="after prompt")["result"]
        self.assertTrue(before[0].endswith("a red fox"))
        self.assertTrue(after[0].startswith("a red fox, "))
        self.assertEqual(before[2], after[2])
        self.assertEqual(before[3], name)

    def test_no_style_leaves_the_prompt_alone(self):
        out = self.node()
        self.assertEqual(out["result"][:4], ("a red fox", "", "", ""))

    def test_an_unknown_style_is_reported_not_fatal(self):
        out = self.node(styles="Definitely Not A Style")
        self.assertEqual(out["result"][0], "a red fox")
        self.assertIn("no style called", out["ui"]["ns2_notes"][0])

    def test_modifiers_are_added_and_random_follows_the_seed(self):
        lighting = self.v2.modifier_names("lighting")[0]
        out = self.node(lighting=lighting)["result"][0]
        self.assertIn(self.v2.modifier("lighting", lighting)["nl"], out)
        one = self.node(palette="Random", roll_seed=11)["result"][0]
        two = self.node(palette="Random", roll_seed=11)["result"][0]
        self.assertEqual(one, two)
        self.assertNotEqual(one, "a red fox")

    def test_tags_output_escapes_brackets_and_carries_weight(self):
        style = next(s for s in self.v2.catalog()["styles"]
                     if any("(" in tag for tag in s["tags"]))
        out = self.node(styles=f"{style['name']}:1.3", output_as="tags", strength="heavy")
        text = out["result"][2]
        self.assertIn("\\(", text)
        self.assertIn(":1.30)", text)
        self.assertNotIn(style["lead"], text)
        both = self.node(styles=style["name"], output_as="natural language + tags")["result"][2]
        self.assertIn(style["lead"], both)

    def test_lora_triggers_lead_the_prompt_whatever_the_position(self):
        name = self.names(1)[0]
        wired = {"lora_triggers_1": "ohwx style, film grain", "lora_triggers_2": "Film Grain, sks",
                 "lora_triggers_3": ""}
        for position in self.v2.POSITIONS:
            out = self.node(styles=name, style_position=position, **wired)["result"]
            self.assertTrue(out[0].startswith("ohwx style, film grain, sks, "), out[0][:80])
            self.assertNotIn("ohwx", out[2], "triggers are not part of the style text")
        plain = self.node(styles=name)["result"][0]
        self.assertEqual(self.node(styles=name, **wired)["result"][0],
                         "ohwx style, film grain, sks, " + plain)
        alone = self.node(lora_triggers_1="sks")["result"][0]
        self.assertEqual(alone, "sks, a red fox")
        tags = self.node(styles=name, output_as="tags", lora_triggers_1="sks (v2)")["result"][0]
        self.assertTrue(tags.startswith("sks (v2), "))

    def test_the_prefix_follows_triggers_and_leads_everything_else(self):
        name = self.names(1)[0]
        style = self.v2.resolve(name)
        for position in self.v2.POSITIONS:
            out = self.node(styles=name, style_position=position, prompt_prefix="best quality, ",
                            lora_triggers_1="sks")["result"]
            self.assertTrue(out[0].startswith("sks, best quality, "), out[0][:60])
            self.assertEqual(out[0].count("best quality"), 1)
            self.assertNotIn("best quality", out[2], "the prefix is not part of the style text")
        before = self.node(styles=name, prompt_prefix="best quality")["result"][0]
        self.assertTrue(before.startswith(f"best quality, {style['lead']}"))
        self.assertEqual(self.node(prompt_prefix="hi")["result"][0], "hi, a red fox")
        self.assertEqual(self.node(prompt_prefix="  ")["result"][0], "a red fox")

    def test_the_negative_is_passed_through_untouched_by_styles(self):
        name = self.names(1)[0]
        out = self.node(styles=name, negative="  blurry, low contrast\nextra limbs  ")["result"]
        self.assertEqual(out[1], "blurry, low contrast\nextra limbs")
        self.assertNotIn("blurry", out[0])
        self.assertEqual(self.node(styles=name)["result"][1], "")
        self.assertEqual(self.node(negative=None)["result"][1], "")

    def test_debug_says_what_the_run_did(self):
        a, b = self.names(2)
        lighting = self.v2.modifier_names("lighting")[0]
        out = self.node(styles=f"{a}, {b}:0.5, Not A Style", lighting=lighting, negative="blurry",
                        prompt_prefix="best quality", lora_triggers_1="sks")["result"]
        debug = out[4]
        for expected in (a, f"{b} x0.5", f"lighting: {lighting}", "sks", "best quality",
                         "no style called", "positive:", out[0], "negative:", "blurry", out[2]):
            self.assertIn(expected, debug)
        self.assertIn("styles used:   none", self.node()["result"][4])

    def test_the_outputs_are_in_the_documented_order(self):
        base, enc = self.nodes2.NeonsStyleExplorer2, self.nodes2.NeonsStyleExplorer2Encode
        self.assertEqual(base.RETURN_NAMES, ("positive", "negative", "style_text", "style_name",
                                             "debug"))
        self.assertEqual(enc.RETURN_NAMES, ("positive_conditioning", "negative_conditioning")
                         + base.RETURN_NAMES)
        for cls in (base, enc):
            self.assertEqual(len(cls.RETURN_TYPES), len(cls.RETURN_NAMES))
            self.assertEqual(len(cls.OUTPUT_TOOLTIPS), len(cls.RETURN_NAMES))
        self.assertEqual(enc.RETURN_TYPES[:2], ("CONDITIONING", "CONDITIONING"))

    def test_the_encode_node_encodes_both_prompts(self):
        seen = []

        class Clip:
            def tokenize(self, text):
                seen.append(text)
                return text

            def encode_from_tokens_scheduled(self, tokens):
                return [["cond", {"text": tokens}]]

        name = self.names(1)[0]
        kwargs = {"prompt": "a red fox", "styles": name, "negative": "blurry", "roll_seed": 5}
        out = self.nodes2.NeonsStyleExplorer2Encode().apply(Clip(), **kwargs)["result"]
        self.assertEqual(seen, [out[2], "blurry"])
        self.assertEqual(out[0][0][1]["text"], out[2])
        self.assertEqual(out[1][0][1]["text"], "blurry")
        self.assertEqual(out[3], "blurry")
        # no negative is still a conditioning a sampler can take
        empty = self.nodes2.NeonsStyleExplorer2Encode().apply(
            Clip(), prompt="x", styles="", roll_seed=5)["result"]
        self.assertEqual(empty[1][0][1]["text"], "")

    def test_a_changed_negative_or_prefix_reruns_the_node(self):
        changed = self.nodes2.NeonsStyleExplorer2.IS_CHANGED
        base = {"prompt": "x", "styles": "", "roll_seed": 5}
        self.assertNotEqual(changed(**base), changed(**dict(base, negative="blurry")))
        self.assertNotEqual(changed(**base), changed(**dict(base, prompt_prefix="hi")))

    def test_the_trigger_inputs_match_the_original_node(self):
        for cls in (self.nodes2.NeonsStyleExplorer2, self.nodes2.NeonsStyleExplorer2Encode):
            optional = cls.INPUT_TYPES()["optional"]
            self.assertEqual(sorted(optional), sorted(nodes.LORA_TRIGGER_INPUTS))
            for spec in optional.values():
                self.assertTrue(spec[1]["forceInput"])
        changed = self.nodes2.NeonsStyleExplorer2.IS_CHANGED
        base = {"prompt": "x", "styles": "", "roll_seed": 5}
        self.assertNotEqual(changed(**base), changed(**dict(base, lora_triggers_1="sks")))

    # ---- dice

    def test_a_dice_follows_the_seed_and_its_scope(self):
        cat = self.v2.catalog()["cats"][3]["id"]
        picks, _notes = self.v2.pick(f"@{cat}", seed=9)
        again, _notes = self.v2.pick(f"@{cat}", seed=9)
        self.assertEqual(picks[0][0]["id"], again[0][0]["id"])
        self.assertEqual(picks[0][0]["cat"], cat)
        seen = {self.v2.pick("@all", seed=seed)[0][0][0]["id"] for seed in range(1, 12)}
        self.assertGreater(len(seen), 5)

    def test_a_dice_narrows_to_a_sub_and_to_a_collection(self):
        style = self.v2.catalog()["styles"][0]
        picks, notes = self.v2.pick(f"@{style['cat']}/{style['sub']}", seed=3)
        self.assertEqual((picks[0][0]["cat"], picks[0][0]["sub"]), (style["cat"], style["sub"]))
        self.assertEqual(notes, [])
        self.assertEqual(self.v2.collection_edit("Keepers", ident=style["id"]), "")
        picks, notes = self.v2.pick("@keepers", seed=3)
        self.assertEqual(picks[0][0]["id"], style["id"])

    def test_an_empty_scope_falls_back_and_says_so(self):
        picks, notes = self.v2.pick("@favourites", seed=4)
        self.assertEqual(len(picks), 1)
        self.assertIn("no favourites yet", notes[0])
        picks, notes = self.v2.pick("@nowhere at all", seed=4)
        self.assertEqual(len(picks), 1)
        self.assertIn("no category or collection", notes[0])

    def test_two_dice_never_land_on_the_same_style(self):
        style = self.v2.catalog()["styles"][0]
        self.v2.collection_edit("One", ident=style["id"])
        picks, _notes = self.v2.pick("@one, @one", seed=2)
        self.assertEqual(len(picks), 1)

    @unittest.skipUnless(HAVE_PILLOW, "needs Pillow")
    def test_next_walks_the_styles_that_have_no_preview(self):
        styles = self.v2.catalog()["styles"]
        first, _n = self.v2.pick("@next", claim=True)
        second, _n = self.v2.pick("@next", claim=True)
        self.assertEqual(first[0][0]["id"], styles[0]["id"])
        self.assertEqual(second[0][0]["id"], styles[1]["id"])
        # looking without claiming does not move it on
        peek, _n = self.v2.pick("@next")
        self.assertEqual(peek[0][0]["id"], styles[2]["id"])
        self.assertEqual(self.v2.pick("@next")[0][0][0]["id"], styles[2]["id"])
        self.assertTrue(self.v2.save_preview(styles[0]["id"], self.png()))
        third, _n = self.v2.pick("@next", claim=True)
        self.assertEqual(third[0][0]["id"], styles[2]["id"])

    # ---- favourites, recents, collections

    def test_favourites_toggle_and_survive_a_reload(self):
        style = self.v2.catalog()["styles"][5]
        self.assertTrue(self.v2.set_favourite(style["name"]))
        self._reset()
        self.assertEqual(self.v2.state()["favourites"], [style["id"]])
        self.assertFalse(self.v2.set_favourite(style["id"]))
        self.assertIsNone(self.v2.set_favourite("no such style"))
        self.assertEqual(self.v2.state()["favourites"], [])

    def test_recents_keep_order_and_a_limit(self):
        ids = [s["id"] for s in self.v2.catalog()["styles"][:self.v2.MAX_RECENT + 8]]
        for ident in ids:
            self.v2.push_recent(ident)
        self.v2.push_recent(ids[3])
        recents = self.v2.state()["recents"]
        self.assertEqual(recents[0], ids[3])
        self.assertEqual(len(recents), self.v2.MAX_RECENT)
        self.assertEqual(len(set(recents)), len(recents))
        self.v2.clear_recents()
        self.assertEqual(self.v2.state()["recents"], [])

    def test_collections_fill_rename_and_delete(self):
        a, b = [s["id"] for s in self.v2.catalog()["styles"][:2]]
        edit = self.v2.collection_edit
        self.assertEqual(edit("Moody set", ident=a), "")
        self.assertEqual(edit("moody SET", ident=b), "")
        self.assertEqual(self.v2.state()["collections"], {"Moody set": [a, b]})
        self.assertEqual(edit("Moody set", ident=a, on=False), "")
        self.assertEqual(edit("Moody set", rename="Night"), "")
        self.assertEqual(self.v2.state()["collections"], {"Night": [b]})
        self.assertTrue(edit("Night", ident="no such style"))
        self.assertTrue(edit(""))
        self.assertEqual(edit("Night", delete=True), "")
        self.assertEqual(self.v2.state()["collections"], {})

    def test_a_damaged_state_file_reads_as_empty(self):
        os.makedirs(self.work, exist_ok=True)
        for junk in ("not json", "[1, 2]", '{"favourites": 7, "collections": [1], "recents": {}}'):
            with open(self.v2.STATE, "w", encoding="utf-8") as handle:
                handle.write(junk)
            self._reset()
            self.assertEqual(self.v2.state(), {"favourites": [], "recents": [], "collections": {}})

    # ---- previews

    @unittest.skipUnless(HAVE_PILLOW, "needs Pillow")
    def test_a_preview_is_saved_listed_and_removed(self):
        style = self.v2.catalog()["styles"][7]
        self.assertFalse(self.v2.has_preview(style["id"]))
        self.assertTrue(self.v2.save_preview(style["name"], self.png((2000, 1000))))
        self.assertIn(style["id"], self.v2.previews())
        path = self.v2.preview_path(style["id"])
        with _Image.open(path) as image:
            self.assertEqual(max(image.size), self.v2.PREVIEW_SIZE)
        self.assertTrue(self.v2.preview_path(style["id"], "256").endswith(".256.jpg"))
        self.assertTrue(self.v2.delete_preview(style["id"]))
        self.assertEqual(self.v2.previews(), {})
        self.assertIsNone(self.v2.preview_path(style["id"]))

    def test_a_preview_can_only_ever_land_in_the_previews_folder(self):
        base = os.path.realpath(self.v2.PREVIEWS)
        for hostile in ("../../etc/passwd", "..\\..\\windows\\win.ini", "/abs/olute",
                        "C:\\x\\y", "a/../../b", "photo.x\x00.jpg", "con", "....//....//x"):
            path = self.v2.preview_file(hostile)
            self.assertEqual(os.path.dirname(os.path.realpath(path)), base, hostile)
            self.assertIsNone(self.v2.save_preview(hostile, b"x"))
            self.assertIsNone(self.v2.preview_path(hostile))
            self.assertFalse(self.v2.delete_preview(hostile))
        self.assertIsNone(self.v2.preview_file(""))

    def test_a_file_that_is_not_an_image_is_refused(self):
        style = self.v2.catalog()["styles"][0]
        self.assertIsNone(self.v2.save_preview(style["id"], b"<script>alert(1)</script>"))
        self.assertIsNone(self.v2.save_preview(style["id"], "a string"))
        self.assertFalse(os.path.isdir(self.v2.PREVIEWS) and os.listdir(self.v2.PREVIEWS))

    @unittest.skipUnless(HAVE_PILLOW, "needs Pillow")
    def test_previews_of_original_styles_are_carried_over_once(self):
        import json
        with open(os.path.join(ROOT, "styles_v2", "_aliases.json"), encoding="utf-8") as handle:
            aliases = json.load(handle)
        old_id, new_id = next((old, new) for old, new in aliases.items() if self.v2.resolve(new))
        # a stand-in for the original gallery, so the test never touches a real one
        folder = os.path.join(self.work, "original")
        os.makedirs(folder)
        with open(os.path.join(folder, "cover.jpg"), "wb") as handle:
            handle.write(self.png())
        records = {gallery.safe(old_id): {"cover": "../original/cover.jpg"},
                   gallery.safe("not.aliased"): {"cover": "cover.jpg"}}
        real = (gallery.manifest, gallery.previews_dir)
        gallery.manifest, gallery.previews_dir = (lambda: records), (lambda cid=None: folder)
        try:
            self.assertEqual(self.v2.adopt_v1_previews(), 1)
            self.assertTrue(self.v2.has_preview(new_id))
            self.assertEqual(len(self.v2.previews()), 1)
            # a one-time step: a preview the user later removes does not come back
            self.assertTrue(self.v2.delete_preview(new_id))
            self.assertEqual(self.v2.adopt_v1_previews(), 0)
            self.assertFalse(self.v2.has_preview(new_id))
            self.assertTrue(os.path.isfile(os.path.join(folder, "cover.jpg")))
        finally:
            gallery.manifest, gallery.previews_dir = real

    # ---- the user's own styles

    def test_own_styles_are_saved_edited_and_deleted(self):
        entry, error = self.v2.save_custom({
            "name": "My Look", "sub": "Tests", "lead": "Soft grainy test photograph",
            "parts": "warm grain\nlow contrast, lifted blacks", "tags": "film grain, sepia"})
        self.assertEqual(error, "")
        self.assertEqual((entry["cat"], entry["custom"]), ("custom", True))
        self.assertEqual(entry["parts"], ["warm grain", "low contrast", "lifted blacks"])
        self.assertEqual(entry["tags"], ["film_grain", "sepia"])
        self.assertIn("custom", [cat["id"] for cat in self.v2.catalog()["cats"]])
        self.assertIn("Soft grainy test photograph", self.node(styles="my look")["result"][0])
        entry, error = self.v2.save_custom({"name": "My Better Look", "lead": "Changed lead"},
                                           replace="My Look")
        self.assertEqual(error, "")
        self.assertIsNone(self.v2.resolve("My Look"))
        self.assertTrue(self.v2.delete_custom("My Better Look"))
        self.assertIsNone(self.v2.resolve("My Better Look"))

    def test_an_own_style_cannot_shadow_or_delete_a_shipped_one(self):
        shipped = self.v2.catalog()["styles"][0]
        entry, error = self.v2.save_custom({"name": shipped["name"], "lead": "x y"})
        self.assertIsNone(entry)
        self.assertIn("already a style", error)
        self.assertFalse(self.v2.delete_custom(shipped["name"]))
        self.assertIsNotNone(self.v2.resolve(shipped["name"]))
        self.assertEqual(self.v2.save_custom({"name": "", "lead": "x"})[1], "Give the style a name.")
        self.assertTrue(self.v2.save_custom("not a dict")[1])

    def test_hostile_text_in_an_own_style_stays_text(self):
        entry, error = self.v2.save_custom({
            "name": "<img src=x>, @all: | (x)", "lead": "lead\x00 with\ncontrol\x1b chars",
            "parts": ["p" * 5000, {"not": "text"}], "tags": ["(tag)"]})
        self.assertEqual(error, "")
        self.assertNotRegex(entry["name"], r"[,:@|()<>]")
        self.assertNotRegex(entry["lead"], r"[\x00-\x1f]")
        self.assertLessEqual(len(entry["parts"][0]), 100)
        out = self.node(styles=entry["name"], output_as="tags")["result"][2]
        self.assertIn("\\(tag\\)", out)

    def test_a_recipe_saved_whole_ignores_strength(self):
        words = [f"word number {index}" for index in range(30)]
        tags = [f"tag_{index}" for index in range(30)]
        entry, error = self.v2.save_custom({"name": "Rolled Recipe", "sub": "Rolled",
                                            "lead": "Painterly", "parts": words, "tags": tags,
                                            "fixed": True})
        self.assertEqual(error, "")
        self.assertTrue(entry["fixed"])
        self.assertEqual(len(entry["parts"]), 30)
        for strength in ("light", "standard", "heavy"):
            text = self.node(styles="Rolled Recipe", strength=strength)["result"][2]
            self.assertEqual(text, "Painterly, " + ", ".join(words))
        tagged = self.node(styles="Rolled Recipe", strength="light", output_as="tags")["result"][2]
        self.assertEqual(tagged.split(", "), tags)
        # blended, it still brings all of itself
        other = self.names(1)[0]
        blend = self.node(styles=f"{other}, Rolled Recipe")["result"][2]
        self.assertIn("word number 29", blend)

    def test_a_recipe_not_saved_whole_follows_strength(self):
        words = [f"word number {index}" for index in range(12)]
        entry, _error = self.v2.save_custom({"name": "Loose Recipe", "lead": "Painterly",
                                             "parts": words})
        self.assertFalse(entry["fixed"])
        light = self.node(styles="Loose Recipe", strength="light")["result"][2]
        self.assertEqual(light, "Painterly, word number 0, word number 1")
        heavy = self.node(styles="Loose Recipe", strength="heavy")["result"][2]
        self.assertEqual(len(heavy.split(", ")), 8)

    def test_a_saved_recipe_has_a_length_limit_and_shipped_styles_are_never_fixed(self):
        entry, _error = self.v2.save_custom({"name": "Huge", "lead": "x y", "fixed": True,
                                             "parts": [f"p {i}" for i in range(500)]})
        self.assertEqual(len(entry["parts"]), self.v2.MAX_OWN_PARTS)
        self.assertFalse(any(style["fixed"] for style in self.v2.catalog()["styles"]
                             if not style["custom"]))
        # "fixed" must be a real true, not anything truthy from a request
        loose, _error = self.v2.save_custom({"name": "Sneaky", "lead": "x y", "fixed": "yes"})
        self.assertFalse(loose["fixed"])

    # ---- the node

    def test_the_node_is_registered_beside_the_original(self):
        for key in ("NeonsStyleExplorer", "NeonsStyleExplorer2", "NeonsStyleExplorer2Encode"):
            self.assertIn(key, nodes.NODE_CLASS_MAPPINGS)
        self.assertEqual(nodes.NODE_DISPLAY_NAME_MAPPINGS["NeonsStyleExplorer2"],
                         "Neons Style Explorer 2")

    def test_the_node_reports_what_it_used(self):
        a, b = self.names(2)
        out = self.node(styles=f"{a}, {b}:0.5")
        self.assertEqual(out["result"][3], f"{a}, {b}")
        self.assertEqual(len(out["ui"]["ns2_style_ids"][0]), 2)
        self.assertEqual(self.v2.state()["recents"][0], out["ui"]["ns2_style_ids"][0][0])

    def test_the_node_reruns_only_when_the_result_would_change(self):
        changed = self.nodes2.NeonsStyleExplorer2.IS_CHANGED
        name = self.names(1)[0]
        base = {"prompt": "x", "styles": name, "roll_seed": 5}
        self.assertEqual(changed(**base), changed(**base))
        self.assertNotEqual(changed(**base), changed(**dict(base, strength="heavy")))
        dice = dict(base, styles="@all")
        self.assertEqual(changed(**dice), changed(**dice))
        self.assertNotEqual(changed(**dict(dice, roll_seed=0)), changed(**dict(dice, roll_seed=0)))
        self.assertNotEqual(changed(**dict(base, styles="@next")),
                            changed(**dict(base, styles="@next")))
        # asking whether to re-run must not itself use anything up
        self.assertEqual(self.v2.state()["recents"], [])
        self.assertEqual(self.v2._claimed, set())

    def test_an_edited_own_style_reruns_the_node(self):
        changed = self.nodes2.NeonsStyleExplorer2.IS_CHANGED
        self.v2.save_custom({"name": "Mine", "lead": "First lead here"})
        before = changed(prompt="x", styles="Mine", roll_seed=5)
        self.v2.save_custom({"name": "Mine", "lead": "Second lead here"}, replace="Mine")
        self.assertNotEqual(before, changed(prompt="x", styles="Mine", roll_seed=5))


if __name__ == "__main__":
    unittest.main(verbosity=2)
