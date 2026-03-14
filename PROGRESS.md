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
- expanded and later trimmed [chatterbox_serving_shape_current_vs_target.html](/Users/hisham/Code/Bahraini_TTS/architecture/chatterbox_serving_shape_current_vs_target.html) into a self-contained engineering diagram with current end-to-end flow, trace shapes, concurrency hazards, the current `scheduled` runtime checkpoint, and the target shared-vs-request-local boundary
- added [chatterbox_runtime_evolution.html](/Users/hisham/Code/Bahraini_TTS/architecture/chatterbox_runtime_evolution.html) as the chronological runtime change log showing each serving change, its code anchors, and the measured improvement it produced
- updated [chatterbox_runtime_evolution.html](/Users/hisham/Code/Bahraini_TTS/architecture/chatterbox_runtime_evolution.html) with the GPU-local scheduled alignment-state milestone and its measured `c8` improvement over the prior scheduled guard implementation
- added a baseline-to-current concurrency performance ladder to [chatterbox_runtime_evolution.html](/Users/hisham/Code/Bahraini_TTS/architecture/chatterbox_runtime_evolution.html) so the starting point and each later serving gain stay visible in one place
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
- hardened the `scheduled` runtime further:
  - active cohorts are now kept by the scheduler
  - cohorts are advanced step-by-step in round-robin order
  - new requests can enter the scheduler while older cohorts are still decoding
- added benchmark-side `VRAM` reporting:
  - allocated/reserved start
  - allocated/reserved end
  - peak allocated/reserved
  - peak deltas
- captured the first post-hardening scheduled benchmark on the `4060 Ti`:
  - `c1 audio_seconds_per_second = 1.0343`
  - `c2 audio_seconds_per_second = 1.7437`
  - `c4 audio_seconds_per_second = 1.7533`
- captured the first measured `VRAM` growth on the scheduled path:
  - `c1 peak allocated = 3512.7 MB`
  - `c2 peak allocated = 3931.6 MB`
  - `c4 peak allocated = 4499.3 MB`
- observed a live `nvidia-smi` snapshot during the scheduled run showing:
  - about `75%` GPU utilization
  - about `107W` power draw
  - about `4786 MiB` in use
- updated the current operating-point judgment:
  - `c1 -> c2` gives most of the throughput win
  - `c2 -> c4` is nearly flat
  - `concurrency=2` is currently the best operating point for this workload
- added per-stage timing splits to the benchmark output:
  - `stage_text_prep_s`
  - `stage_t3_s`
  - `stage_t3_active_s`
  - `stage_t3_wait_s`
  - `stage_s3_s`
  - `stage_watermark_s`
- captured the first timing-enabled scheduled benchmark on the `4060 Ti`:
  - `c1 audio_seconds_per_second = 1.0346`
  - `c2 audio_seconds_per_second = 1.8267`
  - `c4 audio_seconds_per_second = 2.7884`
- recorded the latest timing-enabled gains:
  - `c1 -> c2` throughput: about `+76.6%`
  - `c2 -> c4` throughput: about `+52.6%`
  - `scheduled c4` vs old coarse-lock `concurrent c4`: about `+126.0%`
- recorded the first timing-based bottleneck read:
  - scheduler wait is tiny under simultaneous-arrival load
  - active `T3` compute is still larger than `S3`
  - `S3` is not the first measured bottleneck yet
- recorded the latest measured `VRAM` peaks on the timed scheduled run:
  - `c1 peak allocated = 3514.1 MB`
  - `c2 peak allocated = 3917.5 MB`
  - `c4 peak allocated = 4735.6 MB`
- updated the current operating-point judgment again:
  - the hardened scheduler now scales meaningfully through `concurrency=4`
  - the next interpretation gap is deeper `T3` profiling plus staggered-arrival validation
- extended the timing-enabled scheduled benchmark to `concurrency=8`
- added latency-specific KPIs to the runtime path:
  - `stage_t3_first_token_s`
  - `stage_audio_ready_s`
- captured the first `1/2/4/8` latency-KPI benchmark on the `4060 Ti`:
  - `c1 throughput = 1.0369`
  - `c2 throughput = 1.767`
  - `c4 throughput = 2.8324`
  - `c8 throughput = 3.2907`
- captured the new first-token read:
  - `c2 T3 first token = 56.5 ms`
  - `c4 T3 first token = 105.0 ms`
  - `c8 T3 first token = 368.0 ms`
