# Streaming Checklist

## KPI

- `max concurrent streaming sessions per GPU at target latency`

## Immediate Gate

- [x] one shared model instance handles `2` simultaneous requests correctly
- [x] both outputs are plausible full utterances
- [x] no truncated output like `1920` samples
- [x] no tensor-shape or kernel-size runtime error

Gate status:

- achieved in the `concurrent` A/B runtime path
- still correct at `concurrency=4`
- implementation shape:
  - request-local `T3` backend
  - request-local alignment analyzer
  - coarse full-decode `T3` lock

## Baseline

- [x] run current Chatterbox once as baseline on GPU
- [ ] record first-chunk latency
- [ ] record inter-chunk latency
- [x] record full-response latency
- [ ] record VRAM usage

Current baseline smoke result:

- `RTX 4060 Ti`
- `load_s=22.2723`
- `latency_s=[4.128, 3.6289, 4.3737]`
- `num_samples=114240`

Current streaming-runtime smoke result:

- `RTX 4060 Ti`
- `load_s=22.2407`
- `latency_s=[4.4991, 4.7963, 5.3084]`
- `num_samples=123840`

Current traced single-request reference:

- [TRACE_RUN_RESULTS.md](/Users/hisham/Code/Bahraini_TTS/TRACE_RUN_RESULTS.md)

## Runtime Refactor

- [x] create `mtl_tts_streaming.py` beside the original runtime wrapper
- [x] create explicit streaming session state files under `external/chatterbox/src/chatterbox/runtime/`
- [x] define a streaming session object
- [x] add a baseline-vs-streaming compare script
- [x] add a simultaneous-request concurrency benchmark script
- [x] create a portable patch for the local Chatterbox runtime changes
- [x] create a cloud GPU runbook for baseline-vs-streaming validation
- [ ] remove shared mutable request state from the model object
- [ ] make conditionals explicit per request
- [ ] keep model weights shared and read-only

## Concurrency Safety

- [x] make one model instance safe for `2` active sessions first
- [x] verify the new `concurrent` path remains correct at `concurrency=4`
- [ ] remove hidden cross-request mutation
- [ ] identify batch-size-1 assumptions on the serving path
- [ ] isolate caches by session
- [x] stop mutating shared `T3` inference state during active requests in the new `concurrent` path
- [ ] replace the coarse full-decode `T3` lock with a better scheduler

Current note:

- baseline and `streaming` are still not the concurrency-safe paths
- the new `concurrent` A/B path is currently the only validated path for `concurrency=2` and `4`

## S3 Work

- [ ] profile `S3` after runtime cleanup
- [ ] reduce per-stream S3 cost
- [ ] rerun the same baseline test

Current read:

- Layer 1 runtime works, but it is slower than baseline on the first single-request smoke test
- current `concurrency=2` is now correct in the `concurrent` path
- current `concurrency=4` is also correct in the `concurrent` path
- `T3` shared inference state was the first blocker, and the first-pass fix worked
- traced single-request flow is sane end-to-end
- next question is efficiency:
  - coarse `T3` lock cost
  - only after reducing that lock can we measure `S3` concurrency cost cleanly

## Decision Rule

- if runtime cleanup is enough, keep the current architecture longer
- if concurrency is still poor, replace or redesign `S3`
- but first make `T3` safe enough for `concurrency=2`

Current status:

- that first gate is done
- `concurrency=4` did not fail
- the next decision point is how to replace coarse `T3` serialization with a scheduler or more granular stepping model
