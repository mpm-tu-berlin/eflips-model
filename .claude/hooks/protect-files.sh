#!/bin/bash
# PreToolUse(Edit|Write): poetry.lock must only be changed by poetry itself.
f=$(jq -r '.tool_input.file_path // empty')
case "$f" in
  */poetry.lock)
    echo "Do not hand-edit poetry.lock. Change dependencies in pyproject.toml and ask the user to run 'poetry lock'." >&2
    exit 2 ;;
esac
exit 0
