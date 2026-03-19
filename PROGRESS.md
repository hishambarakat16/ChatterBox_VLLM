# Progress

_Last updated: 2026-03-19_

## Done

- documented the serious `vLLM` environment incident in [VLLM_ENV_INCIDENT.md](/home/ubuntu/ChatterBox_S3_Concurrency/VLLM_ENV_INCIDENT.md) so later agents do not repeat the same multi-cause failure
- fixed the cloud `vLLM` preflight path end to end on the `RTX A6000` box:
  - export `LD_LIBRARY_PATH=/usr/local/cuda/lib64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}`
  - export `VLLM_WORKER_MULTIPROC_METHOD=spawn`
  - install local Chatterbox into `chatterbox-vllm` with `python -m pip install -e external/chatterbox --no-deps`
  - register the custom `ChatterboxT3ForCausalLM` architecture through a `vLLM` general plugin so spawned workers see it too
- revalidated `external/chatterbox/vllm_t3_preflight.py` against `runs/t3_hydra_ar_short_40k_h2_run1/vllm_t3_export` and reached `engine_init=ok`
- completed the first working Hydra-free `vLLM + turbo S3` spike on the `RTX A6000` box:
  - single-request `vllm_turbo_s3` now runs end to end with base multilingual `T3` weights and `turbo S3`
  - the first apparent multi-request `vLLM` "freeze" was traced to an integration-shape bug, not a fundamental `vLLM` failure:
    - we were incorrectly simulating concurrency by calling the same offline `LLM.generate()` from multiple Python threads
    - the correct offline `vLLM` pattern is one batched `generate(...)` call containing many prompts
  - fixed the benchmark so the `vLLM` path now batches independent request-local sessions into one prompt-embed batch before calling the shared engine
  - confirmed on `concurrency=4` that the shared `T3/vLLM` stage is now truly batched:
    - `stage_t3_batch_size_mean=4.0`
    - `stage_t3_s_mean=0.9728`
    - `wall_s=5.6751`
    - `audio_seconds_total=18.76`
    - `audio_seconds_per_second=3.3057`
  - pushed the same batching shape to `concurrency=16`:
    - `stage_t3_batch_size_mean=16.0`
    - `stage_t3_s_mean=1.0512`
    - `wall_s=8.1052`
    - `audio_seconds_total=80.32`
    - `audio_seconds_per_second=9.9096`
  - updated read:
    - `vLLM` is using one shared engine, not one model copy per request
    - the large `VRAM` reservation is mostly shared KV/cache reservation, not request duplication
    - after batching `T3` correctly, the next dominant end-to-end cost is downstream `S3`
  - quality caveat discovered from saved WAV inspection:
    - some batched `vLLM` outputs linger past the intended speech ending with noisy tails
    - the main reason is that the current `vLLM` spike does not yet have parity with the original multilingual `AlignmentStreamAnalyzer` stop controller
    - `drop_invalid_tokens()` is only post-generation cleanup and cannot replace the decode-time EOS controller
    - current mitigation:
      - record per-row stop diagnostics (`stop` vs `length` cap)
      - conservatively trim clearly repetitive suffixes only when a row ends by length cap
    - current read:
      - throughput is very strong
      - quality / stop-control parity is the main remaining blocker before treating this as a production-ready migration
  - new service-design read:
    - logical customer concurrency can be implemented as an admission/batching layer in front of one shared `vLLM` engine
    - the current offline benchmark now demonstrates that shape
    - a true staggered online service path is still a separate next step and likely needs either `AsyncLLMEngine` or an explicit custom request queue around the shared engine
  - tightened the `vLLM` benchmark/save path to avoid unnecessary env churn:
    - benchmark / compare / simulator WAV outputs now save through `soundfile`
    - `torchcodec` is not required for the current `vLLM` migration workflow
    - this keeps the dedicated `chatterbox-vllm` env leaner and avoids a new media-codec dependency just for artifact export
