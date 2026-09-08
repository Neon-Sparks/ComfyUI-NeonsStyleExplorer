#!/usr/bin/env bash
# Rebuild everything from tools/written/*.json, then lint and test.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 tools/import_source.py
python3 tools/lint.py
python3 tools/build_index.py
python3 tools/build_docs.py
python3 tools/build_examples.py
node tools/check_web.mjs
python3 tests/test_compose.py
