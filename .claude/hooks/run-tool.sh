# Sourced by the other hooks. Runs a dev tool from the poetry env if poetry exists,
# else from PATH. Returns 127 if the tool is unavailable (hooks then skip that check).
run_tool() {
  if command -v poetry >/dev/null 2>&1; then
    poetry run "$@"
  elif command -v "$1" >/dev/null 2>&1; then
    "$@"
  else
    return 127
  fi
}
