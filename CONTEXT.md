# Bahraini TTS — Current Context

## Current Goal

The project is currently focused on one thing only:

- make the `Chatterbox`-style stack better for `streaming concurrency`

The main KPI is:

- `max concurrent streaming sessions per GPU at target latency`

Support metrics:

- `p95 first-chunk latency`
- `p95 inter-chunk latency`
- `VRAM per active stream`

## Current Baseline

The baseline is the current open-source `Chatterbox` multilingual stack.

Current mental model:

```text
text
  -> multilingual tokenizer
  -> T3 speech-token LM
  -> S3 token-to-mel decoder
  -> vocoder
  -> waveform
```

We are treating the current implementation as the reference system to beat.

## What We Know

### 1. The stack is serial twice

- `T3` generates speech tokens autoregressively
- `S3` decodes those tokens with iterative flow

This is the core structural reason concurrency is hard.

### 2. The current runtime is not request-safe

In `mtl_tts.py`, the model instance stores and mutates shared `self.conds`.

That is bad for concurrent serving.

### 3. The current S3 path is likely the first hot spot

- Chatterbox README says `speech-token -> mel` was the bottleneck
- `S3` still does mel-space iterative decoding
- the decoder works on the longer mel timeline, not the shorter token timeline

### 4. Chatterbox S3 comes from the CosyVoice family

Useful lineage:

- `Matcha-TTS` -> flow-matching acoustic decoder idea
- `CosyVoice` -> speech-token conditioning + prompt mel + speaker conditioning
- `Chatterbox S3` -> adapted from CosyVoice-style token-to-mel design

`CosyVoice 3` is a later improvement in the same family, but it still keeps:

- AR speech-token generation
- iterative flow decoding
- separate vocoder

So it is a better family member, not a full structural fix.

## Current Non-Goals

These are intentionally out of scope right now:

- Bahraini front end work
- Arabic-only specialization
- tokenizer redesign
- speech-token interface redesign
- quality tuning as the main objective

They can come back later. They are not the current task.

## Current Implementation Direction

Repo strategy:

- use `external/chatterbox/` as the working fork
- keep upstream file paths visible as baseline references
- duplicate only the files we actually need to change

Concrete fork plan:

- [CHATTERBOX_FORK_IMPLEMENTATION_PLAN.md](/Users/hisham/Code/Bahraini_TTS/CHATTERBOX_FORK_IMPLEMENTATION_PLAN.md)

### Phase 1: Fix the runtime shape

- remove shared mutable request state
- make per-request / per-session conditionals explicit
- define a streaming session abstraction
- make the runtime concurrency-safe

### Phase 2: Improve streaming efficiency

- keep `T3` unchanged at first
- isolate `S3` as the first decoder hot path
- reduce per-stream cost on the S3 side

### Phase 3: Re-evaluate architecture

If the runtime is request-safe but concurrency is still poor:

- decide whether S3 must be replaced
- decide whether T3 autoregression must also be reduced

## Current Decision

The shortest path is:

1. treat current Chatterbox as baseline
2. make the runtime concurrency-safe
3. attack `S3` first
4. compare against baseline

Anything outside that path is context bloat for now.
