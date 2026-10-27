#!/usr/bin/env bash
# One collection run: collect, append, then commit + push the data so it survives
# the ephemeral container. Safe to run repeatedly (all writes are append + de-dup).
set -uo pipefail
cd "$(dirname "$0")"
BRANCH="${PRED_BRANCH:-claude/gracious-feynman-cw0lr0}"

python3 -c "import Crypto, requests" 2>/dev/null || pip install -q -r requirements.txt
LINE="$(python3 collector.py)"
echo "$LINE"

git add data
if git diff --cached --quiet; then
  echo "nothing to commit"; exit 0
fi
git commit -q -m "data(pancake-prediction): $(echo "$LINE" | cut -c1-120)"
for delay in 0 2 4 8 16; do
  sleep "$delay"
  git push -q -u origin "$BRANCH" && exit 0
done
echo "push failed after retries; data is committed locally" >&2
exit 1
