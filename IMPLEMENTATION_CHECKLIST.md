# Streaming Checklist

## KPI

- `max concurrent streaming sessions per GPU at target latency`

## Baseline

- [ ] run current Chatterbox once as baseline
- [ ] record first-chunk latency
- [ ] record inter-chunk latency
- [ ] record full-response latency
- [ ] record VRAM usage

## Runtime Refactor

- [ ] create `mtl_tts_streaming.py` beside the original runtime wrapper
- [ ] create explicit streaming session state files under `external/chatterbox/src/chatterbox/runtime/`
- [ ] remove shared mutable request state from the model object
- [ ] make conditionals explicit per request
- [ ] define a streaming session object
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
