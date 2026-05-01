# AGENTS.md — aeon-music-maker

Instructions for AI agents that operate this tool.

## Step 0 — Determine execution mode

**Before doing anything else**, figure out where ComfyUI is running relative to where you (the agent) are running. This determines the entire shape of every command you'll issue.

### Local mode — ComfyUI is on the SAME machine as you

Symptoms:
- The user's `.env` has `COMFYUI_URL=http://127.0.0.1:8188` AND ComfyUI is reachable at that URL from your shell
- Running `curl -sf http://127.0.0.1:8188/system_stats` succeeds locally
- The user mentions running everything on one machine

In local mode, you invoke the CLI directly. **Do not use SSH.**

```bash
python scripts/music_maker.py --prompt "..." -o /local/path/track.flac
```

### Remote mode — ComfyUI is on a DIFFERENT machine

Symptoms:
- `COMFYUI_URL` points to a non-loopback IP (e.g., `http://192.168.x.x:8188`), OR
- The user has set up an SSH tunnel and `COMFYUI_URL=http://127.0.0.1:8188` works locally but only because of the tunnel
- The user mentions a "GPU box", "DGX Spark", "remote workstation", "headless server", etc.

In remote mode, you have two options for HOW you run the CLI:

**Remote-A — CLI runs on the LOCAL machine, hits remote ComfyUI HTTP API:**
- This is the default and simplest. Your shell is on the laptop; the CLI's HTTP calls cross the network to ComfyUI on the GPU box.
- Output FLACs land on the LOCAL filesystem (the CLI receives them as bytes from the API).
- No SSH commands needed for invocation; just regular `python scripts/music_maker.py ...`.

**Remote-B — CLI runs on the REMOTE machine via SSH (legacy pattern):**
- Only use this if the user explicitly requests it (e.g., to keep all renders + outputs centralized on the GPU box).
- Wrap commands in: `ssh ${SSH_USER}@<host> 'cd /path/to/aeon-music-maker && python scripts/music_maker.py ...'`
- Output stays on the remote box; user pulls with `scp` afterward.

**Default to Remote-A unless the user says otherwise.** It's simpler, it works with cloud ComfyUI, and it doesn't require shell access on the GPU box.

## Step 1 — Setup contract

After determining mode, ensure the environment is ready:

1. **Verify ComfyUI is reachable** at `${COMFYUI_URL}`:
   ```bash
   curl -sf "${COMFYUI_URL:-http://127.0.0.1:8188}/system_stats" >/dev/null && echo "OK" || echo "FAIL"
   ```
   If `FAIL`:
   - **Local mode:** prompt the user to start ComfyUI (`python main.py` in the ComfyUI dir).
   - **Remote mode:** verify the host is reachable (`ping`), the port is open (`nc -zv host 8188`), and ComfyUI is started with `--listen 0.0.0.0`.

2. **Verify Python deps** by running `./setup.sh` once. Idempotent — runs `pip install -r requirements.txt`, checks ffmpeg/ffprobe on PATH, and inventories model files in `${COMFYUI_ROOT}/models/`.

3. **Verify the user has filled in `.env`**:
   ```bash
   test -f .env || { echo "Missing .env — copy from .env.example"; exit 1; }
   ```
   Required values: `COMFYUI_URL`. Optional but recommended: `COMFYUI_ROOT` (only in local mode).

4. **If `setup.sh` reports missing models**, instruct the user to install them via:
   - **ComfyUI Manager** — easiest, just click "Install missing models" in ComfyUI's web UI
   - **`huggingface-cli download`** — for batch installs (needs `HF_TOKEN` from https://huggingface.co/settings/tokens if any model is gated)
   - **Manual download** from the URLs `setup.sh` prints

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
