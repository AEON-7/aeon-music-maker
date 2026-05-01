#!/usr/bin/env python3
"""Music Maker — standalone ACE Step 1.5 music generation with maximum-fidelity APG chain.

DISTINCT from scene_production_tool/radio_drama.py's music stage. That one uses the
faster simple-KSampler template tuned for "good enough" music beds under dialogue.
This tool uses the full APG + SamplerCustomAdvanced chain for tracks where audio
quality is the primary deliverable — an album cut, a standalone single, a
vocalised song. Accepts lyrics (ACE Step sings them).

Variants:
  xl_base       (default, max quality)   full fp32 base, APG chain, 50 steps @ CFG 7
  xl_sft        (near-max, faster)       XL SFT bf16, APG chain, 45 steps @ CFG 6
  xl_base_sft   (balanced, simpler)      merged base+SFT bf16, simple KSampler, 35 steps @ CFG 3
  xl_turbo      (preview / iteration)    XL turbo bf16, simple KSampler, 10 steps @ CFG 1
  base_turbo    (fastest, lowest)        1.5 base turbo, simple KSampler, 8 steps @ CFG 1

Usage:
  python music_maker.py --prompt "lofi jazz, warm Rhodes, ..." --duration 180 --bpm 78 --key "A minor"
  python music_maker.py --prompt "..." --lyrics lyrics.txt --duration 120 --variant xl_base
  python music_maker.py --prompt "..." --duration 60 --variant xl_turbo --output preview.mp3
"""
import argparse, json, os, random, shutil, subprocess, sys, time
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Repo root is one level up from scripts/. Override with COMFYUI_ROOT env var
# if you want output to land inside an existing ComfyUI install (so templates,
# models, and outputs share a single tree). Otherwise the repo writes outputs
# under ./output relative to its own location.
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
COMFYUI_ROOT = os.environ.get("COMFYUI_ROOT", REPO_ROOT)
FFMPEG = shutil.which("ffmpeg") or os.environ.get("FFMPEG", "ffmpeg")
FFPROBE = shutil.which("ffprobe") or os.environ.get("FFPROBE", "ffprobe")
COMFYUI_URL = os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188")
OUTPUT_ROOT = os.environ.get("OUTPUT_DIR", os.path.join(COMFYUI_ROOT, "output"))
# Templates ship in this repo at <repo>/templates/, not under scripts/
TEMPLATE_APG = os.path.join(REPO_ROOT, "templates", "ace_step_music_apg_api.json")
TEMPLATE_SIMPLE = os.path.join(REPO_ROOT, "templates", "ace_step_music_simple_api.json")

# Mastering module lives next to this script in aeon-music-maker/scripts/.
# Import is optional — if missing, we skip mastering and just output the raw track.
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
try:
    import music_mastering as _mm
    MASTERING_AVAILABLE = True
except Exception as _e:
    _mm = None
    MASTERING_AVAILABLE = False
    _MASTERING_IMPORT_ERROR = str(_e)

# Variant → (unet, steps, cfg, sampler, scheduler, shift, weight_dtype, use_apg)
# APG params (eta=0.7, norm_threshold=2.5, momentum=-0.75) are fixed in the template
# and only applied when use_apg=True.
VARIANTS = {
    "xl_base":     ("acestep_v1.5_xl_base.safetensors",                  50, 7.0, "gradient_estimation", "simple", 3.0, "default", True),
    "xl_sft":      ("acestep_v1.5_xl_sft_bf16.safetensors",              45, 6.0, "gradient_estimation", "simple", 3.0, "default", True),
    "xl_base_sft": ("acestep_v1.5_xl_merge_base_sft_ta_0.5.safetensors", 35, 3.0, "euler",               "simple", 3.0, "default", False),
    "xl_turbo":    ("acestep_v1.5_xl_turbo_bf16.safetensors",            10, 1.0, "euler",               "simple", 3.0, "default", False),
    "base_turbo":  ("acestep_v1.5_turbo.safetensors",                     8, 1.0, "euler",               "simple", 3.0, "default", False),
}

DEFAULT_VARIANT = "xl_base"


