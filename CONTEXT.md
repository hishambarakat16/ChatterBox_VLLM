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

Immediate milestone:

- make `2` simultaneous requests complete correctly on one shared model instance
- treat truncated outputs and silent early-stop outputs as failures, even if Python does not raise

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

Serving-shape visual:

- [chatterbox_serving_shape_current_vs_target.html](/Users/hisham/Code/Bahraini_TTS/architecture/chatterbox_serving_shape_current_vs_target.html)
- [CLOUD_GPU_QUICKSTART.md](/Users/hisham/Code/Bahraini_TTS/CLOUD_GPU_QUICKSTART.md)
- [CHATTERBOX_STATE_FLOW.md](/Users/hisham/Code/Bahraini_TTS/CHATTERBOX_STATE_FLOW.md)

## What We Know

### 1. The stack is serial twice

- `T3` generates speech tokens autoregressively
- `S3` decodes those tokens with iterative flow

This is the core structural reason concurrency is hard.

### 2. The current runtime is not request-safe

In `mtl_tts.py`, the model instance stores and mutates shared `self.conds`.

That is bad for concurrent serving.

The current issue is therefore:

- runtime architecture problem
- plus serial model architecture problem

Not just one slow function.

There was also a separate baseline environment issue:

- on the tested `4060 Ti` env, the PyPI Perth package exposed `perth.PerthImplicitWatermarker` as `None`
- reinstalling Perth from source fixed that
- that was a dependency/runtime issue, not evidence against the streaming runtime work

New benchmark result:

- both `baseline` and the current `streaming` wrapper break logically or structurally at `concurrency >= 2`
- the wrapper improved session-state isolation, but did not make the shared `T3` inference path safe
- the first concrete milestone is therefore not "scale hard", but "make `2` simultaneous requests correct"

The strongest current suspect is `T3.inference()`:

- it resets `self.compiled = False` per call
- rebuilds `AlignmentStreamAnalyzer`
- rebuilds `self.patched_model`
- stores those objects back on the shared `T3` instance

That means concurrent requests can still stomp on shared inference state even after the new session wrapper.

### 3. The current S3 path is likely the first hot spot

- Chatterbox README says `speech-token -> mel` was the bottleneck
- `S3` still does mel-space iterative decoding
- the decoder works on the longer mel timeline, not the shorter token timeline

But `S3` is not the first correctness blocker anymore.

Current order:

- first fix `T3` concurrency correctness for `2` simultaneous requests
- then profile and reduce `S3` serving cost

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

Current Layer 1 artifacts already exist locally:

- [mtl_tts_streaming.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/mtl_tts_streaming.py)
- [runtime/session.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/runtime/session.py)
- [runtime/types.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/runtime/types.py)
- [runtime/worker.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/runtime/worker.py)
- [compare_multilingual_runtime.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/compare_multilingual_runtime.py)
- [benchmark_multilingual_concurrency.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/benchmark_multilingual_concurrency.py)

Important current repo fact:

- these runtime changes live inside the local `external/chatterbox` submodule worktree
- the portable execution path is the patch file plus quickstart, not a published Chatterbox submodule fork yet
- portable artifacts:
  - [patches/chatterbox_streaming_runtime.patch](/Users/hisham/Code/Bahraini_TTS/patches/chatterbox_streaming_runtime.patch)
  - [CLOUD_GPU_QUICKSTART.md](/Users/hisham/Code/Bahraini_TTS/CLOUD_GPU_QUICKSTART.md)
- the current portable patch also carries a safe Perth fallback so benchmarking is not blocked by the watermark dependency

Current validated baseline smoke result:

- GPU: `RTX 4060 Ti`
- `load_s=22.2723`
- `latency_s=[4.128, 3.6289, 4.3737]`
- `num_samples=114240`

Current validated Layer 1 streaming-runtime smoke result:

- GPU: `RTX 4060 Ti`
- `load_s=22.2407`
- `latency_s=[4.4991, 4.7963, 5.3084]`
- `num_samples=123840`

Immediate interpretation:

- Layer 1 runtime is functionally working
- it is slower than baseline on this single-request smoke test
- this does not yet answer the concurrency question

The target runtime shape is:

- shared worker owns read-only model weights and helpers
- session object owns request conditionals, caches, and decode progress

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
2. validate the new Layer 1 runtime path on GPU using the patch + quickstart flow
3. compare baseline vs new runtime path under simultaneous requests
4. make `2` simultaneous requests work correctly on one shared model instance
5. only then decide whether `S3` must change first

Anything outside that path is context bloat for now.
