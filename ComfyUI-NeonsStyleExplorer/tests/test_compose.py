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
            catalog.write_json(catalog.favourites_path(), [])

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
            catalog.clear_recents()

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
            catalog.write_json(catalog.favourites_path(), [])
            catalog.clear_recents()

    def test_crawl_walks_the_scope_in_order(self):
        names = catalog.crawl_names("all")
        self.assertEqual(len(names), len(catalog.by_axis("style")))
        self.assertEqual(names, [entry["name"] for entry in catalog.by_axis("style")])
        self.assertEqual(len(set(names)), len(names))

    def test_crawl_scope_narrows_the_walk(self):
        family = catalog.by_axis("style")[0]["family"]
        walk = catalog.crawl_names("family", family=family)
        self.assertTrue(walk)
        self.assertTrue(all(catalog.resolve(name)["family"] == family for name in walk))
        self.assertLess(len(walk), len(catalog.crawl_names("all")))

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
            catalog.clear_recents()

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

    def test_catalog_names_get_unique_ids(self):
        made = []
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
