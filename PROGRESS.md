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
- created [chatterbox_serving_shape_current_vs_target.html](/Users/hisham/Code/Bahraini_TTS/architecture/chatterbox_serving_shape_current_vs_target.html) to show current vs target serving architecture with code anchors
- created [patches/chatterbox_streaming_runtime.patch](/Users/hisham/Code/Bahraini_TTS/patches/chatterbox_streaming_runtime.patch) so the local Chatterbox runtime changes can be reproduced on a GPU box
- created [CLOUD_GPU_QUICKSTART.md](/Users/hisham/Code/Bahraini_TTS/CLOUD_GPU_QUICKSTART.md) with the required-only cloud setup and run commands
- confirmed on a `4060 Ti` that PyPI Perth was the real blocker because `perth.PerthImplicitWatermarker` resolved to `None`
- confirmed that reinstalling Perth from source fixes the watermarker path and allows baseline inference to run
- captured the first GPU baseline smoke numbers on `4060 Ti`: `load_s=22.2723`, `latency_s=[4.128, 3.6289, 4.3737]`, `num_samples=114240`
- captured the first Layer 1 streaming-runtime smoke numbers on `4060 Ti`: `load_s=22.2407`, `latency_s=[4.4991, 4.7963, 5.3084]`, `num_samples=123840`
- added [benchmark_multilingual_concurrency.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/benchmark_multilingual_concurrency.py) for simultaneous-request benchmarking at `1/2/4/...` concurrency levels

## Current Focus

Only this:

- streaming concurrency per GPU

Main KPI:

- `max concurrent streaming sessions per GPU at target latency`

## Current Baseline Judgment

Current `Chatterbox` is not concurrency-friendly as written because:

- request state is stored and mutated on the model object
- that either risks unsafe sharing or pushes us toward wasteful one-model-per-request fallback
- S3 contains batch-size-1 assumptions
- T3 and S3 are both serial hot paths

## Current Plan

1. keep current Chatterbox as baseline
2. use the working `4060 Ti + Perth-from-source` environment path
3. compare baseline vs new runtime path
4. confirm the runtime path is stable enough to use as a real baseline fork
5. optimize `S3` next

## Current Execution Path

- use [CLOUD_GPU_QUICKSTART.md](/Users/hisham/Code/Bahraini_TTS/CLOUD_GPU_QUICKSTART.md)
- initialize only `external/chatterbox`
- apply [patches/chatterbox_streaming_runtime.patch](/Users/hisham/Code/Bahraini_TTS/patches/chatterbox_streaming_runtime.patch)
- replace PyPI Perth with Perth from source
- run [benchmark_multilingual_concurrency.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/benchmark_multilingual_concurrency.py) for `baseline` and `streaming`

## Current Baseline Note

- the original blocker was the Perth PyPI package, not the runtime concurrency work
- the portable patch still carries a safe Perth fallback, but the cleaner working env fix is Perth from source

## Current Comparison Note

- baseline avg full-response latency: about `4.04s`
- streaming avg full-response latency: about `4.87s`
- current Layer 1 runtime is therefore slower on this single-request smoke test
- the output lengths also differ (`114240` vs `123840` samples), so this is not a perfectly length-matched comparison yet

## Not Current Work

- Bahraini front end
- Arabic-only student
- tokenizer redesign
- broad architecture brainstorming outside streaming concurrency