def comfy_request(path, data=None, timeout=30):
    url = f"{COMFYUI_URL}{path}"
    if data is not None:
        req = urllib.request.Request(url, data=json.dumps(data).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
    else:
        req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


# Submit retry — absorbs transient failures (400s on concurrent model loads,
# HTTP 5xx during restart-settling, connection resets from brief network blips).
# Backoff schedule: 2 s, 5 s, 10 s — covers the typical 5-15 s recovery window
# for ComfyUI to settle after a custom-node registration or model cache refresh.
SUBMIT_RETRY_DELAYS_S = (2, 5, 10)


def _submit_prompt(wf, client_id, attempts=None):
    """Submit a workflow to /prompt with bounded retries on transient errors.

    Retries on: HTTP 400/409/5xx, connection reset/refused, read timeout.
    Does NOT retry on: 404 (endpoint missing), bad JSON (caller's fault),
    {"node_errors": {...}} with entries (workflow invalid — retry won't help).
    """
    delays = list(SUBMIT_RETRY_DELAYS_S if attempts is None else attempts)
    last_exc = None
    for i in range(len(delays) + 1):
        try:
            res = comfy_request("/prompt", {"prompt": wf, "client_id": client_id})
            # ComfyUI returns 200 with {"node_errors": {...}} for workflow-invalid.
            # Non-empty node_errors means the workflow is broken — not transient.
            node_errors = res.get("node_errors") or {}
            if node_errors:
                raise RuntimeError(f"ComfyUI rejected workflow: {list(node_errors)[:3]}")
            pid = res.get("prompt_id")
            if not pid:
                raise RuntimeError(f"Submit succeeded but no prompt_id in response: {res}")
            if i > 0:
                print(f"    submit succeeded after {i} retr{'y' if i == 1 else 'ies'}")
            return pid
        except urllib.error.HTTPError as e:
            last_exc = e
            # Non-transient: 404 (missing endpoint), 413 (too large)
            if e.code in (404, 413):
                raise
            # Transient: 400/408/409/429/5xx
            if i < len(delays):
                body = e.read().decode("utf-8", errors="replace")[:200] if hasattr(e, "read") else ""
                print(f"    submit HTTP {e.code} ({e.reason}) — retrying in {delays[i]}s… {body}")
                time.sleep(delays[i])
            else:
                raise
        except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
            last_exc = e
            if i < len(delays):
                print(f"    submit connection error ({e}) — retrying in {delays[i]}s…")
                time.sleep(delays[i])
            else:
                raise
    raise RuntimeError(f"submit_prompt exhausted retries: {last_exc}")


def submit_and_wait(wf, client_id, poll_timeout=1800, poll_every=3):
    pid = _submit_prompt(wf, client_id)
    start = time.time()
    while time.time() - start < poll_timeout:
        h = comfy_request(f"/history/{pid}")
        if pid in h:
            return h[pid], pid
        time.sleep(poll_every)
    raise TimeoutError(f"{pid} timed out after {poll_timeout}s")


def build_apg_workflow(tags, lyrics, duration, bpm, keyscale, seed,
                        variant, filename_prefix, steps_ovr=None, cfg_ovr=None):
    """Build the high-fidelity APG workflow (for xl_base / xl_sft)."""
    with open(TEMPLATE_APG) as f:
        wf = json.load(f)
    # Strip the _comment key
    wf.pop("_comment", None)

    unet, p_steps, p_cfg, sampler, scheduler, shift, dtype, _ = VARIANTS[variant]
    steps = int(steps_ovr) if steps_ovr is not None else p_steps
    cfg = float(cfg_ovr) if cfg_ovr is not None else p_cfg

    # UNet
    wf["100"]["inputs"]["unet_name"] = unet
    wf["100"]["inputs"]["weight_dtype"] = dtype
    # ModelSamplingAuraFlow shift
    wf["110"]["inputs"]["shift"] = shift
    # Text encoder — tags/lyrics/duration/bpm/key
    wf["120"]["inputs"].update({
        "tags": tags, "lyrics": lyrics or "[Instrumental]", "seed": seed,
        "bpm": int(bpm), "duration": float(duration),
        "keyscale": keyscale,
    })
    # Empty latent duration
    wf["130"]["inputs"]["seconds"] = float(duration)
    # CFGGuider cfg
    wf["140"]["inputs"]["cfg"] = cfg
    # Sampler select
    wf["141"]["inputs"]["sampler_name"] = sampler
    # Basic scheduler
    wf["142"]["inputs"]["scheduler"] = scheduler
    wf["142"]["inputs"]["steps"] = steps
    # RandomNoise
    wf["143"]["inputs"]["noise_seed"] = seed
    # Output
    wf["170"]["inputs"]["filename_prefix"] = filename_prefix
    return wf


def build_simple_workflow(tags, lyrics, duration, bpm, keyscale, seed,
                           variant, filename_prefix, steps_ovr=None, cfg_ovr=None):
    """Build the simple-KSampler workflow (for turbo variants + xl_base_sft).

    Identical pattern to scene_production_tool/radio_drama.py's build_ace_workflow().
    """
    with open(TEMPLATE_SIMPLE) as f:
        wf = json.load(f)

    unet, p_steps, p_cfg, sampler, scheduler, shift, dtype, _ = VARIANTS[variant]
    steps = int(steps_ovr) if steps_ovr is not None else p_steps
    cfg = float(cfg_ovr) if cfg_ovr is not None else p_cfg

    wf["104"]["inputs"].update({"unet_name": unet, "weight_dtype": dtype})
    wf["78"]["inputs"]["shift"] = shift
    wf["94"]["inputs"].update({
        "tags": tags, "lyrics": lyrics or "[Instrumental]", "seed": seed,
        "bpm": int(bpm), "duration": float(duration),
        "timesignature": "4", "language": "en", "keyscale": keyscale,
    })
    wf["3"]["inputs"].update({
        "seed": seed, "steps": steps, "cfg": cfg,
        "sampler_name": sampler, "scheduler": scheduler,
    })
    wf["98"]["inputs"]["seconds"] = float(duration)
    wf["107"]["inputs"]["filename_prefix"] = filename_prefix
    return wf


def build_workflow(tags, lyrics, duration, bpm, keyscale, seed,
                   variant, filename_prefix, steps_ovr=None, cfg_ovr=None):
    """Dispatch to APG or simple workflow based on the variant."""
    if variant not in VARIANTS:
        raise ValueError(f"Unknown variant '{variant}'. Choices: {list(VARIANTS)}")
    use_apg = VARIANTS[variant][7]
    builder = build_apg_workflow if use_apg else build_simple_workflow
    return builder(tags, lyrics, duration, bpm, keyscale, seed,
                   variant, filename_prefix, steps_ovr, cfg_ovr)


def transcode_output(comfyui_output_path, target_path):
    """Re-encode ComfyUI's output to the caller's requested format.

    APG template writes FLAC (SaveAudio); simple template writes MP3 (SaveAudioMP3).
    We transcode to the target extension without quality loss where possible.
    """
    ext = os.path.splitext(target_path)[1].lower()
    os.makedirs(os.path.dirname(target_path) or ".", exist_ok=True)

    if ext == ".flac":
        # FLAC is lossless; copy if source is already FLAC, else transcode
        if comfyui_output_path.lower().endswith(".flac"):
            shutil.copy2(comfyui_output_path, target_path)
        else:
            subprocess.run([FFMPEG, "-y", "-i", comfyui_output_path,
                "-c:a", "flac", "-compression_level", "8", target_path],
                check=True, capture_output=True)
    elif ext == ".wav":
        subprocess.run([FFMPEG, "-y", "-i", comfyui_output_path,
            "-c:a", "pcm_s24le", "-ar", "48000", target_path],
            check=True, capture_output=True)
    elif ext == ".mp3":
        if comfyui_output_path.lower().endswith(".mp3"):
            shutil.copy2(comfyui_output_path, target_path)
        else:
            subprocess.run([FFMPEG, "-y", "-i", comfyui_output_path,
                "-c:a", "libmp3lame", "-q:a", "0", target_path],
                check=True, capture_output=True)
    else:
        shutil.copy2(comfyui_output_path, target_path)
    return target_path


def load_lyrics(arg):
    """Accept either literal lyrics text or a path to a .txt file."""
    if not arg:
        return ""
    if os.path.exists(arg):
        with open(arg, encoding="utf-8") as f:
            return f.read().strip()
    return arg


def auto_detect_preset(prompt, lyrics=""):
    """Pick a mastering preset from genre keywords in the prompt/lyrics.

    Returns one of: edm, trap, chill, orchestral, jazz, default.
    Ordering matters — more specific matches first.
    """
    text = (prompt + " " + lyrics).lower()
    # Orchestral / cinematic
    if any(k in text for k in ("orchestr", "symphon", "classical", "film score",
                                "cinematic", "epic score", "score,", "string section")):
        return "orchestral"
    # Jazz family
    if any(k in text for k in ("jazz", "bebop", "bossa", "swing", "smooth jazz",
                                "rhodes", "upright bass", "walking bass")):
        return "jazz"
    # EDM / dance family FIRST (covers dubstep, dnb, trance, psy — catch-all for
    # high-energy electronic including tracks that may also mention 808s).
    if any(k in text for k in ("edm", "dubstep", "drum and bass", "dnb", "drum n bass",
                                "trance", "techno", "house,", "house ", "house.",
                                "psychedelic", "psytrance", "future bass",
                                "electronic dance", "dmt", "rave", "festival",
                                "acid house", "glitch hop", "electro")):
        return "edm"
    # Trap / hiphop (only if no EDM keywords matched — these are pure rap/trap idioms)
    if any(k in text for k in ("trap beat", "drill", "hiphop", "hip-hop", "hip hop",
                                "boom bap", "rap,", "rap ", "mumble rap",
                                "trap,", "trap ", "808 bass", "808,")):
        return "trap"
    # Chill / ambient / lofi
    if any(k in text for k in ("lofi", "lo-fi", "ambient", "chillhop", "chillwave",
                                "downtempo", "relax", "sleep music", "meditat")):
        return "chill"
    return "default"


def normalize_key(key):
    """Accept musical flat/sharp unicode and convert to ACE-compatible ASCII.

    B♭ major → Bb major, F♯ minor → F# minor. ACE Step's keyscale enum uses
    plain ASCII; unicode accidentals cause a 400 Bad Request."""
    if not key:
        return "A minor"
    return (key.replace("\u266d", "b")   # ♭ flat
               .replace("\u266f", "#")   # ♯ sharp
               .replace("\u2dd0", "b")   # rare fallback
               .strip())


def main():
    p = argparse.ArgumentParser(description="ACE Step music generator (maximum-fidelity APG chain)")
    p.add_argument("--prompt", "--tags", required=True,
                   help="Comma-separated music descriptors (genre, instruments, mood, production)")
    p.add_argument("--duration", type=float, default=120.0,
                   help="Track length in seconds (ACE Step 1.5 supports up to ~240)")
    p.add_argument("--bpm", type=int, default=75)
    p.add_argument("--key", default="A minor",
                   help="e.g. 'C major', 'E minor', 'F# major'")
    p.add_argument("--lyrics", default="",
                   help="Literal lyrics string OR path to a .txt file. Empty = instrumental.")
    p.add_argument("--variant", default=DEFAULT_VARIANT, choices=list(VARIANTS),
                   help=f"Quality/speed preset (default: {DEFAULT_VARIANT}, max-fidelity)")
    p.add_argument("--steps", type=int, default=None, help="Override preset step count")
    p.add_argument("--cfg", type=float, default=None, help="Override preset CFG")
    p.add_argument("--seed", type=int, default=None, help="Fixed seed for reproducibility")
    p.add_argument("--output", "-o", default=None,
                   help="Output path (.flac/.wav/.mp3). Default: output/music/<slug>.flac")
    # Mastering flags (post-gen dynamics-preserving chain)
    p.add_argument("--master", choices=["auto", "off", "default", "edm", "trap",
                                         "chill", "orchestral", "jazz"],
                   default="auto",
                   help="Mastering preset after generation. 'auto' = pick from prompt "
                        "keywords, 'off' = raw ACE output, else a named preset. "
                        "Default: auto (recommended).")
    p.add_argument("--target-lufs", type=float, default=None,
                   help="Override preset's target LUFS. EDM/trap≈-12, default≈-14, "
                        "jazz≈-15, chill≈-16, orchestral≈-18.")
    p.add_argument("--keep-raw", action="store_true",
                   help="Keep the pre-mastered file alongside the mastered output "
                        "(at <output>.raw.<ext>).")
    args = p.parse_args()

    lyrics = load_lyrics(args.lyrics)
    args.key = normalize_key(args.key)
    seed = args.seed if args.seed is not None else random.randint(0, 2**31 - 1)

    # Default output path under output/music/
    if args.output:
        out_path = os.path.abspath(args.output)
    else:
        slug = "".join(c if c.isalnum() else "_" for c in args.prompt.lower())[:48].strip("_")
        out_path = os.path.join(OUTPUT_ROOT, "music", f"{slug}_{seed}.flac")

    # Build a ComfyUI-internal filename prefix (relative to output/)
    internal_prefix = f"music_maker/{os.path.splitext(os.path.basename(out_path))[0]}"

    wf = build_workflow(
        tags=args.prompt, lyrics=lyrics, duration=args.duration,
        bpm=args.bpm, keyscale=args.key, seed=seed,
        variant=args.variant, filename_prefix=internal_prefix,
        steps_ovr=args.steps, cfg_ovr=args.cfg,
    )

    unet, steps, cfg, sampler, scheduler, shift, dtype, use_apg = VARIANTS[args.variant]
    final_steps = args.steps if args.steps is not None else steps
    final_cfg = args.cfg if args.cfg is not None else cfg
    chain = "APG + SamplerCustomAdvanced" if use_apg else "simple KSampler"
    print(f"=== Music Maker ===")
    print(f"  variant:  {args.variant}  ({chain})")
    print(f"  model:    {unet}")
    print(f"  sampler:  {sampler} / {scheduler} / {final_steps} steps / CFG {final_cfg} / shift {shift}")
    print(f"  duration: {args.duration:.1f}s  |  {args.bpm} BPM  |  {args.key}")
    print(f"  seed:     {seed}")
    print(f"  lyrics:   {'yes (' + str(len(lyrics)) + ' chars)' if lyrics else 'instrumental'}")
    print(f"  prompt:   {args.prompt[:80]}{'...' if len(args.prompt) > 80 else ''}")
    print(f"  output:   {out_path}")
    print()
    print("generating...", flush=True)

    t0 = time.time()
    # xl_base at 50 steps for 4+ minutes of audio could be 2-3 min wall time, give headroom
    poll_timeout = 3600 if use_apg else 1200
    result, pid = submit_and_wait(wf, f"music-maker-{seed}", poll_timeout=poll_timeout)
    elapsed = time.time() - t0

    status = result.get("status", {}).get("status_str")
    if status != "success":
        print(f"FAILED: {status}")
        for m in result.get("status", {}).get("messages", [])[-8:]:
            print(f"  {str(m)[:400]}")
        sys.exit(1)

    # Find ComfyUI's output file
    src = None
    for v in result.get("outputs", {}).values():
        for a in v.get("audio", []):
            p = os.path.join(OUTPUT_ROOT, a.get("subfolder", ""), a["filename"])
            if os.path.exists(p):
                src = p; break
        if src: break
    if not src:
        print("ERROR: no output file found in ComfyUI history")
        sys.exit(1)

    # Transcode to requested format
    # If mastering is active, produce a raw file first, then master to the final path.
    master_mode = args.master
    if master_mode == "auto":
        master_mode = auto_detect_preset(args.prompt, lyrics) if MASTERING_AVAILABLE else "off"

    if master_mode != "off" and MASTERING_AVAILABLE:
        # Stage the raw file next to the final
        stem, ext = os.path.splitext(out_path)
        raw_path = f"{stem}.raw{ext}"
        transcode_output(src, raw_path)
        print(f"\n=== Mastering (preset='{master_mode}') ===")
        mr = _mm.master_track(raw_path, out_path, preset_name=master_mode,
                              target_lufs=args.target_lufs, verbose=True)
        if not args.keep_raw:
            try:
                os.remove(raw_path)
            except Exception:
                pass
        final = out_path
    else:
        if master_mode != "off" and not MASTERING_AVAILABLE:
            print(f"\n[WARN] mastering requested but module unavailable: "
                  f"{_MASTERING_IMPORT_ERROR}. Outputting raw track.")
        final = transcode_output(src, out_path)

    size_mb = os.path.getsize(final) / 1024 / 1024

    # Probe for reporting
    r = subprocess.run([FFPROBE, "-v", "error", "-select_streams", "a:0",
        "-show_entries", "stream=codec_name,sample_rate,channels:format=duration",
        "-of", "default=nw=1", final], capture_output=True, text=True)

    print(f"\ngenerated in {elapsed:.0f}s  ({args.duration/elapsed:.2f}x real-time)")
    print(f"track:  {final}  ({size_mb:.2f} MB)")
    print(f"probe:  {r.stdout.strip().replace(chr(10), ' | ')}")
    print(f"seed:   {seed}  (save this if you want the exact same track again)")
    if master_mode != "off" and MASTERING_AVAILABLE:
        print(f"master: preset='{master_mode}'"
              f"{f', target_lufs={args.target_lufs}' if args.target_lufs is not None else ''}")


if __name__ == "__main__":
    main()