- merged the missing engine-migration state from the older alternate-machine progress snapshot so this repo keeps that history too
- added [t3_engine_migration_memo.md](/Users/hisham/Code/Bahraini_TTS/architecture/t3_engine_migration_memo.md) as the current engine-migration decision memo for the multilingual `T3 + Hydra + turbo S3` stack:
  - mapped the current `T3` boundary into `thin adapter`, `scheduler/runtime replacement`, `model boundary`, `Hydra`, `CFG`, and `speech-token / multilingual` concerns
  - compared `vLLM`, `SGLang`, and `TensorRT-LLM` against the actual local `T3` contract instead of treating them as generic LLM engines
  - made the recommendation explicit:
    - `vLLM` = first feasibility target
    - `SGLang` = later optimization target
    - `TensorRT-LLM` = not recommended at the current migration stage
  - recorded a concrete minimal first spike:
    - externalize only `T3` scheduling/runtime
    - keep app/session + tokenizer + `turbo S3`
    - defer `Hydra`
    - defer `CFG`
    - benchmark mixed-traffic behavior directly
- added [t3_mixed_traffic_scheduler_research_memo.md](/Users/hisham/Code/Bahraini_TTS/architecture/t3_mixed_traffic_scheduler_research_memo.md) with a focused research pass on staggered mixed-length `T3` traffic:
  - continuous batching / dynamic batching / rebatching best practices
  - admission-window and bucketing guidance
  - active-cohort cap and fairness guidance
  - decode-priority / chunked-prefill guidance
  - guidance on when `vLLM`, `SGLang`, `TensorRT-LLM`, `Triton`, `DistServe`, and `Llumnix` are relevant versus overkill
  - later expanded it into a fuller standalone findings document with:
    - executive summary
    - local problem statement
    - ranked recommendation order
    - anti-patterns to avoid
    - suggested scheduler metrics
    - practical engineering sequence
    - local paper/repo bundle references
- downloaded the primary scheduler-serving papers into [References/scheduler_serving](/Users/hisham/Code/Bahraini_TTS/References/scheduler_serving):
  - `Orca`
  - `vLLM`
  - `Sarathi-Serve`
  - `FastServe`
  - `SGLang`
  - `DistServe`
  - `Llumnix`
- cloned the main serving-system reference repos into `external/`:
  - [vllm](/Users/hisham/Code/Bahraini_TTS/external/vllm)
  - [sglang](/Users/hisham/Code/Bahraini_TTS/external/sglang)
  - [sarathi-serve](/Users/hisham/Code/Bahraini_TTS/external/sarathi-serve)
  - [FastServe](/Users/hisham/Code/Bahraini_TTS/external/FastServe)
  - [TensorRT-LLM](/Users/hisham/Code/Bahraini_TTS/external/TensorRT-LLM)
  - [DistServe](/Users/hisham/Code/Bahraini_TTS/external/DistServe)
  - [llumnix-ray](/Users/hisham/Code/Bahraini_TTS/external/llumnix-ray)
  - [triton-server](/Users/hisham/Code/Bahraini_TTS/external/triton-server)
- completed the first isolated `turbo S3` experiment while keeping the multilingual scheduled `T3 + Hydra` path unchanged:
  - added a separate experimental runtime path instead of threading turbo behavior through the main scheduled implementation
  - new runtime entrypoint:
    - [mtl_tts_scheduled_turbo_s3.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/mtl_tts_scheduled_turbo_s3.py)
  - benchmark entrypoints now accept:
    - `--impl scheduled_turbo_s3`
    - optional `--turbo-s3-checkpoint-dir`
