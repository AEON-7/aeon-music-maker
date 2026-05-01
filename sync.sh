#!/usr/bin/env bash
# sync.sh — incremental update for aeon-music-maker.
#
# Pulls latest repo content, refreshes templates, re-runs python deps install,
# and shows model-delta status. Skip the model check with --no-models.
# Mirrors the pattern used in https://github.com/AEON-7/comfyui-aeon-spark

set -euo pipefail

NO_MODELS=0
YES=0
for arg in "$@"; do
    case "$arg" in
        --no-models) NO_MODELS=1 ;;
        --yes|-y)    YES=1 ;;
        *) echo "unknown flag: $arg"; exit 2 ;;
    esac
done

c_blu(){ printf '\033[36m%s\033[0m\n' "$*"; }
c_grn(){ printf '\033[32m%s\033[0m\n' "$*"; }
c_yel(){ printf '\033[33m%s\033[0m\n' "$*"; }

if [[ -f .env ]]; then
    set -a; source .env; set +a
fi

c_blu "==> aeon-music-maker sync"

# 1. Pull latest
c_blu "[1/3] git pull"
git pull --ff-only

# 2. Refresh deps
c_blu "[2/3] pip install -r requirements.txt (delta)"
python -m pip install --quiet -r requirements.txt
c_grn "      ✓ deps up to date"

# 3. Model delta-check (skip if --no-models)
if [[ $NO_MODELS -eq 1 ]]; then
    c_yel "[3/3] --no-models: skipping model check"
else
    c_blu "[3/3] model delta-check"
    if [[ -z "${COMFYUI_ROOT:-}" ]]; then
        c_yel "      COMFYUI_ROOT not set; can't check local models."
    else
        ./setup.sh | tail -n 30 || true
    fi
fi

echo ""
c_grn "==> sync complete"
