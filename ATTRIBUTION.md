# Attribution

`aeon-music-maker` is a thin orchestration layer over the work of others. Full credit to:

## Models

### ACE Step 1.5 (StepFun)
The music generation model. All variants (`xl_base`, `xl_sft`, `xl_base_sft`, `xl_turbo`, `base_turbo`) are derivatives of the original ACE Step v1.5 release.

- **Authors:** StepFun AI
- **Repository:** https://github.com/ace-step/ACE-Step
- **Models on HuggingFace:** https://huggingface.co/ace-step/ACE-Step-v1-3.5B
- **Paper:** ACE-Step: A Step Towards Music Generation Foundation Model (StepFun, 2024)

The APG (Adaptive Projected Guidance) chain we use as the recommended high-fidelity sampler is the canonical configuration for `xl_base` / `xl_sft`, originally surfaced via the [NerdyRodent v35 reference workflow](https://github.com/nerdyrodent/AVeryComfyNerd) and validated against the StepFun training notes.

## Custom nodes

- **`TextEncodeAceStepAudio1.5`**, **`EmptyAceStep1.5LatentAudio`**, **`ModelSamplingAuraFlow`**, **`APG`** — shipped with mainline ComfyUI as of recent versions; originally from the ACE Step integration PRs.

## Python libraries

| Library | Use here | Author |
|---|---|---|
| [pedalboard](https://github.com/spotify/pedalboard) | Mastering chain (HPF, EQ, Distortion, Clipping) | Spotify |
| [librosa](https://github.com/librosa/librosa) | LUFS / RMS / DR / crest measurement | Brian McFee et al. |
| [soundfile](https://github.com/bastibe/python-soundfile) | WAV/FLAC IO | Bastian Bechtold |
| [numpy](https://numpy.org/), [scipy](https://scipy.org/) | numerical foundation | NumPy / SciPy teams |
| [requests](https://requests.readthedocs.io/) | HTTP client for ComfyUI API | Kenneth Reitz |

## ComfyUI

The orchestration target. Without ComfyUI's clean node-graph API and Manager ecosystem, this tool would not exist.

- **Repository:** https://github.com/comfyanonymous/ComfyUI

## Mastering chain heuristics

The "no compressor in the default chain, no LRA constraint" approach was validated empirically against orchestral / jazz / EDM material. Targets and curves are in `scripts/music_mastering.py`. EBU R128 LUFS measurements via ffmpeg's `ebur128` filter.

## License notes

This repo is MIT-licensed. The models we orchestrate retain their own licenses — refer to:

- ACE Step: see https://huggingface.co/ace-step/ACE-Step-v1-3.5B for the upstream license terms
- HuggingFace gated-model agreements where applicable