- completed the first same-stack benchmark for `scheduled + Hydra + turbo S3` on the newer cloud GPU box:
  - `c1`:
    - `audio_seconds_per_second=0.4147`
    - `stage_s3_s_mean=3.6241`
    - `stage_s3_token2mel_s_mean=2.2916`
    - `stage_audio_ready_s_mean=7.8628`
  - `c2`:
    - `audio_seconds_per_second=1.9271`
    - `stage_s3_s_mean=0.8822`
    - `stage_s3_token2mel_s_mean=0.6590`
    - `stage_audio_ready_s_mean=3.4680`
  - `c4`:
    - `audio_seconds_per_second=3.2184`
    - `stage_s3_s_mean=0.9584`
    - `stage_s3_token2mel_s_mean=0.6778`
    - `stage_audio_ready_s_mean=4.1290`
  - `c8`:
    - `audio_seconds_per_second=2.8878`
    - `stage_s3_s_mean=2.2461`
    - `stage_s3_token2mel_s_mean=1.7863`
    - `stage_audio_ready_s_mean=9.0648`
- recorded the main turbo `S3` read:
  - the major win is exactly where we expected it:
    - `token2mel`
  - `HiFT` stays a secondary cost
  - `turbo S3` materially reduces the downstream `S3` bottleneck without changing the current multilingual scheduled `T3 + Hydra` planner path
  - the strongest serving win is at `c2/c4`
  - `c8` still degrades relative to `c4`, but remains far better than the old non-turbo `S3`
- updated the current direction after the turbo `S3` experiments:
  - move forward with the scheduled `T3 + Hydra + turbo S3` stack as the main optimization branch
  - keep the old non-turbo `S3` numbers documented as the comparison baseline
  - later work should focus on:
    - audio-quality / contract validation for turbo `S3`
    - whether `c8` can be stabilized further
    - any remaining `T3` scheduler/orchestration overhead once the `S3` renderer is cheaper
- added [s3_shape_contract_flow.html](/Users/hisham/Code/Bahraini_TTS/architecture/s3_shape_contract_flow.html) to document the current `S3` contract shapes, Hydra-aware token flow, and `stage_s3_s` benchmarks
- updated [chatterbox_runtime_evolution.html](/Users/hisham/Code/Bahraini_TTS/architecture/chatterbox_runtime_evolution.html) to surface the new `TRACE_RUN_RESULTS` / tested-throughput numbers and the latest scheduled+Hydra+turbo-`S3` chapter
- created [t3_serving_stack_layering_memo_flow.html](/Users/hisham/Code/Bahraini_TTS/architecture/t3_serving_stack_layering_memo_flow.html) so the memo's layer model, current path, and option grid can be seen in a structured report format
- recorded the current `T3` scheduler scaling read from the selective stage timing breakdown:
  - the modeled Hydra compute pieces do **not** blow up with concurrency
  - `t3_hydra_verify_forward_s` and `t3_hydra_replay_forward_s` actually improve with batching
  - the red-flag `T3` runtime signal is instead `t3_wait_s`, which rises sharply by `c8`
  - current read:
    - Hydra math is not the main scaling failure
    - scheduler/orchestration overhead is a real next target
    - `S3` is now large enough to justify focused tracing as the next branch
- added a selective `S3`-only trace mode to the concurrency benchmark:
  - new CLI switch: `--trace-s3-shapes`
  - this leaves `T3` shape tracing off while still logging the `S3` contract
- restored the important `S3` shape outputs in a non-spammy way:
  - `token2mel.output`
  - `hift.input`
  - `hift.output`
  - `inference.output`
  - these are now logged once per run instead of flooding every request
- added [s3_shape_contract.md](/Users/hisham/Code/Bahraini_TTS/architecture/s3_shape_contract.md) as the first dedicated `S3` contract note with the canonical selective trace command and the current expected stage list
- threaded `Hydra` into the real `scheduled` runtime path instead of leaving it as a planner-only prototype:
  - scheduled runtime can now load a Hydra checkpoint and run speculative `T3` rounds inside the real scheduler
  - scheduler can split one cohort into successor cohorts when different requests accept different token counts
  - concurrency/runtime benchmark entrypoints now accept `--hydra-checkpoint-dir` and `--hydra-speculate-k`
