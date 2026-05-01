---
name: music-producer
description: >
  Generate standalone music tracks (songs, instrumentals, cues) at maximum audio fidelity using
  ACE Step 1.5 XL on the Workstation workstation. USE THIS SKILL when the user asks to make a music
  track, song, instrumental, beat, album cut, demo, jingle, score cue, or any standalone audio
  deliverable where music quality is the primary concern (not background bed for a radio drama
  or video). Triggers on: "make a song", "generate music", "create a track", "music in the style
  of X", "instrumental", "lofi / jazz / classical / ambient / rock / etc. track", "album", "demo",
  "jingle", "music cue", "original song". This is DISTINCT from the radio-drama-production skill,
  which uses a faster "good enough" music pipeline optimized for dialogue beds. This skill uses
  the full APG + SamplerCustomAdvanced chain with the 20GB fp32 XL base model for the highest
  possible audio integrity — lossless FLAC 48kHz stereo output.
---

# Music Producer — ACE Step 1.5 XL, maximum fidelity

Generate **standalone music tracks** at the highest audio quality the system is capable of. For radio-drama music beds (fast, "good enough"), use the `radio-drama-production` skill instead; this one exists for tracks where the audio is the deliverable.

## 0. Target host + tool

- **Host:** `${SSH_USER}@127.0.0.1` (Workstation — RTX 5090, 64 GB RAM, Win 11 + OpenSSH)
- **Tool:** `${COMFYUI_ROOT}\music_tool\music_maker.py`
- **Templates:** `music_tool\templates\ace_step_music_apg_api.json` (APG chain) + `ace_step_music_simple_api.json` (simple KSampler)
- **ComfyUI endpoint on Workstation:** `http://127.0.0.1:8188`

## 1. Why a dedicated tool

`scene_production_tool/radio_drama.py` uses a simple `KSampler` template tuned for turbo variants — fast, clean enough to sit under dialogue, but the ceiling is the `xl_base_sft` merged model at CFG 3. The APG-requiring base models (`xl_base` fp32, `xl_sft` bf16) **distort audibly** under that template because ACE Step's full base models need `SamplerCustomAdvanced + APG + CFGGuider` to avoid artifacts (per NerdyRodent's v35 reference workflow and Stability's training notes).

`music_maker.py` here uses the **proper APG chain** for `xl_base` / `xl_sft`, producing clean output at true base-model quality. It also defaults to **lossless FLAC** output (48 kHz stereo), unlike the radio-drama pipeline which writes MP3 V0.

## 2. Variants — pick by quality/speed tradeoff

| Variant | UNet | Chain | Steps | CFG | Time (per 90 s) | Best for |
|---|---|---|---|---|---|---|
| **`xl_base`** (default) | acestep_v1.5_xl_base.safetensors (19.95 GB fp32) | APG | 50 | 7.0 | ~21 s | **Album masters, standalone songs, hero cues** |
| `xl_sft` | acestep_v1.5_xl_sft_bf16.safetensors | APG | 45 | 6.0 | ~18 s | Near-base quality, faster, bf16 |
| `xl_base_sft` | acestep_v1.5_xl_merge_base_sft_ta_0.5.safetensors | simple KSampler | 35 | 3.0 | ~21 s | Balance (shared default with radio-drama) |
| `xl_turbo` | acestep_v1.5_xl_turbo_bf16.safetensors | simple KSampler | 10 | 1.0 | ~12 s | Preview iterations, fast A/B |
| `base_turbo` | acestep_v1.5_turbo.safetensors (4.8 GB) | simple KSampler | 8 | 1.0 | ~8 s | Smallest/fastest, lowest quality |

**APG variants** use `SamplerCustomAdvanced` with:
- `APG(eta=0.7, norm_threshold=2.5, momentum=-0.75)` (v35 params)
- `CFGGuider(cfg=per-variant)`
- `KSamplerSelect("gradient_estimation")`
- `BasicScheduler("simple", steps, denoise=1.0)`
- `ModelSamplingAuraFlow(shift=3)`
- `RandomNoise(seed)`

**Simple variants** use a straight `KSampler` with `euler` / `simple` — works because those models are distilled (turbo) or merged (base+SFT).

