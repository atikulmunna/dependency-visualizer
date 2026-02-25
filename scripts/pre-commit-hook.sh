#!/usr/bin/env bash
# pre-commit-hook.sh — Check dependency files for circular dependencies
#
# Usage:
#   bash scripts/pre-commit-hook.sh           # auto-detect files
#   bash scripts/pre-commit-hook.sh deps.yaml # check specific file
#
# As a git pre-commit hook:
#   cp scripts/pre-commit-hook.sh .git/hooks/pre-commit
#   chmod +x .git/hooks/pre-commit

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}━━━ dgvis pre-commit: dependency check ━━━${NC}"

# Determine which files to check
if [ $# -gt 0 ]; then
    FILES=("$@")
else
    FILES=()
    for candidate in requirements.txt package.json go.mod; do
        if [ -f "$candidate" ]; then
            FILES+=("$candidate")
        fi
    done
    # Also check any .yaml/.yml files that look like dep files
    for f in *.yaml *.yml; do
        if [ -f "$f" ] && grep -q "dependencies:" "$f" 2>/dev/null; then
            FILES+=("$f")
        fi
    done
fi

if [ ${#FILES[@]} -eq 0 ]; then
    echo -e "${YELLOW}No dependency files found — skipping.${NC}"
    exit 0
fi

EXIT_CODE=0

for f in "${FILES[@]}"; do
    echo -e "\n${CYAN}Checking ${f}...${NC}"

    if ! python -m dgvis detect-cycles "$f" 2>/dev/null; then
        echo -e "${RED}✗ Circular dependencies found in ${f}${NC}"
        EXIT_CODE=1
    fi

    # Show SCC info (informational, doesn't fail the hook)
    python -m dgvis scc "$f" 2>/dev/null || true
done

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✓ All dependency files are cycle-free.${NC}"
else
    echo -e "${RED}✗ Commit blocked: circular dependencies detected.${NC}"
    echo -e "${YELLOW}  Fix the cycles above before committing.${NC}"
fi

exit $EXIT_CODE
