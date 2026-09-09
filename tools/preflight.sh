#!/usr/bin/env bash
# Publish preflight: is this tree safe and complete to push?
#
#   bash tools/preflight.sh
#
# Checks, in order: nothing private is tracked, no build junk is tracked, the
# catalog rebuilds identically from its source packs, the linter and tests pass,
# the web layer has no undefined calls, and the release metadata is filled in.
set -uo pipefail
cd "$(dirname "$0")/.."

fail=0
note() { printf '  %-8s %s\n' "$1" "$2"; }
ok()   { note "ok" "$1"; }
bad()  { note "PROBLEM" "$1"; fail=$((fail + 1)); }

echo "== private data =="
private=$(git ls-files | grep -E '^user/|^previews/.*\.(jpg|jpeg|png|webp)$|\.tmp$' || true)
if [ -n "$private" ]; then bad "these are tracked but should not be:"; echo "$private" | sed 's/^/           /'
else ok "no user data, previews or scratch files tracked"; fi

echo "== build junk =="
junk=$(git ls-files | grep -E '__pycache__|\.pyc$|\.DS_Store|node_modules' || true)
if [ -n "$junk" ]; then bad "build junk tracked:"; echo "$junk" | sed 's/^/           /'
else ok "no caches or editor droppings tracked"; fi

echo "== working tree =="
if [ -n "$(git status --porcelain)" ]; then
    bad "uncommitted changes:"; git status --porcelain | sed 's/^/           /'
else ok "everything committed"; fi

echo "== catalog rebuild =="
python3 tools/import_source.py >/dev/null 2>&1
if [ -n "$(git status --porcelain styles/ data/ web/style_index.js STYLES.md 2>/dev/null)" ]; then
    bad "the built catalog differs from its source packs — commit the rebuild"
else ok "catalog matches tools/written/"; fi

echo "== lint, web check, tests =="
lint=$(python3 tools/lint.py 2>&1 | tail -3)
echo "$lint" | grep -q "errors:       0" && ok "lint clean" || { bad "lint errors"; echo "$lint" | sed 's/^/           /'; }
web=$(node tools/check_web.mjs 2>&1 | tail -1)
echo "$web" | grep -q "clean" && ok "$web" || { bad "$web"; }
tests=$(python3 tests/test_compose.py 2>&1 | tail -1)
[ "$tests" = "OK" ] && ok "tests pass" || bad "tests: $tests"

echo "== release metadata =="
grep -q 'PublisherId = ""' pyproject.toml && bad "PublisherId is empty" || ok "publisher set"
grep -q 'github.com/local' pyproject.toml && bad "placeholder repo URL" || ok "repo URL set"
grep -qi "krea" LICENSE && bad "LICENSE still names the old project" || ok "licence names this project"
version=$(grep -m1 '^version' pyproject.toml | cut -d'"' -f2)
grep -q "## $version" CHANGELOG.md && ok "changelog has an entry for $version" \
    || bad "no changelog entry for version $version"

echo
[ "$fail" -eq 0 ] && echo "preflight: ready to push" || echo "preflight: $fail problem(s)"
exit "$fail"