## 3. Quick-start

Three ways to invoke from anywhere:

### Direct SSH one-liner

```bash
ssh ${SSH_USER}@127.0.0.1 'cd ${COMFYUI_ROOT} && python music_tool\music_maker.py --prompt "lofi jazz, warm Rhodes, soft saxophone, brushed drums, vinyl crackle" --duration 180 --bpm 78 --key "A minor"'
```

### From a sidecar script (recommended for longer tracks)

```bash
ssh ${SSH_USER}@127.0.0.1 'start /B python ${COMFYUI_ROOT}\music_tool\music_maker.py --prompt "..." --duration 240 --variant xl_base > ${USER_HOME}\music_maker_run.log 2>&1'
ssh ${SSH_USER}@127.0.0.1 'powershell -Command "Get-Content ${USER_HOME}\music_maker_run.log -Wait -Tail 10"'
```

### Pull the result

```bash
scp ${SSH_USER}@127.0.0.1:${COMFYUI_ROOT}/output/music/lofi_jazz_*.flac .
```

## 4. Argument reference

```
python music_maker.py [options]

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
                          output/music/<slug>_<seed>.flac
```

## 5. Writing good prompts

ACE Step understands music the way image models understand art — the prompt is a **cloud of descriptors**, not a sentence. Pile on comma-separated tags across four categories:

### Genre + subgenre

```
lofi jazz / jazz fusion / bossa nova / swing / cool jazz / bebop
ambient drone / cinematic ambient / dark ambient / space music
lofi hiphop / boom bap / trip hop / chillhop / study beats
neo-soul / R&B / funk / gospel
classical / chamber / string quartet / solo piano / minimalist / romantic
cinematic orchestral / film score / epic trailer / horror score / ghibli-style
indie rock / shoegaze / post-rock / dream pop / synthwave / vaporwave
electronic / IDM / techno / house / drum and bass / ambient techno
world / flamenco / tango / celtic / middle eastern / afrobeat / reggae
```

### Instruments (more specific = better)

```
warm Rhodes piano, muted saxophone, brushed jazz drums,
upright bass walking line, vibraphone, muted trumpet,
Fender Rhodes, clean Stratocaster, nylon-string guitar,
Moog bass, analog synth pad, mellotron strings,
violin section, cello, timpani, woodwinds,
hand drums, sitar, oud, didgeridoo, koto
```

### Production / mix character

```
vinyl crackle, tape hiss, analog warmth, lo-fi compression,
big reverb, long delay, spring reverb, plate reverb,
close-mic'd, room ambience, field recording,
dry and intimate, lush and wide, spectral shimmer,
sidechained pump, pumping kick, saturated bass
```

### Mood / setting

```
nocturnal, rainy window, coffee shop, late-night drive,
contemplative, melancholic, uplifting, triumphant, dark foreboding,
urgent, tense, calm and measured, reverent, sacred,
morning coffee, sunrise, sunset, winter, summer, desert, forest
```

### Rhythm / groove cues (reinforces BPM)

```
relaxed 4/4 swing, boom-bap groove, head-nod groove,
samba syncopation, waltz 3/4, odd meter 7/8,
driving straight 8ths, laid back behind the beat
```

### Full example prompt

```
lofi jazz, mellow hip hop beat, warm Rhodes piano, soft muted saxophone,
brushed jazz drums, upright bass walking line, vinyl crackle,
rainy window atmosphere, nocturnal, study beats, relaxed 4/4 swing
```

### Anti-patterns

- ❌ Full sentences ("A beautiful jazz song with piano") — ACE expects tags, not prose
- ❌ Requesting specific artists ("in the style of Miles Davis") — might hint but not reliable
- ❌ Contradictory tags ("aggressive peaceful / loud quiet") — model averages to mush
- ❌ Song-structure prose ("verse 1 goes like...") — use the `--lyrics` arg for vocals

### Writing for dynamics, feel, and punch

**If your tracks sound flat / same-level / lifeless, the prompt is usually why.** ACE Step mirrors the energy envelope of its tags. A "wall of sound" prompt produces a wall-of-sound track — no peaks, no valleys, no feel.

**Words that CREATE dynamics (use these):**