- captured the current audio-ready read:
  - `c2 audio ready = 4.5553s`
  - `c4 audio ready = 5.2462s`
  - `c8 audio ready = 8.6152s`
- updated the operating-point judgment again:
  - `c8` still improves throughput, but only modestly over `c4`
  - `c8` is poor for latency-sensitive use
  - `c2/c4` remain the practical operating range depending on whether latency or throughput matters more
- added temporary scheduled-alignment experiment controls and a sweep runner to test:
  - analyzer on vs off
  - inspection frequency
  - selected EOS-policy toggles
- learned from the alignment experiments that:
  - turning the analyzer off causes bad long-tail / gibberish behavior
  - inspecting every `2` steps is already too weak on the tested prompt
  - disabling the `long_tail` force-EOS rule is clearly bad
  - the current safe assumption is still full analyzer inspection every step
- removed the temporary alignment sweep controls and runner after recording the conclusion, so the runtime stays on the validated scheduled path
- rewrote the scheduled alignment analyzer to reduce hot-path overhead without weakening the guard:
  - removed the scheduled hook's per-step `.cpu()` attention copy
  - removed the growing CPU-side full alignment matrix
  - replaced it with rolling GPU-local state for:
    - recent rows
    - early-text activation max
    - post-completion tail mass
    - post-completion repetition mass
- validated the GPU-local scheduled analyzer rewrite on the `4060 Ti`:
  - `errors=[]`
  - manual listening stayed clean
  - clearest high-load gain at `c8`:
    - `wall_s: 11.0954 -> 9.5139`
    - `audio_seconds_per_second: 3.1941 -> 3.4518`
    - `stage_t3_s_mean: 6.9425 -> 5.6515`
    - `stage_t3_first_token_s_mean: 0.2016 -> 0.1561`
- updated the current `T3` bottleneck read again:
  - CPU copies and full-history growth were a real part of the scheduled guard overhead
  - that part is now reduced
  - the next likely structural cost is still `output_attentions=True` forcing the slower attention path
- added a standalone `T3` output-attentions microbenchmark to isolate that one flag from the rest of the runtime
- measured the isolated `output_attentions=True` tax at `concurrency=8`, `decode_steps=64`:
  - `prefill_overhead_pct = 1.16%`
  - `decode_overhead_pct = 14.83%`
  - `total_t3_overhead_pct = 13.71%`
- updated the bottleneck read again:
  - returned attention maps are a real cost
  - but they are not the whole problem
  - the larger structural limit is still the shape of AR decode itself:
    - tiny per-step query length
    - CFG doubling the rows
    - many small decode steps instead of one large GPU-friendly workload

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
- the scheduler has now been hardened and `VRAM` is measured
- per-stage timing now exists and shows `T3` is still the larger current limiter
- the new latency KPIs show `T3` first-token time is much better than full audio-ready time
- next target is to validate staggered arrivals, profile `T3` further, and then add true first-audio-chunk measurement
- the alignment guard stays enabled while this profiling continues, because the recent experiments showed it is necessary for quality
- the current best analyzer implementation is now the GPU-local scheduled version, but the attention-output fallback is still likely the next guard-path tax
- the latest isolated A/B also says the next architecture work should look beyond the guard alone and into the base `T3` decode shape

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
- the hardened `scheduled` path now pushes GPU utilization materially higher than before
- stage timing says active `T3` is still the larger current hot path
- `S3` is still a secondary cost worth tracking, but not the first measured limiter
- the new latency-KPI read refines that:
  - `T3` first token is already decent at `c2` and still near target at `c4`
  - the bigger product gap is that audio is still only ready seconds later
- but the current benchmark shape still launches requests together, so staggered-arrival validation is still missing
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
7. validate the hardened scheduler under staggered arrivals
8. profile deeper inside `T3`, then add true first-audio-chunk measurement before shifting focus to `S3`

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
  - the scheduler now supports active-cohort rotation, but that still needs staggered-arrival validation
  - throughput now improves materially through `concurrency=4`
  - `VRAM` increase is now measured and not just guessed
  - per-stage timing says active `T3` still dominates `S3`
  - the new latency KPIs say the first-token story is much better than the audio-ready story
- current best systems direction:
  - adapt an LLM-serving style `prefill + step + scheduler` design for `T3`
  - do not treat the core scheduler idea itself as novel
  - treat the speech-specific adaptation and evaluation as the real opportunity

## Not Current Work

- Bahraini front end
- Arabic-only student
- tokenizer redesign
- broad architecture brainstorming outside streaming concurrency
