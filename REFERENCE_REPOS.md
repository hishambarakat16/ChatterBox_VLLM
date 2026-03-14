# Reference Repos

Only these repos matter for the current task.

## 1. Chatterbox

- local: `external/chatterbox/`
- role: current baseline

Use for:

- current runtime behavior
- current `T3 -> S3 -> vocoder` path

## 2. CosyVoice

- local: `external/CosyVoice/`
- role: upstream S3-family reference

Use for:

- origin of the token-to-mel design
- `CosyVoice 2` and `CosyVoice 3` comparison

## 3. HiFi-GAN

- local: `external/hifi-gan/`
- role: fallback vocoder reference

Use only if vocoder cost becomes the next bottleneck.

## Ignore For Now

These are not current-task repos:

- `FastSpeech2`
- `camel_tools`
- `Montreal-Forced-Aligner`
- Bahraini front-end tools
- Arabic-only specialization repos