- fixed the first scheduled+Hydra runtime bug:
  - cached Hydra verify/replay was incorrectly going through the HuggingFace backend wrapper
  - scheduled Hydra verify now uses the raw cached `T3` transformer path, matching the working single-request prototype contract
- completed the first end-to-end scheduled+Hydra concurrency run on the newer cloud GPU box:
  - `errors=[]` through `concurrency=8`
  - `stage_t3_acceptance_rate_mean` stayed at `0.6078` across `1/2/4/8`
  - `stage_t3_rounds_mean` stayed at `34`
- completed the first same-machine A/B against the current scheduled baseline on that newer cloud GPU box:
  - scheduled+Hydra `k3`:
    - `c1`: `audio_seconds_per_second=0.4685`, `stage_t3_s_mean=3.3776`, `stage_audio_ready_s_mean=6.9015`
    - `c2`: `audio_seconds_per_second=1.6016`, `stage_t3_s_mean=2.6818`, `stage_audio_ready_s_mean=4.2148`
    - `c4`: `audio_seconds_per_second=2.2456`, `stage_t3_s_mean=3.0249`, `stage_audio_ready_s_mean=5.9999`
    - `c8`: `audio_seconds_per_second=1.8320`, `stage_t3_s_mean=6.4019`, `stage_audio_ready_s_mean=14.5041`
  - scheduled baseline on the same box:
    - `c1`: `audio_seconds_per_second=0.4491`, `stage_t3_s_mean=6.6579`, `stage_audio_ready_s_mean=11.0511`
    - `c2`: `audio_seconds_per_second=1.2611`, `stage_t3_s_mean=5.9476`, `stage_audio_ready_s_mean=8.0791`
    - `c4`: `audio_seconds_per_second=1.4037`, `stage_t3_s_mean=11.3521`, `stage_audio_ready_s_mean=14.2960`
    - `c8`: `audio_seconds_per_second=1.9478`, `stage_t3_s_mean=12.2031`, `stage_audio_ready_s_mean=20.6349`
- updated the runtime read after the same-machine A/B:
  - scheduled+Hydra clearly reduces measured `T3` time on the new box
  - it improves total throughput at `c1/c2/c4`
  - it loses total throughput at `c8`
  - but the run is **not yet apples-to-apples correct**, because scheduled+Hydra produced shorter outputs on this prompt:
    - Hydra run: `81600` samples per request
    - scheduled baseline: `122880` samples per request
  - current interpretation:
    - runtime integration is now stable
    - performance looks promising
    - but output-length / decode-contract equivalence must be resolved before treating this as a final serving win
- built the first `Hydra` dataset on top of the best greedy Medusa corpus:
  - source dataset: [t3_medusa_distill_ar_short_40000_384_v5_greedy](/Users/hisham/Code/Bahraini_TTS/data/t3_medusa_distill_ar_short_40000_384_v5_greedy)
  - Hydra dataset: `data/t3_hydra_distill_ar_short_40000_v1`
  - effective training rows: `37400`
- added the first separate `Hydra` path for multilingual `T3`, split cleanly from `Medusa`:
  - dataset builder: [build_t3_hydra_distill_dataset.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/build_t3_hydra_distill_dataset.py)
  - trainer: [hydra_distill.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/train/hydra_distill.py)
  - train entrypoint: [train_t3_hydra.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/train_t3_hydra.py)
  - inference helper: [hydra_decode.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/inference/hydra_decode.py)
  - prototype benchmark: [benchmark_t3_hydra_prototype.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/benchmark_t3_hydra_prototype.py)
- kept the Hydra implementation `T3`-native instead of forcing the official text-LM Hydra dataset format:
  - Hydra dataset extends an existing Medusa-style corpus
  - builder emits per-sample planner hidden-state sidecars at the shifted teacher-forced `T3` boundary
  - trainer consumes logical planner hidden states shaped `(decode_len, 1024)`
  - benchmark stays separate from the Medusa prototype
