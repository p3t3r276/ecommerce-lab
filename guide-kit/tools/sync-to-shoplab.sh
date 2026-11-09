#!/usr/bin/env bash
# Copy the shared files of a step (contracts, public interfaces, seed, realm, shared tests)
# from reference/ into the user's repo. Implementation files are never copied.
#
#   bash tools/sync-to-shoplab.sh S3            copy; files that differ are saved as <file>.reference
#   bash tools/sync-to-shoplab.sh S3 --force    overwrite files that differ
#   bash tools/sync-to-shoplab.sh S3 --dry-run  only show what would happen
set -euo pipefail
cd "$(dirname "$0")/.."
shopt -s globstar nullglob dotglob

step="${1:-}"; mode="${2:-}"
[[ $step =~ ^[Ss][0-8]$ ]] || { echo "Usage: bash tools/sync-to-shoplab.sh S0..S8 [--force|--dry-run]" >&2; exit 1; }
step=$(echo "$step" | tr 'S' 's')

[ -f kit.env ] || { echo "Missing kit.env (copy kit.env.example and set SHOPLAB_PATH)" >&2; exit 1; }
# shellcheck disable=SC1091
source kit.env
target="${SHOPLAB_PATH:?SHOPLAB_PATH not set in kit.env}"
[ -d "$target/.git" ] || { echo "$target is not a git repo" >&2; exit 1; }

list="shared/$step.txt"
[ -f "$list" ] || { echo "Missing $list (run /decide ${step^^} first)" >&2; exit 1; }
[ -d reference ] || { echo "reference/ does not exist yet" >&2; exit 1; }

new=0; same=0; updated=0; conflict=0; missing=0
while IFS= read -r pattern || [ -n "$pattern" ]; do
  pattern="${pattern%%#*}"; pattern="$(echo "$pattern" | xargs)"
  [ -n "$pattern" ] || continue
  matches=()
  for f in reference/$pattern; do [ -f "$f" ] && matches+=("$f"); done
  if [ ${#matches[@]} -eq 0 ]; then echo "  no match   $pattern"; missing=$((missing+1)); continue; fi
  for src in "${matches[@]}"; do
    rel="${src#reference/}"; dst="$target/$rel"
    if [ ! -e "$dst" ]; then
      echo "  new        $rel"; new=$((new+1))
      [ "$mode" = "--dry-run" ] || { mkdir -p "$(dirname "$dst")"; cp "$src" "$dst"; }
    elif cmp -s "$src" "$dst"; then
      same=$((same+1))
    elif [ "$mode" = "--force" ]; then
      echo "  overwrite  $rel"; updated=$((updated+1)); cp "$src" "$dst"
    else
      echo "  differs    $rel  -> saved as $rel.reference"; conflict=$((conflict+1))
      [ "$mode" = "--dry-run" ] || cp "$src" "$dst.reference"
    fi
  done
done < "$list"

echo "new=$new identical=$same overwritten=$updated differs=$conflict patterns-without-match=$missing"
[ $conflict -eq 0 ] || echo "Compare each <file>.reference with your file, merge by hand, then delete the .reference copies."
