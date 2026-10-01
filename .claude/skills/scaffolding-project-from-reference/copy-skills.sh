#!/usr/bin/env bash
# Copies every entry of the reference's .claude/skills into the new project's .claude/skills.
# An entry the new project already has is left as it is and reported as skipped.
# Usage: bash copy-skills.sh <reference folder> <new project folder>
set -euo pipefail

if [ "$#" -ne 2 ]; then
  echo "usage: bash copy-skills.sh <reference folder> <new project folder>" >&2
  exit 2
fi

src="$1/.claude/skills"
dst="$2/.claude/skills"

if [ ! -d "$2" ]; then
  echo "new project folder $2 does not exist" >&2
  exit 1
fi

if [ ! -d "$src" ]; then
  echo "$src does not exist: nothing to copy"
  exit 0
fi

shopt -s nullglob dotglob
mkdir -p "$dst"
for entry in "$src"/*; do
  name=$(basename "$entry")
  if [ -e "$dst/$name" ] || [ -L "$dst/$name" ]; then
    echo "skipped $dst/$name: it exists"
  else
    # -L: a symlinked skill lands as files, so the new project's repo holds it.
    cp -RL "$entry" "$dst/$name"
    echo "copied $dst/$name"
  fi
done
