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
- added [t3_serving_research_memo.md](/Users/hisham/Code/Bahraini_TTS/architecture/t3_serving_research_memo.md) with the focused research read on whether `prefill + step + scheduler` serving is already solved in TTS or mainly inherited from LLM serving
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
- added a first-pass `scheduled` runtime path with:
  - one shared `T3` worker
  - one scheduler per shared `T3` worker
  - per-request mutable decode state
  - batched same-shape `T3` cohorts
- validated `concurrency=2` on the `4060 Ti` with the new `scheduled` path:
  - `errors=[]`
  - trace confirmed one real batched cohort:
    - `run_cohort requests 2`
    - `prefill.batch inputs_embeds (4, 72, 1024)`
- validated `concurrency=4` on the `4060 Ti` with the `scheduled` path:
  - `errors=[]`
  - all four outputs saved successfully
  - throughput improved materially compared with the coarse-lock `concurrent` path
- recorded the first concrete scheduler gains vs the coarse-lock path:
  - `c1` throughput: `0.8549 -> 1.0309` about `+20.6%`
  - `c2` traced throughput: `1.1257 -> 1.7764` about `+57.8%`
  - `c4` throughput: `1.2339 -> 1.8018` about `+46.0%`

## Current Focus

Only this:

- streaming concurrency per GPU

Main KPI:

- `max concurrent streaming sessions per GPU at target latency`

Immediate milestone:

- make `2` simultaneous requests complete correctly on one shared model instance

Status:

- achieved in the `concurrent` A/B path first
- improved further in the `scheduled` A/B path
- correctness holds through `concurrency=4`
- next target is to make the scheduler more dynamic and measure whether `S3` becomes the next bottleneck

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
- the old coarse `T3` lock is no longer the best path
- the new `scheduled` path now proves batched `T3` serving improves performance without retraining
- `S3` is now a more plausible next performance hot path
- but the current scheduler is still cohort-to-completion, so dynamic admission is still missing
- current research read:
  - closest open-source TTS answers already exist in `CosyVoice` and `Fish Audio S2`
  - but they mainly solve the problem by adopting `vLLM` / `SGLang` / `TensorRT-LLM` style serving, not by introducing a separate widely-used TTS-native scheduler layer

## Current Plan

1. keep current Chatterbox as baseline
2. use the working `4060 Ti + Perth-from-source` environment path
3. compare baseline vs new runtime path
4. make `concurrency=2` correct on one shared worker
5. verify correctness beyond `2`
6. keep the new scheduler path as the main runtime branch
7. make the scheduler more dynamic than same-shape cohort-to-completion
8. optimize `S3` next if it is still the next bottleneck after `T3` scheduling improves

## Current Execution Path

- use [CLOUD_GPU_QUICKSTART.md](/Users/hisham/Code/Bahraini_TTS/CLOUD_GPU_QUICKSTART.md)
- initialize only `external/chatterbox`
- use the forked `external/chatterbox` submodule directly
- replace PyPI Perth with Perth from source
- run [benchmark_multilingual_concurrency.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/benchmark_multilingual_concurrency.py) for `baseline`, `streaming`, `concurrent`, and `scheduled`

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
- the new `scheduled` path is the first validated centralized batched decode step in that direction
- the current best long-term `T3` shape is still a more dynamic batched decode scheduler with per-request contexts
- the new single-request traces confirm the tensor flow itself is sane before concurrency is introduced
- the new `concurrent` runtime confirms the short-term `T3` fix is enough to restore correctness at `concurrency=2`
- the `concurrent` runtime also remains correct at `concurrency=4`
- the new `scheduled` runtime proves multiple separate requests can be batched together for `T3`
- the remaining issue is now efficiency:
  - the scheduler still runs same-shape cohorts to completion
  - throughput improved materially, but it is not yet the final serving shape
  - `VRAM` increase was observed qualitatively and still needs formal measurement
  - `S3` is now a more realistic next bottleneck candidate
- current best systems direction:
  - adapt an LLM-serving style `prefill + step + scheduler` design for `T3`
  - do not treat the core scheduler idea itself as novel
  - treat the speech-specific adaptation and evaluation as the real opportunity

## Not Current Work

- Bahraini front end
- Arabic-only student
- tokenizer redesign
- broad architecture brainstorming outside streaming concurrency
