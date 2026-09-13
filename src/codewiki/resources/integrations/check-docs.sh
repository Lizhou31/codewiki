#!/bin/sh
# Run from the project directory, with CodeWiki installed in the active environment.
# Optional first argument selects wiki.config.yaml; this checks the working tree.
set -eu
if [ "$#" -gt 0 ]; then
  codewiki build --strict --config "$1"
  codewiki review check --config "$1"
else
  codewiki build --strict
  codewiki review check
fi