```
punchy, snappy, transient-rich, kick-forward, staccato, percussive,
breathy, restrained, sparse, minimal, space between notes,
quiet intro, slow build, drops to silence, sudden hit,
accent on the one, ghost note, syncopated, rhythmic tension,
call and response, rest, pause, breathing room,
rises and falls, crescendo, decrescendo, swell, taper,
loud-quiet-loud dynamics, cinematic dynamics,
sidechain pump, ducking, gated, stabbed, plucked, stabs,
muted, then big, whispered then roared
```

**Words that KILL dynamics (avoid or use sparingly):**

```
wall of sound, dense mix, thick, maximal, lush full arrangement,
constant energy, always moving, never stops, saturated everything,
massive, huge, overwhelming, pounding nonstop,
layered and layered, everything at once,
compressed to the max, radio-ready loud  ← asks the model to pre-compress
```

**Structural cues (for lyrics or instrumental builds):**

```
[verse: hushed]    [chorus: full]    [breakdown: drums only]
[drop]             [build]            [silence]
[intro: solo piano]   [outro: solo cello, sparse]
```

**Tempo + dynamics:** slower tempos (60–90 BPM) naturally have more room for dynamics than fast ones (140+). If a genre is dense and fast by default (dubstep, drum-and-bass), insert explicit dynamic cues ("drop to solo bass, silence, then full drop", "pause at bar 16") to force contrast.

**Diagnostic: measure your output.** After `--master auto` the tool prints LUFS / TP / LRA / DR / crest before and after. Targets for a track that has "feeling":
| Metric | Flat (bad) | Good | Wide (excellent) |
|---|---|---|---|
| **LRA** | < 3 LU | 5–8 LU | 10+ LU (classical territory) |
| **DR** | < 8 dB | 15–25 dB | 30+ dB |
| **Crest** | < 4 | 5–8 | 9+ |

LRA of 1.8 means your track is squashed flat. LRA of 6–8 is what pop/EDM typically ships at. LRA of 20+ is cinematic/classical.

## 6. Lyrics (vocal songs)

ACE Step is one of the few audio models that **sings**. Pass lyrics either inline:

```bash
python music_maker.py --prompt "indie folk, acoustic guitar, soft vocals, melancholic" \
  --lyrics "[verse]
The road was long, the night was colder
The stars were hidden in the rain
I walked along with only shadows
Listening for your voice in vain
[chorus]
Find me, find me, in the morning
When the sun breaks through again..." \
  --duration 180 --bpm 90 --key "D minor"
```

Or from a file:

```bash
python music_maker.py --prompt "..." --lyrics ./lyrics/my_song.txt --duration 240
```

### Lyrics syntax

ACE Step respects **structural tags** in square brackets. Use these to guide the model:

```
[intro]            instrumental intro, no vocals
[verse]            verse vocals
[chorus]           chorus — typically higher energy, repeated hook
[pre-chorus]       build-up lines before the chorus
[bridge]           contrasting section
[outro]            instrumental outro
[instrumental]    skip vocals for this section
[solo: saxophone]  instrumental solo on the named instrument
[hook]             catchy short phrase
[break]            brief silence or drum-only
```

Keep lines short (4–8 words) and meter-consistent within sections. ACE handles English best; other languages via the `language` field in the text encoder (not yet exposed as a CLI flag — edit the template if you need that).

## 7. Key and tempo guide

| Genre | Typical BPM | Typical keys |
|---|---|---|
| Lofi hiphop / study beats | 70–90 | A minor, D minor, E minor |
| Jazz / bossa nova | 80–140 | any — major for upbeat, minor for ballad |
| Ambient / drone | 60–70 or n/a | E minor, A minor, D minor (modal) |
| Classical / chamber | varies | full chromatic range |
| Cinematic orchestral | 60–100 hero, 120–160 action | D minor (dread), E♭ major (hero), C minor (tragedy) |
| Neo-soul / R&B | 70–95 | any — minor keys + 7ths for color |
| Indie / alt rock | 100–130 | E minor / G major / D major |
| EDM / techno | 120–135 | any |
| Dnb / jungle | 160–175 | minor keys |