- aligned the Hydra contract across builder, trainer, and inference after integration:
  - builder writes `safetensors` sidecars under `hydra_base_hidden_states/`
  - trainer reads those sidecars directly
  - grounded offsets now match the intended semantics:
    - base head predicts the current next token
    - Hydra head `0` predicts the token after that
    - later Hydra heads continue sequentially
- trained the first large `Hydra h2/l1` checkpoint:
  - run: `runs/t3_hydra_ar_short_40k_h2_run1/checkpoint_step_022910`
  - `eval_loss = 2.2706`
  - `eval_base_top1 = 0.6808`
  - `eval_hydra_head_0_top1 = 0.4787`
  - `eval_hydra_head_1_top1 = 0.3756`
- fixed the first Hydra inference bug in checkpoint loading:
  - Hydra heads were initially left on `cpu` during benchmark load
  - loader now moves the Hydra model onto the verifier device and forces `eval()`
- benchmarked the first Hydra checkpoint and established a new best speculative planner result:
  - `k2`:
    - `speedup = 18.88%`
    - `acceptance_rate = 0.7907`
    - `exact_token_match = true`
    - `rebuild_count = 0`
  - `k3`:
    - `speedup = 24.34%`
    - `acceptance_rate = 0.6078`
    - `exact_token_match = true`
    - `rebuild_count = 0`
  - current read:
    - Hydra is now ahead of the best Medusa result on this single-request planner benchmark
    - current best overall speculative setting is `Hydra h2` trained, infer with `k3`
- uploaded the current best Hydra checkpoint to the private Hugging Face model repo `Hishambarakat/hydra-chatterbox-t3-enhancement`
- kept the uploaded Hydra payload minimal so the downloaded snapshot can be used directly as `--hydra-checkpoint-dir`:
  - `README.md`
  - `t3_hydra_config.json`
  - `t3_hydra_heads.safetensors`
- updated [CLOUD_GPU_QUICKSTART.md](/Users/hisham/Code/Bahraini_TTS/CLOUD_GPU_QUICKSTART.md) with the canonical private-download flow for Hydra using `HYDRA_CHECKPOINT_DIR` and `huggingface_hub.snapshot_download(...)` from the `chatterbox-s3` env
- updated [CONTEXT.md](/Users/hisham/Code/Bahraini_TTS/CONTEXT.md) so later agents see the uploaded Hydra reference artifact and where to download it
- uploaded the current best Medusa checkpoint to the private Hugging Face model repo `Hishambarakat/TTS_Optimization`
- kept the uploaded payload minimal so the downloaded snapshot can be used directly as `--medusa-checkpoint-dir`:
  - `README.md`
  - `t3_medusa_config.json`
  - `t3_medusa_heads.safetensors`
