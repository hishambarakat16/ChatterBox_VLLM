# Streaming Checklist

## KPI

- `max concurrent streaming sessions per GPU at target latency`

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

## Runtime Refactor

- [x] create `mtl_tts_streaming.py` beside the original runtime wrapper
- [x] create explicit streaming session state files under `external/chatterbox/src/chatterbox/runtime/`
- [x] define a streaming session object
- [x] add a baseline-vs-streaming compare script
- [x] create a portable patch for the local Chatterbox runtime changes
- [x] create a cloud GPU runbook for baseline-vs-streaming validation
- [ ] remove shared mutable request state from the model object
- [ ] make conditionals explicit per request
- [ ] keep model weights shared and read-only

## Concurrency Safety

- [ ] make one model instance safe for multiple active sessions
- [ ] remove hidden cross-request mutation
- [ ] identify batch-size-1 assumptions on the serving path
- [ ] isolate caches by session

## S3 Work

- [ ] profile `S3` after runtime cleanup
- [ ] reduce per-stream S3 cost
- [ ] rerun the same baseline test

## Decision Rule

- if runtime cleanup is enough, keep the current architecture longer
- if concurrency is still poor, replace or redesign `S3`
- only revisit `T3` after that