Valid keyscales: `"C major"`, `"C minor"`, `"C# major"`, `"C# minor"`, ... through the full chromatic range + all major/minor pairs. ACE accepts modal hints too (e.g. `"A dorian"`, `"E phrygian"`) but fidelity to mode is best-effort.

## 8. Output formats

The tool's output is determined by the `--output` extension:

- **`.flac`** (default) — lossless, 48 kHz stereo, typical 6–10 MB / 90 s. **Use for masters.**
- **`.wav`** — 48 kHz pcm_s24le (24-bit), larger files, no quality difference from FLAC, useful for DAW import without re-encoding.
- **`.mp3`** — libmp3lame at `-q:a 0` (highest VBR, ~245 kbps typical). **Use for delivery / sharing.**

FLAC is the right default. The model's native output is 48 kHz stereo; FLAC captures that losslessly.

## 9. Reproducibility + iteration workflows

Every run prints the seed used. **Save it** — rerunning with the same `--prompt` + `--seed` + `--variant` gives you the exact same track, bit-for-bit, even weeks later. This is how you:

- Iterate on a loved draft (same seed, tweak one tag)
- Bounce multiple mixes (same seed, different variant)
- Generate stems (same seed, sequential prompts emphasizing different instruments)

```bash
# You loved this one; now try a version with stronger sax
python music_maker.py --prompt "lofi jazz, warm Rhodes, PROMINENT soft saxophone, brushed drums..." \
  --seed 1210744748 --duration 90 --bpm 78 --key "A minor"
```

### Mastering-preset A/B on the same generation

When you have a great draft and want to hear it through two different mastering chains without re-generating the 2-3 minute track, use `--keep-raw` to stash the pre-master:

```bash
# First pass: generate + master with auto-detect
python music_maker.py --prompt "..." --seed 259461068 --duration 150 --keep-raw -o track.flac
# → produces track.flac (mastered) + track.raw.flac (pre-master)

# Second pass: re-master the raw with a different preset
python scene_production_tool/music_mastering.py track.raw.flac --preset edm -o track_edm.flac
python scene_production_tool/music_mastering.py track.raw.flac --preset default --target-lufs -14 -o track_hifi.flac
python scene_production_tool/music_mastering.py track.raw.flac --preset orchestral -o track_transparent.flac

# Compare all three side by side
```

This is the fastest way to find the right sonic character for a track: generate once, master many.

### Sweep seeds cheaply, master the winner

When a prompt might go many different directions, do a fast preview sweep with `xl_turbo --master off`, pick the best seed, then re-generate at xl_base quality with mastering on:

```bash
# Sweep 5 seeds at turbo speed, raw output (no mastering yet)
for i in 1 2 3 4 5; do
  python music_maker.py --prompt "..." --duration 30 --variant xl_turbo --master off \
    --output "preview_${i}.flac" --seed $RANDOM
done
# Pick the one you like, note its seed, then:
python music_maker.py --prompt "..." --duration 180 --variant xl_base --seed <winning_seed>
```

### Remaster an existing track in-place

```bash
# If you already have a .flac from a previous run and want to try the mastering chain:
python scene_production_tool/music_mastering.py \
  output/music/some_older_track.flac --preset jazz \
  --output output/music/some_older_track_mastered.flac
```

## 9b. Diagnosing a flat-sounding track

If a rendered track feels lifeless, the `--master auto` run prints before/after LRA / DR / crest. Decision tree:

```
LRA (raw) < 3.0 LU?
├── YES → the GENERATOR produced a flat track. Mastering can't fix this.
│         FIX: rewrite prompt with dynamics vocabulary (section 5).
│         Add [intro: sparse] / [drop] / [breakdown] structural cues.
│         Drop dynamics-killing words ("wall of sound", "dense", "massive").
│
└── NO (LRA > 3.0) → generator is fine.
    └── LRA (after) << LRA (before)?
        ├── YES → mastering chain is compressing too hard.
        │         CHECK: did you force a preset that adds a Compressor?
        │         (Default presets have NO compressor; only `use_compressor: True`
        │         presets compress. None of the named presets set this.)
        │
        └── NO → dynamics intact. If track still feels "dull":
                 - Check saturation_db in preset (raise for more color)
                 - Check presence_db / high_shelf_db (raise for more clarity)
                 - Try a different preset: chill → default → edm (ascending color)
```