- updated [CLOUD_GPU_QUICKSTART.md](/Users/hisham/Code/Bahraini_TTS/CLOUD_GPU_QUICKSTART.md) to point at the current best Medusa checkpoint `runs/t3_medusa_ar_short_40k_v5_greedy_h2_run1/checkpoint_step_022910` instead of the older `5k` run
- added the canonical private-download flow to [CLOUD_GPU_QUICKSTART.md](/Users/hisham/Code/Bahraini_TTS/CLOUD_GPU_QUICKSTART.md) using `huggingface_hub.snapshot_download(...)` from the `chatterbox-s3` env
- updated [CONTEXT.md](/Users/hisham/Code/Bahraini_TTS/CONTEXT.md) with a shared handoff note for the uploaded Medusa checkpoint, its benchmark status, and how later agents should download and use it
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
- updated [chatterbox_runtime_evolution.html](/Users/hisham/Code/Bahraini_TTS/architecture/chatterbox_runtime_evolution.html) again to include the new Hydra planner milestone, benchmark deltas (`k2/k3`), and the runtime-integration next step
- added a baseline-to-current concurrency performance ladder to [chatterbox_runtime_evolution.html](/Users/hisham/Code/Bahraini_TTS/architecture/chatterbox_runtime_evolution.html) so the starting point and each later serving gain stay visible in one place
- added [t3_shape_contract_flow.html](/Users/hisham/Code/Bahraini_TTS/architecture/t3_shape_contract_flow.html) as a simple T3-only flow board showing request-in, CFG row expansion, prefill shape, cached decode step, request-local state, CFG logit combine, and speech-token output
- synced [t3_shape_contract_flow.html](/Users/hisham/Code/Bahraini_TTS/architecture/t3_shape_contract_flow.html) to the latest traced contract so it now includes confirmed prefill logits, BOS positional shapes, speech-token vocab size, and first-layer prefill KV-cache shape
- added [t3_speculative_shape_contract_flow.html](/Users/hisham/Code/Bahraini_TTS/architecture/t3_speculative_shape_contract_flow.html) as the in-progress speculative T3 board showing the preserved scheduled prefill boundary, draft proposal path, verifier block contract, cache-growth invariant, and the current self-draft benchmark caution
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
- added [t3_speculative_decoding_research_memo.md](/Users/hisham/Code/Bahraini_TTS/architecture/t3_speculative_decoding_research_memo.md) with a Chatterbox-specific research pass on speculative decoding for the multilingual `T3` planner
- added [References/speculative_decoding/README.md](/Users/hisham/Code/Bahraini_TTS/References/speculative_decoding/README.md) plus a local PDF bundle for the primary speculative-decoding sources used in that memo
- added [t3_planner_rearchitecture_prior_art_memo.md](/Users/hisham/Code/Bahraini_TTS/architecture/t3_planner_rearchitecture_prior_art_memo.md) with a focused prior-art pass on replacing only the upstream `T3`-like planner while keeping the downstream renderer as fixed as possible
- added [References/planner_rearchitecture/README.md](/Users/hisham/Code/Bahraini_TTS/References/planner_rearchitecture/README.md) plus a local paper bundle for the planner-only / stage-local replacement literature
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
  - latest recorded post-rewrite checkpoints:
    - `c1`: `wall_s=4.4756`, `audio_seconds_per_second=0.992`
    - `c2`: `wall_s=5.3274`, `audio_seconds_per_second=1.5918`
    - `c4`: `wall_s=6.4274`, `audio_seconds_per_second=2.5951`
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
- completed a focused speculative-decoding research pass for the current multilingual `T3` architecture:
  - strong current read:
    - speculative decoding is mature in `LLM` serving
    - there is adjacent speech evidence from `Distil-Whisper`
    - but there is not strong evidence yet that it is already a standard open-source solution for `AR speech-token TTS planners`
  - best near-term candidate for this repo:
    - classic draft-and-verify with a smaller multilingual draft `T3`
  - important blocker:
    - existing `Chatterbox Turbo` is too architecturally mismatched to act as a direct draft model for the multilingual verifier
  - best long-term alternative if retraining is acceptable:
    - self-speculative / early-exit `T3` in the `LayerSkip` style
- completed a focused prior-art pass on `planner-only` or `stage-local` TTS acceleration:
  - strongest direct structural prior:
    - `SPEAR-TTS`, because it cleanly separates the planner-like stage from the downstream speaking/rendering stage
  - strongest planner-side speed priors in codec-LM TTS:
    - `VALL-E 2`
    - `VALL-E R`
  - strongest open-source non-AR token-planner prior:
    - `MaskGCT`
  - strongest stage-local but downstream-shifted analog:
    - `SoundStorm`
  - updated read:
    - people have already changed only one discrete-token generation stage while leaving downstream codec synthesis mostly intact
    - but a clean open-source multilingual `T3-only` swap into an existing `T3 -> S3` renderer contract still does not look common

## Current Focus

Immediate branch:

