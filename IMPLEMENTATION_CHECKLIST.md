# Streaming Checklist

## KPI

- `max concurrent streaming sessions per GPU at target latency`

## Immediate Gate

- [x] one shared model instance handles `2` simultaneous requests correctly
- [x] both outputs are plausible full utterances
- [x] no truncated output like `1920` samples
- [x] no tensor-shape or kernel-size runtime error

Gate status:

- achieved first in the `concurrent` A/B runtime path
- improved further in the `scheduled` A/B runtime path
- still correct at `concurrency=4`
- current best implementation shape:
  - request-local `T3` backend
  - request-local alignment analyzer state
  - shared `T3` weights
  - cohort-based `T3` scheduler

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
- [x] add a cohort-based `T3` scheduler path
- [ ] make the scheduler admit new requests dynamically mid-cohort

## Concurrency Safety

- [x] make one model instance safe for `2` active sessions first
- [x] verify the new `concurrent` path remains correct at `concurrency=4`
- [x] verify the new `scheduled` path remains correct at `concurrency=4`
- [ ] remove hidden cross-request mutation
- [ ] identify batch-size-1 assumptions on the serving path
- [ ] isolate caches by session
- [x] stop mutating shared `T3` inference state during active requests in the new `concurrent` path
- [x] replace the coarse full-decode `T3` lock with a first-pass cohort scheduler
- [ ] make `T3` scheduling fully dynamic instead of cohort-to-completion
- [ ] measure peak `VRAM` for `concurrent` vs `scheduled`

Current note:

- baseline and `streaming` are still not the concurrency-safe paths
- the new `concurrent` A/B path restored correctness first
- the new `scheduled` A/B path is now the best validated path for `concurrency=2` and `4`
- the trace confirms it batches multiple separate requests together for `T3`

## S3 Work

- [ ] profile `S3` after runtime cleanup
- [ ] reduce per-stream S3 cost
- [ ] rerun the same baseline test

Current read:

- Layer 1 runtime works, but it is slower than baseline on the first single-request smoke test
- current `concurrency=2` is now correct in both `concurrent` and `scheduled`
- current `concurrency=4` is also correct in both `concurrent` and `scheduled`
- `T3` shared inference state was the first blocker, and the first-pass fix worked
- traced single-request flow is sane end-to-end
- next question is efficiency:
  - improve beyond same-shape cohort scheduling
  - measure `VRAM`
  - quantify whether `S3` is now the next bottleneck

## Decision Rule

- if runtime cleanup is enough, keep the current architecture longer
- if concurrency is still poor, replace or redesign `S3`
- but first make `T3` safe enough for `concurrency=2`

Current status:

- that first gate is done
- `concurrency=4` did not fail
- the coarse `T3` lock has now been replaced by a first-pass cohort scheduler
- the next decision point is how to make that scheduler more dynamic and how to measure `S3` under the less-serialized front half
