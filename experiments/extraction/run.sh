#!/bin/bash
# Run the ingest prompt on every excerpt in out/excerpts with each model.
# Usage: ./run.sh [models...]   (default: haiku sonnet)
# Env: PROMPT (default ingest-prompt.md), OUT (default out), SCHEMA (optional
# JSON schema file for structured output).
# Hooks, tools, MCP and session persistence are off so the test doesn't feed
# claude-mem, mem0 or any other memory plugin.
set -u
cd "$(dirname "$0")"
models=("${@:-haiku sonnet}"); [ $# -eq 0 ] && models=(haiku sonnet)
export PROMPT="${PROMPT:-ingest-prompt.md}" OUT="${OUT:-out}" SCHEMA="${SCHEMA:-}"
mkdir -p "$OUT/results"
one() {
  ex="$1"; model="$2"
  base=$(basename "$ex" .txt); proj=$(echo "$base" | cut -d- -f2- | sed -E 's/-(trimmed2|trimmed|full)$//')
  outf="$OUT/results/$base.$model.json"
  schema=(); [ -n "$SCHEMA" ] && schema=(--json-schema "$(cat "$SCHEMA")")
  [ -s "$outf" ] && return
  start=$(date +%s)
  python3 -I -c 'import sys; p=open(sys.argv[1]).read(); e=open(sys.argv[2]).read(); sys.stdout.write(p.replace("{PROJECT}", sys.argv[3]).replace("{EXCERPT}", e))' "$PROMPT" "$ex" "$proj" \
    | (cd "${TMPDIR:-/tmp}" && claude -p --model "$model" --settings '{"disableAllHooks": true}' --strict-mcp-config --tools "" \
        --no-session-persistence --setting-sources "" --output-format json "${schema[@]}" \
        --system-prompt "You are a precise information-extraction function. Output only what the user message asks for.") > "$outf.tmp" 2> "$outf.err"
  mv "$outf.tmp" "$outf"; echo "$base $model $(( $(date +%s) - start ))s"
}
export -f one
for m in "${models[@]}"; do for ex in "$OUT"/excerpts/*.txt; do echo "$ex $m"; done; done | xargs -P 6 -L 1 bash -c 'one "$0" "$1"'