- keep the working Hydra-free `vLLM` spike as the active serving-migration branch
- validate quality on saved benchmark WAVs
- move from offline batched benchmarking toward a real staggered service-admission shape
- keep scheduled `T3 + Hydra + turbo S3` as the main custom-runtime comparison baseline

Broader project objective:

- streaming concurrency per GPU

Main KPI:

- `max concurrent streaming sessions per GPU at target latency`

Immediate milestone:

- make shared-engine service concurrency explicit and production-shaped on one GPU

Status:

- achieved in the `concurrent` A/B path first
- improved further in the `scheduled` A/B path
- correctness holds through `concurrency=4`
- correctness now also holds for the first batched `vLLM` spike at `concurrency=4`
- the scheduler has now been hardened and `VRAM` is measured
- per-stage timing now exists and shows `T3` is still the larger current limiter
- but the new `vLLM` spike changes the local read:
  - once `T3` is handed to a shared batched `vLLM` engine correctly, `T3` is no longer the dominant wall-time stage on the tested `c4` run
  - `S3` becomes the larger remaining end-to-end cost
- the new latency KPIs show `T3` first-token time is much better than full audio-ready time
- next target is to validate staggered arrivals with a real admission queue around the shared engine, then add true first-audio-chunk measurement
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
- stage timing still says active `T3` is the larger hot path on the custom scheduled branch
- the new `vLLM` spike refines that:
  - the earlier `vLLM` stall was not “one model per request”
  - it was the wrong offline API shape
  - after switching to one batched `generate(...)` call, `T3` became much cheaper than before on the tested `c4` run
- `S3` is still a secondary cost worth tracking, but not the first measured limiter
- on the current `vLLM c4` spike, `S3` is now the larger remaining wall-time stage
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
7. keep the `vLLM` spike as the main engine-migration feasibility branch
8. validate a staggered admission queue shape for the shared `vLLM` engine
9. profile deeper inside the downstream `S3` path now that batched `T3` is working
10. add true first-audio-chunk measurement before treating this as a production serving win

## Current Execution Path

- use [CLOUD_GPU_QUICKSTART.md](/Users/hisham/Code/Bahraini_TTS/CLOUD_GPU_QUICKSTART.md)
- use [GPU_MIGRATION_SERVING_PLAN.md](/Users/hisham/Code/Bahraini_TTS/GPU_MIGRATION_SERVING_PLAN.md) for the current `vLLM` spike path
- initialize only `external/chatterbox`
- use the forked `external/chatterbox` submodule directly
- replace PyPI Perth with Perth from source
- run [benchmark_multilingual_concurrency.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/benchmark_multilingual_concurrency.py) for `baseline`, `streaming`, `concurrent`, `scheduled`, and `vllm_turbo_s3`

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
- the new `vLLM` spike now proves the same higher-level service idea with a shared external engine:
  - independent request-local sessions can be admitted together
  - the benchmark can batch them into one shared `vLLM` `generate(...)` call
  - `stage_t3_batch_size_mean=4.0` on the tested `c4` run confirms the batch shape is real
- the first `vLLM` stall taught an important architecture lesson:
  - offline `vLLM` concurrency should be expressed as one batched request list
  - it should not be simulated by multiple Python threads calling the same offline `LLM.generate()` independently
- the current `vLLM` `c4` result is encouraging:
  - `wall_s=5.6751`
  - `audio_seconds_total=18.76`
  - `audio_seconds_per_second=3.3057`
  - `stage_t3_s_mean=0.9728`
  - current read: shared batched `T3` is working, and downstream `S3` is now the bigger remaining stage
- the remaining issue is now efficiency:
  - the scheduler now supports active-cohort rotation, but that still needs staggered-arrival validation
  - throughput now improves materially through `concurrency=4`
  - `VRAM` increase is now measured and not just guessed
  - on the custom scheduled branch, active `T3` still dominates `S3`
  - on the batched `vLLM` spike, the remaining large cost is `S3`
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
