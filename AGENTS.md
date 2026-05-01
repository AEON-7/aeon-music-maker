# AGENTS.md — aeon-music-maker

Instructions for AI agents that operate this tool.

## Setup contract

If the user has not yet installed this repo, your job is to:

1. **Verify ComfyUI is reachable** at `${COMFYUI_URL}` (default `http://127.0.0.1:8188`):
   ```bash
   curl -s "${COMFYUI_URL:-http://127.0.0.1:8188}/system_stats" | head
   ```
   If 404 or no response, prompt the user to start ComfyUI before continuing.

2. **Verify Python deps** by running `./setup.sh` once. The script:
   - Installs `requirements.txt` (pedalboard, librosa, soundfile, numpy, scipy, requests)
   - Confirms ffmpeg/ffprobe exist on PATH (or honors `FFMPEG` / `FFPROBE` env vars)
   - Checks for required ACE Step model files in `${COMFYUI_ROOT}/models/`
   - Lists missing models with download commands (uses huggingface-cli; can also be done via the ComfyUI Manager UI)

3. **Verify the user has filled in `.env`**:
   ```bash
   cp .env.example .env
   # edit COMFYUI_URL, COMFYUI_ROOT, and any preset overrides
   ```

## Invocation contract

**ALWAYS** call the CLI — never reconstruct ComfyUI workflows by hand:

```bash
python scripts/music_maker.py \
    --prompt "<comma-separated descriptor cloud>" \
    --duration <seconds> \
    --bpm <int> --key "<key>" \
    --variant <xl_base|xl_sft|xl_base_sft|xl_turbo|base_turbo> \
    --master <auto|off|default|edm|trap|chill|orchestral|jazz> \
    -o <output_path>
```

Parameters worth knowing:

| Flag | Default | Meaning |
|---|---|---|
| `--variant` | `xl_base` | `xl_base` for masters; `xl_turbo` for quick previews |
| `--master` | `auto` | Auto-detects preset from prompt keywords. Override only when needed. |
| `--target-lufs` | preset default | EDM ‑12, default ‑14, jazz ‑15, chill ‑16, orchestral ‑18 |
| `--keep-raw` | off | Keep pre-mastered file at `<output>.raw.<ext>` for A/B |
| `--seed` | random | Print this when the user loves a track — they can iterate exactly |

## Prompt engineering rules

The full vocabulary is documented in `SKILL.md` — read it before crafting prompts. Highlights:

**Words that CREATE dynamics** (use these):
`punchy / staccato / sparse intro / breathing room / loud-quiet-loud / sudden silence / decrescendo / call and response / [intro: ...] [build: ...] [drop: ...] [breakdown: ...] [outro: ...]`

**Words that KILL dynamics** (avoid):
`wall of sound / dense / maximal / radio-ready loud / massive / never stops / always moving / compressed to the max`

Structural section tags inside `[brackets]` work best — ACE respects them as compositional cues.

## When to use this vs. sibling repos

| User asks for | Use |
|---|---|
| Standalone music track / song / album cut | This repo |
| Background music for a radio drama | This repo, then mix into `aeon-radio-drama` |
| Background music for a film | This repo with `--master orchestral`, then feed to `aeon-movie-maker` |
| Audio-reactive music video | This repo, then feed FLAC to `aeon-music-video` |

## Failure modes you'll hit

| Symptom | Cause | Fix |
|---|---|---|
| `Submit failed: 400` | Custom node missing or model file not found | Run `./sync.sh` to delta-fetch deps |
| `ConnectionRefusedError` on `/prompt` | ComfyUI not running at `${COMFYUI_URL}` | Start it; verify URL |
| Distorted / hollow output | Used `--variant xl_base` with non-APG template | Tool always picks the right template per variant — check you didn't edit `VARIANTS` dict |
| Mastered output much louder than expected | `--master` preset mismatch (e.g. `edm` on a quiet ballad) | Force preset: `--master jazz` or `--master default` |
| `[Errno 22]` on model load | Windows mmap bug in ComfyUI | Confirm `comfy/utils.py` line 41 sets `DISABLE_MMAP = True` on the ComfyUI host |

## Output location

By default, files land at `${OUTPUT_DIR}/<slug>_<seed>.flac` where `OUTPUT_DIR` defaults to `${COMFYUI_ROOT}/output` if `COMFYUI_ROOT` is set, else `<repo>/output`. Override with `-o <path>` per call. The tool always creates parent dirs.

## A note on the mastering chain

Don't try to "improve" the chain by adding a compressor or tighter LUFS targets. The whole point of the design is to *preserve* dynamics, not crush them. If a track sounds flat, the fix is in the prompt (more dynamics vocabulary, structural section tags), not the mastering. Read `SKILL.md` § "Diagnosing a flat-sounding track".
