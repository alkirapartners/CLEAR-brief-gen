#!/bin/bash
# Backs up /var/www/briefgen/data/ to the 'data' branch on GitHub

REPO_URL='git@github-briefgen-backup:alkirapartners/CLEAR-brief-gen.git'
DATA_DIR='/var/www/briefgen/data'
WORK_DIR='/tmp/briefgen-data-backup'

# Clone only the data branch (shallow) into a temp dir
rm -rf "$WORK_DIR"
if git ls-remote --exit-code --heads "$REPO_URL" data &>/dev/null; then
  git clone --depth=1 --branch=data "$REPO_URL" "$WORK_DIR" -q
else
  # Branch doesn't exist yet — create it as an orphan
  mkdir -p "$WORK_DIR"
  cd "$WORK_DIR"
  git init -q
  git remote add origin "$REPO_URL"
  git checkout --orphan data
fi

cd "$WORK_DIR"
git config user.email 'backup@alkira-briefgen'
git config user.name 'Brief Generator Backup'

# Copy data files (exclude tokens and sessions — they're transient)
cp "$DATA_DIR/admins.json"             . 2>/dev/null || true
cp "$DATA_DIR/domains.json"            . 2>/dev/null || true
cp "$DATA_DIR/team-synced-admins.json" . 2>/dev/null || true

# Commit and push only if something changed
git add -A
if ! git diff --cached --quiet; then
  git commit -m "Data backup $(date '+%Y-%m-%d %H:%M')" -q
  git push origin data -q
  echo "$(date): backup pushed to GitHub data branch"
else
  echo "$(date): no changes, skipping backup"
fi

rm -rf "$WORK_DIR"