**Rule of thumb target LRA by genre:**

| Style | Target LRA |
|---|---|
| Pop / commercial EDM | 5–8 LU |
| Hip-hop / trap | 4–7 LU |
| Rock / indie | 6–10 LU |
| Jazz | 8–14 LU |
| Film score / cinematic | 12–20 LU |
| Classical | 15–25 LU |

If your prompt is for "cinematic orchestral" and the track measures LRA 4, the prompt lost the fight — rewrite to emphasize dynamics (section 5).

## 10. Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Distorted / tinny / hollow audio | You're using simple KSampler with `xl_base` or `xl_sft` via a non-APG template | Use `music_maker.py` (this tool), NOT `radio_drama.py --stage music` — this one uses APG |
| Truncated audio | `--duration` > ~240 s exceeds model coherence window | Split into 2–3 tracks, crossfade in DAW |
| Lyrics not sung | Model ignored the lyrics tag | Ensure the `--lyrics` arg is set and the prompt includes vocal tags ("soft vocals", "sung", "male/female voice") |
| Timing wrong for BPM | Prompt contradicts `--bpm` (e.g. BPM 80 but tags say "uptempo") | Either tighten tags or change `--bpm` to match |
| `GatedRepoError` or missing model | Model file not on disk | Confirm with `ssh ${SSH_USER}@127.0.0.1 'dir ${COMFYUI_ROOT}\models\diffusion_models\acestep_*'` |
| Out-of-memory | Happens occasionally with `xl_base` fp32 + long durations + concurrent ComfyUI work | Set `--variant xl_sft` (bf16, ~10 GB), or wait for other jobs to finish |
| `[Errno 22]` on ComfyUI load | Windows mmap bug | Verify `comfy/utils.py` line 41 is `DISABLE_MMAP = True` on Workstation |

## 11. Recipes

### Lofi jazz bed (a solid starting point)

```bash
python music_maker.py \
  --prompt "lofi jazz, mellow hip hop beat, warm Rhodes piano, soft muted saxophone, brushed jazz drums, upright bass walking line, vinyl crackle, rainy window atmosphere, nocturnal, study beats, relaxed 4/4 swing" \
  --duration 180 --bpm 78 --key "A minor" --variant xl_base
```

### Cinematic hero cue (for a trailer)

```bash
python music_maker.py \
  --prompt "cinematic orchestral, epic trailer, powerful strings rising, heroic horns, thunderous timpani, choir swell, uplifting resolution, dolby atmos wide" \
  --duration 90 --bpm 100 --key "E♭ major" --variant xl_base --cfg 8.0
```

### Dark ambient drone (atmosphere bed)

```bash
python music_maker.py \
  --prompt "dark ambient drone, sub bass sustain, granular synthesis pad, distant wind chimes, long reverb tail, cave-like space, slow evolving, no rhythm" \
  --duration 240 --bpm 60 --key "D minor" --variant xl_base --steps 70
```

### Indie folk demo with lyrics

```bash
python music_maker.py \
  --prompt "indie folk, intimate acoustic guitar fingerpicking, soft female vocals, close-mic'd, cold morning, minimal reverb" \
  --lyrics "[verse]
I left my heart up on the ridge
Between the pine and snow
You said you'd come and find me there
But winter just would not let go
[chorus]
Find me, find me, find me before the thaw
Where the silence holds the note" \
  --duration 160 --bpm 88 --key "G major" --variant xl_base
```

### Preview iteration (fast, disposable)

```bash
python music_maker.py --prompt "..." --duration 30 --variant xl_turbo
```

## 12. Mastering — post-generation dynamics-preserving chain

Raw ACE output benefits from a quick mastering pass: subtle EQ for presence and air, whisper of tape warmth, gain-match to a sensible LUFS target, and a safety ceiling to catch stray peaks. The tool does this automatically unless you opt out.

### What's in the chain

