# Reference Repos For Bahraini TTS

This project should not try to "clone everything." The goal is to collect a small set of strong reference repos, each tied to one subsystem in the architecture, so we can study structure and selectively borrow ideas without letting external code define the product.

## What We Build Ourselves

These are the parts that should remain Bahraini-specific and custom:

- Text normalization rules for Bahraini Arabic
- Bahraini phoneme inventory
- Bahraini lexicon and pronunciation overrides
- Code-switch handling policy
- Dataset manifests and preprocessing glue
- The final training entrypoints and project structure

These are the parts where external repos are useful as references or starting points:

- Acoustic model implementation patterns
- Vocoder implementation and training setup
- Forced alignment and feature extraction
- Arabic text processing utilities
- Full-stack training/inference examples

## Recommended Clone Set

Clone these into `external/` and keep them out of version control.

### 1. Acoustic Model

#### Primary reference: FastSpeech 2

- Repo: `https://github.com/ming024/FastSpeech2`
- Why: Clean, focused FastSpeech 2 implementation that maps directly to the architecture in `CONTEXT.md`
- Use it for:
  - encoder / decoder structure
  - variance adaptor wiring
  - duration / pitch / energy training flow
  - dataset and preprocessing patterns

#### Secondary reference: NVIDIA FastPitch

- Repo: `https://github.com/NVIDIA/DeepLearningExamples/tree/master/PyTorch/SpeechSynthesis/FastPitch`
- Why: Production-minded non-autoregressive TTS implementation with strong engineering patterns
- Use it for:
  - training structure
  - feature extraction pipeline
  - optimization and inference ideas
- Note: This is not exactly the same architecture as FastSpeech 2, but it is close enough to be very useful.

### 2. Vocoder

#### Primary reference: HiFi-GAN

- Repo: `https://github.com/jik876/hifi-gan`
- Why: Standard fast neural vocoder and the most natural fit for v1
- Use it for:
  - generator / discriminator setup
  - mel-to-waveform training
  - config patterns for lightweight deployment

#### Secondary reference: BigVGAN

- Repo: `https://github.com/NVIDIA/BigVGAN`
- Why: Useful upgrade path if quality is more important than simplicity
- Use it for:
  - higher-quality vocoder ideas
  - comparison against HiFi-GAN
- Note: Treat this as optional until v1 works end to end.

### 3. Alignment And Data Prep

#### Primary reference: Montreal Forced Aligner

- Repo: `https://github.com/MontrealCorpusTools/Montreal-Forced-Aligner`
- Why: Best reference for duration target generation if we stay with a FastSpeech 2 style training setup
- Use it for:
  - alignment workflow
  - pronunciation dictionary formats
  - corpus preparation
- Important: Generic Arabic resources may help as bootstrap material, but Bahraini-specific pronunciation will still need custom work.

### 4. Arabic Front End

#### Primary utility reference: CAMeL Tools

- Repo: `https://github.com/CAMeL-Lab/camel_tools`
- Why: Useful Arabic NLP utilities for tokenization, normalization, and general text handling
- Use it for:
  - Arabic normalization helpers
  - tokenization ideas
  - general preprocessing support
- Important: This is not a Bahraini G2P solution. It is only a utility layer.

#### Optional utility reference: phonemizer + espeak-ng

- Repo: `https://github.com/bootphon/phonemizer`
- Repo: `https://github.com/espeak-ng/espeak-ng`
- Why: Useful for quick experiments or pronunciation baselines
- Use it for:
  - rough phoneme baselines
  - experimentation only
- Important: Do not let these define the final Bahraini front end. Also watch license implications before integrating them into production code.

### 5. Full-Stack Survey Reference

#### Optional: Coqui TTS

- Repo: `https://github.com/coqui-ai/TTS`
- Why: Large end-to-end TTS toolkit with many models and training recipes
- Use it for:
  - project structure ideas
  - dataset config patterns
  - trainer abstractions
- Important: This is a study repo, not a good basis for the Bahraini-specific front end.

## Existing Local Reference

- `F5-TTS/` is already present locally.
- Keep it as a contrastive reference only.
- It is useful for:
  - modern TTS repo organization
  - deployment ideas
  - general engineering patterns
- It is not a good architectural source for the current plan, because the target design is deterministic front end + FastSpeech 2 style acoustic model + separate vocoder.

## What We Should Not Do

- Do not merge large upstream repos directly into the main codebase.
- Do not start implementation by copying random files from many repos.
- Do not let a full-stack toolkit override the Bahraini-specific front end design.
- Do not lock ourselves into TensorRT, DDP, or streaming details before the first model trains.

## Recommended Clone Order

1. `ming024/FastSpeech2`
2. `jik876/hifi-gan`
3. `Montreal-Forced-Aligner`
4. `CAMeL-Lab/camel_tools`
5. `NVIDIA FastPitch`
6. `NVIDIA/BigVGAN`
7. `coqui-ai/TTS`

This gives us the minimum set needed to answer the main design question first:

"Can we build a Bahraini-specific deterministic front end and connect it to a practical non-autoregressive acoustic model plus a fast vocoder?"

## Suggested Local Layout

```text
Bahraini_TTS/
├── external/
│   ├── FastSpeech2/
│   ├── hifi-gan/
│   ├── Montreal-Forced-Aligner/
│   ├── camel_tools/
│   ├── FastPitch/
│   ├── BigVGAN/
│   └── TTS/
├── docs/
├── frontend/
├── data/
├── training/
├── inference/
└── vocoder/
```

## The Real Decision

We are not deciding whether code exists. It does.

We are deciding which parts are commodity and which parts are the product.

For this project, the product is the Bahraini front end, the data choices, and the integration decisions. The model internals and vocoder internals are mostly reference material unless we discover a strong reason to customize them deeply.
