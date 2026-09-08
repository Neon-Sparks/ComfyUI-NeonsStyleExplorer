# Releasing

Everything here is repeatable. Two placeholders are filled once, at first
release: `Neon-Sparks` (your GitHub account) and `PublisherId` (your Comfy
Registry publisher, which is permanent — it appears in the node's registry URL).

## Once, before the first release

1. **GitHub repo.** Create an empty public repo named
   `ComfyUI-NeonsStyleExplorer` — no README, licence or .gitignore, this repo
   already has them. Then:

   ```bash
   git remote add origin https://github.com/Neon-Sparks/ComfyUI-NeonsStyleExplorer.git
   git branch -M main
   git push -u origin main
   ```

2. **Placeholders are already filled** — repo `Neon-Sparks/ComfyUI-NeonsStyleExplorer`,
   publisher `Neon-Sparks`. If the registry will not accept that publisher id
   (it is claimed first-come and is permanent), change
   `[tool.comfy] PublisherId` to whatever you claimed and commit.

3. **Comfy Registry publisher.** Create the account at
   <https://registry.comfy.org>, then create a publishing API key for it.

4. **Repository secret.** GitHub → Settings → Secrets and variables → Actions →
   New repository secret, named `REGISTRY_ACCESS_TOKEN`, value = that API key.
   `.github/workflows/publish_action.yml` publishes on every push that changes
   `pyproject.toml`'s version, and can also be run by hand from the Actions tab.

## Every release

1. `bash tools/build_all.sh` — rebuilds the catalog from `tools/written/*.json`,
   lints, rebuilds the index and docs, checks the web layer, runs the tests.
   Must end `OK` with `errors: 0`.
2. Bump `version` in `pyproject.toml` (semantic: breaking / feature / fix).
3. Write the `CHANGELOG.md` entry: what changed, and for a fix, what the cause
   was.
4. Commit, push. The publish action fires on the version change.
5. Tag the release so the git history matches the registry:

   ```bash
   git tag -a v1.6.1 -m "1.6.1"
   git push origin v1.6.1
   ```

6. Draft a GitHub release from the tag, pasting that changelog entry.

## What ships

`.comfyignore` keeps `tests/`, `tools/`, `examples/`, `.github/`, `CHANGELOG.md`
and `STYLES.md` out of the published archive — none of it is needed to run the
node. `.gitignore` keeps `user/` (catalogs, favourites, recents, custom styles,
overrides) and generated preview images out of git entirely: **the gallery ships
empty and fills up on the user's machine.**

## Version policy

* **patch** — a fix, no behaviour change for anyone who was not hitting the bug
* **minor** — new styles, new widgets, new UI, anything additive
* **major** — a change that alters existing output text or breaks saved
  workflows (a renamed widget, a removed node, a changed default)

Renaming or removing a widget breaks every saved workflow that uses it, so it
belongs in a major release with a note in the changelog.
