#!/usr/bin/env bash
# Builds the branch that Anthropic's plugin directory tracks: the plugin as
# Claude Code loads it, without the parts for other clients and for
# development. Those parts hold the only code and text that read an API key
# from the machine (Codex and Grok Build have no plugin settings), which the
# directory does not accept in a submitted plugin.
#
#   scripts/release-directory.sh [source-ref]     default: HEAD
#
# Creates or moves the local branch `claude-directory` to one new commit on
# top of its previous one. Nothing is pushed: check the result, then
#   git push origin claude-directory
# In the directory's developer portal, enter `claude-directory` under
# "Branch or tag". Run this at every release; never edit the branch by hand.
set -euo pipefail

BRANCH=claude-directory
SOURCE=${1:-HEAD}
LEAVE_OUT=(codex .codex-plugin .agents mcp.json tests experiments docs scripts)
# No file that stays may read or name a key from the machine.
BANNED='INFRANODUS_API_KEY|set-key|clear-key|user_config\.api_key'

ROOT=$(git rev-parse --show-toplevel)
cd "$ROOT"
COMMIT=$(git rev-parse --verify "$SOURCE^{commit}")
VERSION=$(git show "$COMMIT:.claude-plugin/plugin.json" | sed -n 's/.*"version": *"\([^"]*\)".*/\1/p' | head -1)
WORK=$(mktemp -d "${TMPDIR:-/tmp}/claude-directory.XXXXXX")
trap 'git worktree remove --force "$WORK" >/dev/null 2>&1 || true; rm -rf "$WORK"' EXIT

if git show-ref --verify --quiet "refs/heads/$BRANCH"; then
	git worktree add --quiet "$WORK" "$BRANCH"
else
	git worktree add --quiet --detach "$WORK" "$COMMIT"
	git -C "$WORK" checkout --quiet --orphan "$BRANCH"
fi

# The tree of the source commit, minus what is left out.
git -C "$WORK" rm -r --quiet --cached --ignore-unmatch . >/dev/null
find "$WORK" -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +
git archive "$COMMIT" | tar -x -C "$WORK"
for path in "${LEAVE_OUT[@]}"; do rm -rf "${WORK:?}/$path"; done

if grep -rnIE "$BANNED" "$WORK" --exclude-dir=.git; then
	echo "release-directory: the lines above read or name a key from the machine; fix them on the source branch." >&2
	exit 1
fi

git -C "$WORK" add -A
if git -C "$WORK" diff --cached --quiet; then
	echo "release-directory: $BRANCH already matches $(git rev-parse --short "$COMMIT")"
	exit 0
fi
git -C "$WORK" commit --quiet -m "infranodus-memory $VERSION for the plugin directory (from $(git rev-parse --short "$COMMIT"))"
echo "release-directory: $BRANCH is now $(git -C "$WORK" rev-parse --short HEAD), version $VERSION"
echo "  files: $(git -C "$WORK" ls-files | wc -l | tr -d ' ')   left out: ${LEAVE_OUT[*]}"
echo "  check: claude plugin validate <a checkout of $BRANCH> --profile directory"
echo "  then:  git push origin $BRANCH"
