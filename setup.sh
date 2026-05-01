#!/usr/bin/env bash
# setup.sh — first-time install for aeon-music-maker.
#
# Validates ComfyUI reachability, installs Python deps, checks model files
# in the user's ComfyUI install, and prints download commands for any
# missing pieces. Idempotent — safe to re-run.
#
# Windows users: run via Git Bash or WSL.

set -euo pipefail

# Load .env if present
if [[ -f .env ]]; then
    set -a; source .env; set +a
fi

COMFYUI_URL="${COMFYUI_URL:-http://127.0.0.1:8188}"
COMFYUI_ROOT="${COMFYUI_ROOT:-}"
HF_TOKEN="${HF_TOKEN:-}"

c_red()   { printf '\033[31m%s\033[0m\n' "$*"; }
c_grn()   { printf '\033[32m%s\033[0m\n' "$*"; }
c_yel()   { printf '\033[33m%s\033[0m\n' "$*"; }
c_blu()   { printf '\033[36m%s\033[0m\n' "$*"; }

c_blu "==> aeon-music-maker setup"
echo ""

# 1. ComfyUI reachable?
c_blu "[1/4] Checking ComfyUI at $COMFYUI_URL"
if curl -sf "$COMFYUI_URL/system_stats" >/dev/null 2>&1; then
    c_grn "      ✓ ComfyUI is reachable"
else
    c_red "      ✗ ComfyUI not reachable at $COMFYUI_URL"
    c_yel "        Start ComfyUI before continuing, then re-run setup.sh."
    c_yel "        Override URL in .env: COMFYUI_URL=http://<host>:<port>"
    exit 1
fi

# 2. Python + deps
c_blu "[2/4] Installing Python dependencies"
if ! command -v python >/dev/null 2>&1; then
    c_red "      ✗ python not found on PATH"
    exit 1
fi
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt
c_grn "      ✓ deps installed"

# 3. ffmpeg / ffprobe
c_blu "[3/4] Checking ffmpeg/ffprobe"
ffmpeg_bin="${FFMPEG:-ffmpeg}"
ffprobe_bin="${FFPROBE:-ffprobe}"
if command -v "$ffmpeg_bin" >/dev/null 2>&1 && command -v "$ffprobe_bin" >/dev/null 2>&1; then
    c_grn "      ✓ found"
else
    c_red "      ✗ ffmpeg or ffprobe missing"
    c_yel "        Install with: brew install ffmpeg  (macOS)"
    c_yel "                       sudo apt install ffmpeg  (Debian/Ubuntu)"
    c_yel "                       https://www.ffmpeg.org/download.html  (Windows)"
    c_yel "        Or set FFMPEG / FFPROBE env vars in .env if non-PATH."
    exit 1
fi

# 4. ACE Step models
c_blu "[4/4] Checking ACE Step models in ComfyUI"
if [[ -z "$COMFYUI_ROOT" ]]; then
    c_yel "      COMFYUI_ROOT not set in .env. Skipping local model check."
    c_yel "      If you're driving a remote ComfyUI, ensure these models are present there:"
    cat <<EOF

      models/diffusion_models/acestep_v1.5_xl_base.safetensors        (~20 GB, REQUIRED for xl_base)
      models/diffusion_models/acestep_v1.5_xl_sft_bf16.safetensors    (~10 GB, optional)
      models/diffusion_models/acestep_v1.5_xl_turbo_bf16.safetensors  (~10 GB, optional, for previews)
      models/diffusion_models/acestep_v1.5_xl_merge_base_sft_ta_0.5.safetensors  (~10 GB, optional)
      models/diffusion_models/acestep_v1.5_turbo.safetensors          (~5 GB, optional, smallest)
      models/text_encoders/qwen_0.6b_ace15.safetensors                 (~1.2 GB, REQUIRED)
      models/text_encoders/qwen_4b_ace15.safetensors                   (~8 GB, REQUIRED)
      models/vae/ace_1.5_vae.safetensors                               (~330 MB, REQUIRED)

EOF
else
    missing=()
    REQUIRED=(
        "diffusion_models/acestep_v1.5_xl_base.safetensors"
        "text_encoders/qwen_0.6b_ace15.safetensors"
        "text_encoders/qwen_4b_ace15.safetensors"
        "vae/ace_1.5_vae.safetensors"
    )
    OPTIONAL=(
        "diffusion_models/acestep_v1.5_xl_sft_bf16.safetensors"
        "diffusion_models/acestep_v1.5_xl_turbo_bf16.safetensors"
        "diffusion_models/acestep_v1.5_turbo.safetensors"
    )
    for m in "${REQUIRED[@]}"; do
        if [[ ! -f "$COMFYUI_ROOT/models/$m" ]]; then
            missing+=("REQUIRED:$m")
        fi
    done
    for m in "${OPTIONAL[@]}"; do
        if [[ ! -f "$COMFYUI_ROOT/models/$m" ]]; then
            missing+=("optional:$m")
        fi
    done

    if [[ ${#missing[@]} -eq 0 ]]; then
        c_grn "      ✓ all required + optional ACE Step models present"
    else
        c_yel "      ${#missing[@]} model(s) missing. Download with:"
        echo ""
        for m in "${missing[@]}"; do
            tier="${m%%:*}"
            path="${m#*:}"
            base="https://huggingface.co/ace-step/ACE-Step-v1-3.5B/resolve/main/$(basename "$path")"
            echo "      [$tier] $path"
            echo "        curl -L --create-dirs -o \"$COMFYUI_ROOT/models/$path\" \\"
            echo "             ${HF_TOKEN:+-H \"Authorization: Bearer \$HF_TOKEN\"} $base"
            echo ""
        done
        c_yel "      Or use ComfyUI Manager / huggingface-cli for batch download."
    fi
fi

echo ""
c_grn "==> Setup complete."
c_blu "    Try it:"
echo '      python scripts/music_maker.py \'
echo '          --prompt "lofi jazz, warm Rhodes, brushed drums" \'
echo '          --duration 60 --bpm 78 --variant xl_turbo \'
echo '          -o my_first_track.flac'
