# aeon-music-maker


[![☕ Tips](https://img.shields.io/badge/%E2%98%95_Tips-Support_the_work-ff5e5b?style=flat)](https://github.com/AEON-7/AEON-7#-support-the-work)
> Standalone music generator with studio-grade dynamics-preserving mastering. Wraps ACE Step 1.5 XL (full-quality APG chain or fast distilled variants) with a one-pass mastering chain (HPF → EQ → tape saturation → LUFS gain-match → true-peak ceiling). FLAC-lossless output. Auto-detects the right mastering preset from your prompt.

Part of the **AEON Media Production** family of agent-driven media tools.

## What this gives you

- **5 ACE Step variants** — `xl_base` (full fp32, 50 steps, APG chain) → `base_turbo` (8 steps, ~8 s per 90 s of audio). One CLI flag.
- **6 mastering presets** — `default / edm / trap / chill / orchestral / jazz` — auto-picked from prompt keywords or pinned with `--master <preset>`. Tuned to preserve dynamics rather than crush them.
- **Lossless 48 kHz stereo FLAC** by default; `.wav` and `.mp3` exports.
- **Reproducibility via seeds** — every run prints the seed; same prompt + same seed = same track, byte-identical.
- **Lyrics support** — ACE Step actually sings them. Pass with `--lyrics`.
- **One command, no node graphs** — calls into ComfyUI under the hood; you never touch a workflow JSON.

## Quick start

```bash
# 1. Clone + install deps
git clone https://github.com/AEON-7/aeon-music-maker.git
cd aeon-music-maker
cp .env.example .env       # edit COMFYUI_ROOT + COMFYUI_URL
./setup.sh                 # check ComfyUI, install python deps, fetch missing models

# 2. Generate a track
python scripts/music_maker.py \
    --prompt "lofi jazz, warm Rhodes, brushed drums, vinyl crackle, rainy window" \
    --duration 180 --bpm 78 --key "A minor" \
    --variant xl_base --master auto \
    -o my_first_track.flac
```

That's it. The tool talks to your ComfyUI server at `${COMFYUI_URL}`, runs the full APG chain, and writes a mastered FLAC to your chosen path.

## Prerequisites

- A running ComfyUI instance reachable at `${COMFYUI_URL}` (default `http://127.0.0.1:8188`)
- Python 3.10+
- ffmpeg + ffprobe on PATH (or set `FFMPEG`/`FFPROBE` env vars)
- About 30 GB free disk for the full ACE Step model set (smaller variants are 5–10 GB each)

The included `setup.sh` checks all of these and fetches missing pieces.

## Configuration

All configuration goes through environment variables (loaded from `.env` if present). Copy `.env.example` to `.env` and fill in your values, OR set the variables in your shell.

### Where to run this CLI: local vs remote ComfyUI

This tool is a **client** for a ComfyUI server — it sends workflow JSON to ComfyUI's HTTP API and receives back the generated audio. Two ways to run it:

#### Mode A — Local (CLI runs on the same machine as ComfyUI)

The simplest setup. ComfyUI is running at `http://127.0.0.1:8188` on your machine, and you run the CLI in the same terminal/shell. Set:

```bash
COMFYUI_URL=http://127.0.0.1:8188
COMFYUI_ROOT=/path/to/your/local/ComfyUI    # optional — only if you want output in ComfyUI's tree
```

No SSH involved. Run scripts directly:

```bash
python scripts/music_maker.py --prompt "..." -o track.flac
```

#### Mode B — Remote (CLI runs on a different machine from ComfyUI)

ComfyUI runs on a GPU box (workstation, DGX Spark, headless server) and you orchestrate from your laptop. Two sub-options:

**B1 — Direct HTTP** (simplest if both machines are on the same LAN):
```bash
COMFYUI_URL=http://<gpu-box-ip>:8188
# Don't set COMFYUI_ROOT — output will be written locally to ./output/
```
Make sure ComfyUI is started with `--listen 0.0.0.0` (default binding is loopback only) and that your firewall allows port 8188.

**B2 — SSH tunnel** (more secure, no firewall changes):
```bash
# In a separate terminal, before running the CLI:
ssh -L 8188:127.0.0.1:8188 user@<gpu-box-host>
# Leave it running. Then in your CLI shell:
COMFYUI_URL=http://127.0.0.1:8188   # tunnel forwards to remote ComfyUI
```
The CLI thinks it's talking to localhost; the SSH tunnel forwards to the remote ComfyUI process.

### All environment variables

| Variable | Required? | Default | What it is |
|---|---|---|---|
| `COMFYUI_URL` | required | `http://127.0.0.1:8188` | HTTP endpoint of your ComfyUI server. See "local vs remote" above. |
| `COMFYUI_ROOT` | optional | (repo dir) | Path to ComfyUI install root. **Local mode only** — if set, output FLACs land in `${COMFYUI_ROOT}/output/music/`. Leave unset for remote mode. |
| `OUTPUT_DIR` | optional | `${COMFYUI_ROOT}/output` or `./output` | Override where outputs land. |
| `FFMPEG` | optional | `ffmpeg` from PATH | Full path to `ffmpeg` binary if not on PATH. |
| `FFPROBE` | optional | `ffprobe` from PATH | Full path to `ffprobe` binary if not on PATH. |
| `ACE_DEFAULT_VARIANT` | optional | `xl_base` | Default ACE variant when `--variant` is omitted. |
| `MASTER_DEFAULT_PRESET` | optional | `auto` | Default mastering preset. Per-call `--master` always overrides. |
| `HF_TOKEN` | optional | none | HuggingFace access token. Only needed if `setup.sh` is auto-downloading gated models. Get one free at https://huggingface.co/settings/tokens (Read scope is enough). |

### How to know which model files you need

Run `./setup.sh` after setting `COMFYUI_URL` + `COMFYUI_ROOT`. It checks for every required model file at the canonical path under `${COMFYUI_ROOT}/models/` and prints download commands for any missing ones. The fastest way to install the models:

1. **Use ComfyUI Manager** (the in-browser UI button at the top of ComfyUI) — most ACE Step models are one-click installable.
2. **`huggingface-cli download`** — for batch installs from `Lightricks` / `ace-step` HF repositories.
3. **Manual download** from `https://huggingface.co/ace-step/ACE-Step-v1-3.5B` and place files at the paths `setup.sh` lists.

`HF_TOKEN` is only needed for option 2 if any model is gated (most aren't).

## Updating an existing install

If you cloned this repo before and want to pick up the latest changes, run:

```bash
cd /path/to/aeon-music-maker
./sync.sh
```

The script:
1. **Detects local uncommitted changes** and offers to stash + re-apply them after the pull
2. **Shows a diff preview** — commit list + files-changed summary — before actually pulling
3. **Asks for confirmation** before applying anything
4. **Refreshes Python deps** via `pip install -r requirements.txt`
5. **Re-runs the model delta-check** so any new models can be flagged

### Flags

| Flag | What it does |
|---|---|
| `./sync.sh` | Default — interactive, shows diff, prompts before pulling |
| `./sync.sh --dry-run` (or `-n`) | Show what would change without actually pulling |
| `./sync.sh --yes` (or `-y`) | Non-interactive — accept all prompts (CI / cron use) |
| `./sync.sh --no-models` | Skip the model file check (faster if you know nothing changed there) |
| `./sync.sh --help` | Print usage |

### What if I customized something?

The sync script auto-stashes any uncommitted local edits before pulling, then re-applies them. If your edits don't conflict with the incoming changes, you'll never notice. If they do, sync stops with clear instructions.

`.env`, `output/`, `__pycache__/`, and other personal files are gitignored — they're never touched by sync.

## Usage

```
python scripts/music_maker.py [options]

  --prompt STR            (required) comma-separated music descriptors
  --duration FLOAT        track length in seconds (default 120, max ~240)
  --bpm INT               tempo (default 75)
  --key STR               key/scale, e.g. "A minor", "C# major" (default "A minor")
  --lyrics STR_OR_PATH    literal lyrics OR path to .txt file (default empty = instrumental)
  --variant {xl_base|xl_sft|xl_base_sft|xl_turbo|base_turbo}  (default xl_base)
  --steps INT             override the variant's preset step count
  --cfg FLOAT             override the variant's preset CFG
  --seed INT              fixed seed for reproducibility
  --output / -o PATH      output file (.flac / .wav / .mp3) — default is
                          output/<slug>_<seed>.flac
  --master {auto|off|default|edm|trap|chill|orchestral|jazz}
                          mastering preset (default 'auto' = pick from prompt)
  --target-lufs FLOAT     override the preset's target LUFS
  --keep-raw              keep the pre-mastered file alongside the mastered output
```

See `SKILL.md` for the full prompt-engineering recipe, the variant comparison table, the dynamics-preserving prompt vocabulary, and the mastering preset details.

## How the mastering works

Most "mastering" tools crush dynamics. This one is built around the principle that you cannot restore dynamics the generator never produced — but you can stop *destroying* what's there. The chain does the bare minimum:

```
raw.flac
  ├─ HighpassFilter(20–30 Hz)        remove sub-rumble
  ├─ LowShelf(–1..2 dB @ 150–200 Hz) tame mud
  ├─ PeakFilter(+1..2 dB @ 2–4 kHz)  presence (additive)
  ├─ HighShelf(+1.5..3 dB @ 10–12 k) air
  ├─ Distortion(0..4 dB)             light tape warmth
  ├─ Gain match to target LUFS       (capped at +6 dB to avoid boosting silence)
  ├─ Clipping ceiling (–0.8..–2 dBFS) brick-wall safety
mastered.flac
```

**No compressor in the default chain.** No `loudnorm LRA=X`. Both squash dynamics. Validated against orchestral material with **LRA preserved within ~1 LU** (typical 22 → 22.9 on a 23 LU source).

## Project structure

```
aeon-music-maker/
├── README.md            this file
├── AGENTS.md            agent setup + invocation contract
├── SKILL.md             full prompt-engineering + mastering guide
├── ATTRIBUTION.md       upstream credits
├── LICENSE              MIT
├── .env.example         all configurable env vars
├── setup.sh             first-time install
├── sync.sh              incremental update (pull + delta-fetch missing models)
├── requirements.txt     python deps (pedalboard, librosa, etc.)
├── scripts/
│   ├── music_maker.py     main CLI
│   └── music_mastering.py mastering chain (also callable standalone)
└── templates/
    ├── ace_step_music_apg_api.json     full-quality APG chain (xl_base / xl_sft)
    └── ace_step_music_simple_api.json  fast simple-KSampler (turbo / merged variants)
```

## License

MIT. See `LICENSE`.

## Credits

- **ACE Step 1.5** by [StepFun](https://github.com/ace-step/ACE-Step) — the music generation model
- **Pedalboard** by [Spotify](https://github.com/spotify/pedalboard) — Python audio FX framework powering the mastering chain
- **librosa**, **soundfile**, **numpy**, **scipy** — audio analysis/IO substrate

Full attribution in `ATTRIBUTION.md`.

## See also

Sister repos in the AEON Media Production family:

- [`aeon-radio-drama`](https://github.com/AEON-7/aeon-radio-drama) — full radio drama production (dialogue + music + SFX + sidechain mix)
- [`aeon-movie-maker`](https://github.com/AEON-7/aeon-movie-maker) — fast cinematic video via LTX 2.3 22B
- [`aeon-music-video`](https://github.com/AEON-7/aeon-music-video) — audio-reactive video generation
- [`comfyui-aeon-spark`](https://github.com/AEON-7/comfyui-aeon-spark) — base ComfyUI Docker stack with pre-staged models

---

## ☕ Support the work

If this release has been useful, tips are deeply appreciated — they go directly toward more compute, more models, and more open releases.

<table align="center">
  <tr>
    <td align="center" width="50%">
      <strong>₿ Bitcoin (BTC)</strong><br/>
      <img src="https://raw.githubusercontent.com/AEON-7/AEON-7/main/assets/qr/btc.png" alt="BTC QR" width="200"/><br/>
      <sub><code>bc1q09xmzn00q4z3c5raene0f3pzn9d9pvawfm0py4</code></sub>
    </td>
    <td align="center" width="50%">
      <strong>Ξ Ethereum (ETH)</strong><br/>
      <img src="https://raw.githubusercontent.com/AEON-7/AEON-7/main/assets/qr/eth.png" alt="ETH QR" width="200"/><br/>
      <sub><code>0x1512667F6D61454ad531d2E45C0a5d1fd82D0500</code></sub>
    </td>
  </tr>
  <tr>
    <td align="center" width="50%">
      <strong>◎ Solana (SOL)</strong><br/>
      <img src="https://raw.githubusercontent.com/AEON-7/AEON-7/main/assets/qr/sol.png" alt="SOL QR" width="200"/><br/>
      <sub><code>DgQsjHdAnT5PNLQTNpJdpLS3tYGpVcsHQCkpoiAKsw8t</code></sub>
    </td>
    <td align="center" width="50%">
      <strong>ⓜ Monero (XMR)</strong><br/>
      <img src="https://raw.githubusercontent.com/AEON-7/AEON-7/main/assets/qr/xmr.png" alt="XMR QR" width="200"/><br/>
      <sub><code>836XrSKw4R76vNi3QPJ5Fa9ugcyvE2cWmKSPv3AhpTNNKvqP8v5ba9JRL4Vh7UnFNjDz3E2GXZDVVenu3rkZaNdUFhjAvgd</code></sub>
    </td>
  </tr>
</table>

> **Ethereum L2s (Base, Arbitrum, Optimism, Polygon, etc.) and EVM-compatible tokens** can be sent to the same Ethereum address.
