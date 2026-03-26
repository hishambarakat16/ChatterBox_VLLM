# Chatterbox Streaming Plan

## Objective

Optimize for:

- `max concurrent streaming sessions per GPU at target latency`

Near-term success gate:

- `2` simultaneous requests on one shared model instance
- both requests must return plausible full audio
- no Python exception
- no obvious collapsed output like `1920` samples

Not for:

- Bahraini quality
- Arabic specialization
- tokenizer redesign

## Baseline

Use the current `Chatterbox` implementation as the baseline.

We do not need a long research phase before acting.

We already have the first baseline measurement set.

The next job is narrower:

- make `concurrency=2` correct before caring about `4+`

Current status:

- `concurrency=2` is now correct in the `concurrent` path
- `concurrency=4` is also correct
- the next blocker is no longer correctness, but the coarse `T3` serialization strategy

Current validated baseline env note:

- `RTX 4060 Ti` with stock `torch 2.6.0+cu124` was fine
- the real blocker was PyPI Perth, not CUDA on that machine
- reinstalling Perth from source fixed baseline loading

Repo strategy:

- use `external/chatterbox/` as the working fork
- keep original upstream file paths as the baseline path
- add new streaming-specific files beside the originals

See:

- [CHATTERBOX_FORK_IMPLEMENTATION_PLAN.md](/Users/hisham/Code/Bahraini_TTS/CHATTERBOX_FORK_IMPLEMENTATION_PLAN.md)
- [CHATTERBOX_STATE_FLOW.md](/Users/hisham/Code/Bahraini_TTS/CHATTERBOX_STATE_FLOW.md)
- [chatterbox_serving_shape_current_vs_target.html](/Users/hisham/Code/Bahraini_TTS/architecture/chatterbox_serving_shape_current_vs_target.html)
- [CLOUD_GPU_QUICKSTART.md](/Users/hisham/Code/Bahraini_TTS/CLOUD_GPU_QUICKSTART.md)

## What Must Be Fixed First

### 1. Request isolation

Current problem:

- `self.conds` is stored on the model instance and mutated per request
- the serving problem is runtime shape plus a double-serial model path, not one isolated slow line

Target:

- no request-specific mutable state on the shared model object
- all conditionals passed explicitly through a session/request object

### 2. Streaming session model

Target:

- one explicit streaming session object per active request
- session owns its prompt state, caches, and decode progress
- shared model weights stay read-only

Current Layer 1 status:

- this path is implemented locally in a parallel runtime wrapper
- the baseline [mtl_tts.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/mtl_tts.py) is still untouched
- the preferred GPU path is now the forked `external/chatterbox` submodule plus:
  - [CLOUD_GPU_QUICKSTART.md](/Users/hisham/Code/Bahraini_TTS/CLOUD_GPU_QUICKSTART.md)
- the patch file is now fallback-only

### 3. Concurrency safety

Target:

- multiple active sessions can share one model worker safely
- no hidden cross-request mutation
- no global prompt state

Current read:

- session data is now more isolated
- `T3` inference internals were the first blocker and are now isolated in the `concurrent` path
- the new issue is that the current fix uses a coarse full-decode `T3` lock
- the exact hazard breakdown is recorded in [t3_concurrent_inference_findings.md](/Users/hisham/Code/Bahraini_TTS/architecture/t3_concurrent_inference_findings.md)
- the most direct blockers are shared `self.patched_model` / `self.compiled` mutation plus persistent forward hooks on shared transformer layers
- the current most direct scalability blocker is the coarse `T3` lock, not corrupted shared state

### 4. S3 serving cost

After the runtime is safe:

- profile `S3` as the first hot path
- reduce per-stream decoder cost there first

This ordering matters:

- `T3` was the first correctness blocker
- `S3` is still the first likely performance hot path after correctness is restored
- but `S3` is not being measured fairly yet while `T3` is serialized with a full-decode lock

## Current Architecture Judgment

### What is probably okay for now

- multilingual tokenizer
- T3 as the initial baseline text-to-speech-token stage
- existing speech-token interface

### What is probably not okay for streaming density

- shared mutable runtime state
- batch-size-1 assumptions on the S3 side
- iterative mel-space S3 cost under many active streams

The main runtime decision remains:

- fix request/session isolation first
- then decide whether `S3` itself must change

## Decision Rule

If request isolation + runtime cleanup gives acceptable concurrency:

- keep the architecture longer

If request isolation is fixed and concurrency is still poor:

- replace or redesign `S3`

If S3 is improved and concurrency is still poor:

- revisit `T3` autoregression

## Immediate Work Order

1. use [CLOUD_GPU_QUICKSTART.md](/Users/hisham/Code/Bahraini_TTS/CLOUD_GPU_QUICKSTART.md) on the GPU box
2. keep the forked `external/chatterbox` submodule as the execution path
3. treat `concurrency=2` and `concurrency=4` stability as correctness checkpoints already achieved
4. profile how much throughput is being lost to the coarse full-decode `T3` lock
5. replace that lock with a scheduler or finer-grained stepping model
6. rerun concurrency benchmarks after the new `T3` scheduling shape
7. only then attack `S3`

## Current Boundary Decision

We are deliberately not pushing more of the prompt/input assembly stack into `vLLM`.

Rationale:

- the earlier fixed-shape `vLLM` path scaled well and stayed relatively simple
- the instability showed up when dynamic text and mixed prompt shapes were pushed through one reused engine
- once prompt assembly and input-contract handling move deeper into `vLLM`, the serving path starts to sprawl across two libraries at once
- that creates maintenance overhead, makes failures harder to localize, and turns `vLLM` into the place where every Chatterbox-specific detail must be reimplemented
- that is not the cheapest architecture to maintain unless we are fully committing to a deep fork

Current decision:

- treat the current fixed-prompt-embed `vLLM` path as the serving core
- keep dynamic ingestion and chunking outside `vLLM`
- make the upstream ingestion layer produce stable, bounded request shapes before requests enter the engine
- only revisit deeper `vLLM` integration if the simpler boundary fails on throughput or quality

## Ingestion Policy

The next optimization step is not a `vLLM` rewrite.

It is an ingestion contract:

- chunk input by text-token budget, not by raw character count
- keep the target chunk size in the `64` to `128` token range
- start calibration around `96` tokens as the middle point
- set `max_new_tokens` to match the chosen chunk budget instead of leaving a large tail budget that turns into silence
- split on whitespace and punctuation boundaries so words do not get cut mid-token when possible
- if a boundary forces a short leftover gap, accept a small pause rather than overfilling the chunk
- if needed, carry the cut text into the next chunk and allow a small inter-chunk pause to hide the seam

Why this policy:

- it keeps prompt-embed length and decode budget much more stable
- it avoids wasting latency on extra low-information tail tokens
- it lets us benchmark concurrency on a controlled serving shape
- it preserves a cleaner separation of responsibilities: ingestion outside, fast batched decode inside

## Multiprocessing Note

Process isolation is a deployment fallback, not the core fix.

Why:

- it sidesteps thread-unsafety by duplicating the model into separate processes
- that increases VRAM pressure and lowers sessions-per-GPU density
- it avoids the bug, but does not make one shared worker efficient
- it can still be useful later for production isolation, but it is not the architectural win we are trying to prove first

## Reference Scope

Only keep these mental references active:

- `Chatterbox` = current baseline
- `CosyVoice` = origin of the S3 family
- `CosyVoice 3` = later family evolution, useful reference but not the answer by itself
