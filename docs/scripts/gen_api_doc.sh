#!/usr/bin/env bash
set -euo pipefail

# Generate Markdown API docs from SDK docstrings into the docs repo (Mintlify)
# Usage:
#   docs/scripts/gen_api_doc.sh [OUTPUT_DIR]
# If OUTPUT_DIR is not provided, defaults to ../openhands-docs/sdk/reference

REPO_ROOT=$(cd "$(dirname "$0")/../.." && pwd)
DOCS_REPO_DEFAULT="$REPO_ROOT/../openhands-docs/sdk/reference"
OUTPUT_DIR="${1:-$DOCS_REPO_DEFAULT}"

# Ensure output dir exists and is empty
rm -rf "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR"

# Generate using pdoc (isolated via uvx to avoid workspace dependency conflicts)
export PYTHONPATH="$REPO_ROOT/openhands-sdk:$PYTHONPATH"
PYTHONPATH="$REPO_ROOT/openhands-sdk:$PYTHONPATH" uvx --from griffe2md griffe2md openhands.sdk -o "$OUTPUT_DIR/index.mdx"

# Split per-top-level subpackage into individual pages for navigation clarity
while IFS= read -r -d '' pkg; do
  name=$(basename "$pkg")
  PYTHONPATH="$REPO_ROOT/openhands-sdk:$PYTHONPATH" uvx --from griffe2md griffe2md "openhands.sdk.$name" -o "$OUTPUT_DIR/$name.md"
done < <(find "$REPO_ROOT/openhands-sdk/openhands/sdk" -maxdepth 1 -mindepth 1 -type d ! -name '__pycache__' -print0)

# Post-process: remove __init__ module files, which aren't useful for client developers.
find "$OUTPUT_DIR" -type f -name "*.__init__.md" -delete || true
find "$OUTPUT_DIR" -type f -name "__init__.md" -delete || true

# Create a minimal README/index for the reference section
cat > "$OUTPUT_DIR/README.md" <<'MD'
# API Reference

Generated from Python docstrings. Do not edit manually. Regenerate via:

uv run docs/scripts/gen_api_doc.sh
MD

# Optionally create Mintlify-friendly index.mdx that links to generated modules
# Build a simple nav list of all md files relative to this directory
INDEX_FILE="$OUTPUT_DIR/index.mdx"
echo "# API Reference" > "$INDEX_FILE"
echo >> "$INDEX_FILE"
echo "> This section is auto-generated from docstrings. ✨" >> "$INDEX_FILE"
echo >> "$INDEX_FILE"

while IFS= read -r -d '' file; do
  rel=${file#"$OUTPUT_DIR/"}
  # Skip README and the index itself
  [[ "$rel" == "README.md" || "$rel" == "index.mdx" ]] && continue
  # Make mintlify link without .md extension
  link="${rel%.md}"
  name="${link##*/}"
  echo "- [${name}](${link})" >> "$INDEX_FILE"
done < <(find "$OUTPUT_DIR" -type f -name "*.md" -print0 | sort -z)

# Done
