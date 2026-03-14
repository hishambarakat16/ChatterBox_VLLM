# Planner Re-Architecture References

This folder stores the primary-source bundle for the `T3 planner replacement while keeping S3 fixed` research pass.

## Local PDFs

- `2023_tacl_spear_tts.pdf`
  - `SPEAR-TTS`
  - best structural precedent for separating planner and downstream speaking/rendering
  - source: <https://aclanthology.org/2023.tacl-1.95/>
- `2305.09636_soundstorm.pdf`
  - `SoundStorm`
  - stage-local parallel replacement while keeping semantic input and codec decoder structure
  - source: <https://arxiv.org/abs/2305.09636>
- `2401.01099_group_masked_language_modeling.pdf`
  - `G-MLM`
  - group-masked parallel codec generation, fewer decoding iterations than SoundStorm-style masking
  - source: <https://arxiv.org/abs/2401.01099>
- `2406.05370_valle2.pdf`
  - `VALL-E 2`
  - grouped code modeling to reduce effective autoregressive length
  - source: <https://arxiv.org/abs/2406.05370>
- `2406.07855_valler.pdf`
  - `VALL-E R`
  - planner-side monotonic alignment and codec merging for fewer autoregressive steps
  - source: <https://arxiv.org/abs/2406.07855>
- `2409.00750_maskgct.pdf`
  - `MaskGCT`
  - fully non-autoregressive masked generative codec transformer with released code in Amphion
  - source: <https://arxiv.org/abs/2409.00750>
- `2603.08823_fish_audio_s2_technical_report.pdf`
  - `Fish Audio S2`
  - product-oriented Dual-AR planner and streaming deployment evidence
  - source: <https://arxiv.org/abs/2603.08823>

## Supporting Sources

- `SPEAR-TTS` ACL Anthology page:
  - <https://aclanthology.org/2023.tacl-1.95/>
- `VALL-E 2` Microsoft Research page:
  - <https://www.microsoft.com/en-us/research/publication/vall-e-2-neural-codec-language-models-are-human-parity-zero-shot-text-to-speech-synthesizers/>
- `VALL-E R` Microsoft Research page:
  - <https://www.microsoft.com/en-us/research/publication/vall-e-r-robust-and-efficient-zero-shot-text-to-speech-synthesis-via-monotonic-alignment/>
- `MaskGCT` official code path in Amphion:
  - <https://github.com/open-mmlab/Amphion>
- `Fish Audio S2` model card:
  - <https://huggingface.co/fishaudio/s2-pro/blob/main/README.md>
