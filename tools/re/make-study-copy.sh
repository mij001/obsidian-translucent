#!/usr/bin/env bash
# Build a local, beautified, split copy of the installed Obsidian for reading.
# Output: .local/study/  (git-ignored; proprietary code, do not publish)
# Needs: python3, and `pip install jsbeautifier` (in a venv is fine) for the beautify step.
set -euo pipefail
root="$(cd "$(dirname "$0")/../.." && pwd)"
src="${OBSIDIAN_TRANSLUCENT_SOURCE:-/usr/lib/obsidian}"
out="$root/.local/study"
py="${PYTHON:-python3}"

mkdir -p "$out"
PYTHONPATH="$root/src" "$py" -c "
from obsidian_translucent import asar
print(asar.extract('$src/obsidian.asar', '$out/raw'), 'files from obsidian.asar')
print(asar.extract('$src/app.asar', '$out/launcher'), 'files from app.asar')"

"$py" -c 'import jsbeautifier' 2>/dev/null || { echo "install jsbeautifier first: $py -m pip install jsbeautifier" >&2; exit 1; }
"$py" "$root/tools/re/pretty.py" "$out/raw" "$out/pretty" main.js app.js worker.js help.js starter.js i18n.js enhance.js sim.js
"$py" "$root/tools/re/split_bundle.py" "$out/pretty/app.js" "$out/app_split"
"$py" "$root/tools/re/chunk_tail.py" "$out/app_split/bootstrap_tail.js" "$out/app_chunks" 3500 >/dev/null
echo "study copy ready in $out"
