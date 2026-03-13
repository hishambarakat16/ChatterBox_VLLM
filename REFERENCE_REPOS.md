# Reference Repos For The Current Plan

The current plan is no longer "build the Bahraini front end first."

The current plan is:

- use `Chatterbox` as the main architecture under study
- understand where the runtime and scaling bottlenecks are
- treat `S3 token -> mel` as the first likely optimization target
- keep `Arabic-only student` work as the next architectural step

So the reference repo priority has changed.

## Primary References Now

### 1. Chatterbox

- Repo: `https://github.com/resemble-ai/chatterbox`
- Local path: `external/chatterbox/`
- Why:
  - this is now the main architecture being studied
  - it contains the multilingual path, `T3`, `S3Gen`, and Turbo comparison point
- Use it for:
  - multilingual tokenizer behavior
  - `T3` text-to-speech-token path
  - `S3 token -> mel` decoder path
  - conditioning and voice prompt structure

### 2. CosyVoice

- Repo: `https://github.com/FunAudioLLM/CosyVoice`
- Why:
  - Chatterbox `S3Gen` is explicitly modified from CosyVoice-style components
  - useful when tracing the origin of the `speech-token -> mel` path
- Use it for:
  - understanding the flow decoder lineage
  - comparing token-to-mel design choices
  - identifying what Chatterbox inherited versus changed

### 3. F5-TTS

- Local path: `F5-TTS/`
- Why:
  - still a useful comparison point for naturalness-oriented modern TTS
  - useful as a contrastive reference against the Chatterbox path
- Use it for:
  - repo organization
  - deployment ideas
  - comparison against a different architecture family

## Secondary References

### 4. HiFi-GAN

- Repo: `https://github.com/jik876/hifi-gan`
- Why:
  - useful when thinking about vocoder-side efficiency and alternatives
- Use it for:
  - mel-to-waveform boundary understanding
  - lightweight vocoder patterns

### 5. FastSpeech 2

- Repo: `https://github.com/ming024/FastSpeech2`
- Why:
  - still useful as a contrastive controlled architecture
  - relevant only if the project pivots back to a front-end-heavy explicit-control path
- Use it for:
  - comparison against phoneme-first pipelines
  - future fallback if Chatterbox path is abandoned

### 6. CAMeL Tools

- Repo: `https://github.com/CAMeL-Lab/camel_tools`
- Why:
  - still useful later for Arabic normalization utilities
- Use it for:
  - utility preprocessing only

## What We Build Ourselves Later

These are still custom work items, but they are `not` the first priority now:

- Arabic-only text tokenizer or text vocabulary
- Arabic-only student design
- Bahraini specialization and adaptation policy
- later front-end / lexicon work if still needed

## What We Should Not Do

- Do not change the speech tokenizer just because it looks like a clean compression lever.
- Do not assume lower speech-token rate is a local optimization.
- Do not redesign text-side Arabic specialization before profiling the current stack.
- Do not mix runtime optimization and dialect-quality debugging into one workstream.

## Current Local Priority Order

1. `external/chatterbox/`
2. `F5-TTS/`
3. `external/hifi-gan/`
4. `external/FastSpeech2/`
5. `external/camel_tools/`

## Current Decision

The main product decision for now is not:

- "How do we build the full Bahraini stack?"

It is:

- "Can we keep the Chatterbox-style architecture, improve its scalability, and then specialize it cleanly toward Arabic?"