```
raw.flac
  |
  |-- HighpassFilter(20–30 Hz)      remove sub-rumble
  |-- LowShelf(-1 dB @ 150–200 Hz)  tame mud
  |-- PeakFilter(+1..2 dB @ 2.5–4.5 kHz, Q 0.6–0.9)  presence
  |-- HighShelf(+1.5..3 dB @ 10–13 kHz)              air
  |-- Distortion(0..4 dB)           light tape warmth (skipped at 0)
  |-- Gain match to target LUFS     CAPPED at +6 dB to avoid boosting silence
  |-- Clipping ceiling (−0.8..−2.0 dBFS)  brick-wall safety (rarely engages)
  |
mastered.flac
```

**Key design choice: no compressor in the default chain, no `loudnorm LRA=X`.** Both flatten dynamics. Instead the chain relies on additive EQ + light saturation to add perceived "life" without squashing transients, then gain-matches to LUFS via ebur128 measurement.

### Presets

| Preset | Target LUFS | Saturation | Best for |
|---|---|---|---|
| `default` | −14 | 2.5 dB | Unknown / mixed genre |
| `edm` | −12 | 3.5 dB | Dubstep, dnb, trance, psy, house, DMT-flash |
| `trap` | −12 | 3.0 dB | 808 rap, drill, hip-hop |
| `chill` | −16 | 1.5 dB | Lofi, ambient, chillhop |
| `orchestral` | −18 | **0 dB** | Classical, film score (fully transparent) |
| `jazz` | −15 | 1.0 dB | Jazz, bossa, bebop, smooth jazz |

### Usage

**Auto-detect (default, recommended):**

```bash
python music_maker.py --prompt "lofi jazz, Rhodes, saxophone, brushed drums" --duration 180
# auto-picks "jazz" preset from prompt keywords
```

**Force a preset:**

```bash
python music_maker.py --prompt "..." --master orchestral
python music_maker.py --prompt "..." --master edm --target-lufs -11   # louder than default
```

**Opt out (raw ACE output, no mastering):**

```bash
python music_maker.py --prompt "..." --master off
```

**Keep both raw and mastered:**

```bash
python music_maker.py --prompt "..." --keep-raw
# writes <output>.flac (mastered) AND <output>.raw.flac (pre-master)
```

### Standalone mastering (on any audio file)

The chain is also callable directly for mastering pre-existing tracks:

```bash
python scene_production_tool/music_mastering.py input.flac --preset orchestral
python scene_production_tool/music_mastering.py input.flac --preset edm -o out.wav --target-lufs -11
```

### Validation

The tool prints a before/after table:

```
[BEFORE] epic_orchestral_xl_base.flac
  LUFS  -11.9  TP  0.30  LRA  23.1  DR  28.5  crest  6.68
[AFTER]  epic_orchestral_xl_base_orchestral.flac  (preset='orchestral')
  LUFS  -18.0  TP -5.82  LRA  22.9  DR  27.9  crest  7.47
  Δ LRA -0.2   Δ DR -0.6   Δ crest +0.79
```

**What to expect:** LUFS hits target within ±0.2 LU. LRA should change by less than 1 LU (preferably +0 or better). Crest factor may drop slightly on tracks whose source was clipping (peaks get cleaned up) or may rise on clean sources (EQ adds punch). TP should land in the −1 to −3 dBTP range (safe for streaming).

**What NOT to expect:** Mastering cannot restore dynamics the generator never produced. A track that comes out of ACE with LRA 1.8 stays at LRA 1.8 after mastering — you get back what was there, with more color and safer peaks. To get more dynamics, fix the **prompt** (see section 5: Writing for dynamics).

## 13. When to use this vs. radio-drama music

**Use this (`music_maker.py`)** when:
- The music is the deliverable (song, single, album cut, demo, jingle)
- You care about audio fidelity — lossless masters, full dynamic range, no mp3 artifacts
- Tracks will be listened to front-and-center, not under dialogue
- You want full base-model quality via APG

**Use `scene_production_tool/radio_drama.py --stage music`** when:
- The music sits UNDER dialogue with sidechain ducking
- 30–60 s cues per scene, MP3 output fine
- Part of a larger radio-drama production
- Speed matters more than ceiling quality

Different templates, different defaults, different output formats. They don't conflict — both exist side-by-side.
