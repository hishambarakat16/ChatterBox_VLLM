# Progress

_Last updated: 2026-03-14_

## Done

- cloned and registered reference repos as submodules under `external/`
- inspected local `Chatterbox` runtime
- traced `T3 -> S3 -> vocoder`
- confirmed `S3` lineage from the `CosyVoice` family
- checked `CosyVoice 3` as a later family evolution
- reduced the project docs to a streaming-concurrency focus
- defined the local Chatterbox fork strategy and minimal-file-duplication plan
- added Layer 1 streaming-runtime scaffolding inside `external/chatterbox`
- expanded [chatterbox_serving_shape_current_vs_target.html](/Users/hisham/Code/Bahraini_TTS/architecture/chatterbox_serving_shape_current_vs_target.html) into a self-contained engineering diagram with current end-to-end flow, trace shapes, concurrency hazards, target redesign, per-file rewrite map, and the validated `concurrent` checkpoint
- created [patches/chatterbox_streaming_runtime.patch](/Users/hisham/Code/Bahraini_TTS/patches/chatterbox_streaming_runtime.patch) so the local Chatterbox runtime changes can be reproduced on a GPU box
- created [CLOUD_GPU_QUICKSTART.md](/Users/hisham/Code/Bahraini_TTS/CLOUD_GPU_QUICKSTART.md) with the required-only cloud setup and run commands
- confirmed on a `4060 Ti` that PyPI Perth was the real blocker because `perth.PerthImplicitWatermarker` resolved to `None`
- confirmed that reinstalling Perth from source fixes the watermarker path and allows baseline inference to run
- captured the first GPU baseline smoke numbers on `4060 Ti`: `load_s=22.2723`, `latency_s=[4.128, 3.6289, 4.3737]`, `num_samples=114240`
- captured the first Layer 1 streaming-runtime smoke numbers on `4060 Ti`: `load_s=22.2407`, `latency_s=[4.4991, 4.7963, 5.3084]`, `num_samples=123840`
- added [benchmark_multilingual_concurrency.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/benchmark_multilingual_concurrency.py) for simultaneous-request benchmarking at `1/2/4/...` concurrency levels
- confirmed with simultaneous-request benchmarks that `concurrency=2` is still not correct on a shared model instance
- confirmed that the current streaming wrapper reduces some session-state issues but does not isolate shared `T3` inference internals
- added [CHATTERBOX_STATE_FLOW.md](/Users/hisham/Code/Bahraini_TTS/CHATTERBOX_STATE_FLOW.md) as the file-by-file input/output and state-shape reference
- added an opt-in shape-trace path across baseline, streaming, T3, and S3 code paths, now exposed through `--trace-shapes` on the benchmark scripts
- added [t3_concurrent_inference_findings.md](/Users/hisham/Code/Bahraini_TTS/architecture/t3_concurrent_inference_findings.md) with the focused `T3` concurrency hazard review, short-term correctness fix, and long-term scheduler recommendation
- switched the intended cloud workflow from patch-application toward a real forked `external/chatterbox` submodule path
- captured traced single-request baseline and streaming runs in [TRACE_RUN_RESULTS.md](/Users/hisham/Code/Bahraini_TTS/TRACE_RUN_RESULTS.md)
- added a first-pass `concurrent` runtime path with:
  - request-local `T3` backend state
  - request-local alignment analyzer
  - coarse full-decode `T3` lock
- added benchmark WAV export support for per-request listening checks
- validated `concurrency=2` on the `4060 Ti` with the new `concurrent` path:
  - `errors=[]`
  - both outputs saved successfully
  - both outputs sounded correct on manual listening
- validated `concurrency=4` on the `4060 Ti` with the same `concurrent` path:
  - `errors=[]`
  - all four outputs saved successfully
  - correctness held, but throughput scaling remained weak

## Current Focus

Only this:

- streaming concurrency per GPU

Main KPI:

- `max concurrent streaming sessions per GPU at target latency`

Immediate milestone:

- make `2` simultaneous requests complete correctly on one shared model instance

Status:

- achieved in the current `concurrent` A/B path
- correctness holds through `concurrency=4`
- next target is to remove the coarse `T3` serialization bottleneck

## Current Baseline Judgment

Current `Chatterbox` is not concurrency-friendly as written because:

- request state is stored and mutated on the model object
- that either risks unsafe sharing or pushes us toward wasteful one-model-per-request fallback
- S3 contains batch-size-1 assumptions
- T3 and S3 are both serial hot paths

More precise current read:

- the first correctness blocker is still shared mutable `T3` inference state
- the exact `T3` hazards are now pinned down:
  - request-local backend state stored on shared `self`
  - persistent forward hooks installed on shared transformer layers
  - shared `output_attentions` config mutation
- `S3` remains the first likely performance hot path after correctness is restored
- but the coarse `T3` lock is currently hiding how concurrent `S3` really is

## Current Plan

1. keep current Chatterbox as baseline
2. use the working `4060 Ti + Perth-from-source` environment path
3. compare baseline vs new runtime path
4. make `concurrency=2` correct on one shared worker
5. verify correctness beyond `2`
6. replace coarse `T3` serialization with a scheduler or finer stepping model
7. optimize `S3` next if it is still the next bottleneck after `T3` scheduling improves

## Current Execution Path

- use [CLOUD_GPU_QUICKSTART.md](/Users/hisham/Code/Bahraini_TTS/CLOUD_GPU_QUICKSTART.md)
- initialize only `external/chatterbox`
- use the forked `external/chatterbox` submodule directly
- replace PyPI Perth with Perth from source
- run [benchmark_multilingual_concurrency.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/benchmark_multilingual_concurrency.py) for `baseline` and `streaming`

## Current Baseline Note

- the original blocker was the Perth PyPI package, not the runtime concurrency work
- the portable patch still carries a safe Perth fallback, but the cleaner working env fix is Perth from source

## Current Comparison Note

- see [TRACE_RUN_RESULTS.md](/Users/hisham/Code/Bahraini_TTS/TRACE_RUN_RESULTS.md) for the current trusted single-request traced runs
- current read stays the same:
  - both baseline and streaming wrappers are structurally healthy for one request
  - output lengths differ, so raw latency comparisons are not perfectly length-matched

## Current Concurrency Note

Observed behavior on the `4060 Ti`:

- `baseline @ concurrency=2` produced tensor-size mismatch errors
- `streaming @ concurrency=2` avoided a Python exception but one request collapsed to `1920` samples
- `baseline @ concurrency=4` and `streaming @ concurrency=4` still failed

Interpretation:

- the wrapper is not the full fix
- the benchmark is useful because it exposed a real shared-state correctness bug
- the next technical target is `2` simultaneous requests, not higher concurrency yet
- the current best short-term `T3` fix is a coarse full-decode lock plus request-local backend/analyzer state
- the current best long-term `T3` shape is a centralized batched decode scheduler with per-request contexts
- the new single-request traces confirm the tensor flow itself is sane before concurrency is introduced
- the new `concurrent` runtime confirms the short-term `T3` fix is enough to restore correctness at `concurrency=2`
- the `concurrent` runtime also remains correct at `concurrency=4`
- the remaining issue is now efficiency:
  - one request waits behind the coarse `T3` lock
  - throughput improves somewhat, but not enough to call the system scalable yet
  - until that `T3` lock is replaced, `S3` is not being stress-tested behind a truly concurrent front half

## Not Current Work

- Bahraini front end
- Arabic-only student
- tokenizer redesign
- broad architecture brainstorming outside streaming concurrency
