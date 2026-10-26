#!/bin/bash
# PostToolUse(Edit|Write): format the edited Python file with black.
. "$(dirname "$0")/run-tool.sh"
f=$(jq -r '.tool_input.file_path // empty')
case "$f" in
  *.py) cd "$CLAUDE_PROJECT_DIR" && run_tool black -q "$f" 2>/dev/null ;;
esac
exit 0
