#!/bin/bash
# Stop: block "done" while the branch would fail CI's lint / version checks.
# Tests are NOT run here: they need a database and wipe whatever DATABASE_URL points at.
. "$(dirname "$0")/run-tool.sh"
input=$(cat)
[ "$(jq -r '.stop_hook_active' <<<"$input")" = "true" ] && exit 0
cd "$CLAUDE_PROJECT_DIR" || exit 0

base=$(git merge-base HEAD origin/main 2>/dev/null || git merge-base HEAD main 2>/dev/null) || exit 0
changed=$( (git diff --name-only "$base"; git ls-files --others --exclude-standard) | sort -u)
[ -z "$changed" ] && exit 0

problems=""
add() { problems="$problems"$'\n\n'"$1"; }

ver() { sed -n 's/^version = "\(.*\)"/\1/p' | head -1; }
pkg_version=$(ver <pyproject.toml)
doc_version=$(sed -n 's/^release = "\(.*\)"/\1/p' doc/conf.py)
[ "$pkg_version" != "$doc_version" ] &&
  add "Version mismatch: pyproject.toml has $pkg_version, doc/conf.py has $doc_version. They must be equal."

if grep -qE '^(eflips/|pyproject\.toml|poetry\.lock)' <<<"$changed"; then
  base_version=$(git show "$base:pyproject.toml" | ver)
  [ "$pkg_version" = "$base_version" ] &&
    add "Package code or dependencies changed but the version is still $base_version (same as main). Bump it per SemVer in pyproject.toml and doc/conf.py, or tell the user why this change needs no release."
fi

if grep -q '\.py$' <<<"$changed"; then
  out=$(run_tool black --check -q . 2>&1); rc=$?
  [ $rc -ne 0 ] && [ $rc -ne 127 ] && add "black --check failed (run black .):"$'\n'"$out"
  out=$(run_tool mypy eflips --explicit-package-bases --strict 2>&1); rc=$?
  [ $rc -ne 0 ] && [ $rc -ne 127 ] && add "mypy --strict failed:"$'\n'"$(tail -40 <<<"$out")"
fi

[ -n "$problems" ] && jq -n --arg r "Pre-PR checks failed:$problems" '{decision:"block", reason:$r}'
exit 0
