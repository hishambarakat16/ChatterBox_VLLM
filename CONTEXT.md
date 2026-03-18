# Bahraini TTS — Current Context

## Current Goal

Immediate active branch:

- record the `T3` stage-timing read and come back to the scheduler/orchestration overhead later
- shift the immediate tracing/debugging target from `T3` to `S3`
- build the same kind of concrete shape contract for `S3` that already exists for `T3`
- keep the current `Hydra` scheduled runtime path in place while tracing only the downstream `S3` side

Broader project goal:

- make the `Chatterbox`-style stack better for `streaming concurrency`

The main KPI is:

- `max concurrent streaming sessions per GPU at target latency`

Support metrics:

- `p95 first-chunk latency`
- `p95 inter-chunk latency`
- `VRAM per active stream`

Immediate Hydra milestone:

- keep the first Hydra training/benchmark result as the new planner baseline
- integrate Hydra into the scheduled runtime path: done
- measure whether the single-request planner win carries over into concurrency: partially done
- resolve the new runtime finding:
  - scheduled+Hydra is stable through `concurrency=8`
  - but it currently emits shorter outputs than scheduled baseline on the same prompt
- only revisit architecture/training again after that runtime equivalence check

Broader serving milestone:

- make `2` simultaneous requests complete correctly on one shared model instance
- treat truncated outputs and silent early-stop outputs as failures, even if Python does not raise

Status:

- the separate Hydra build/train/inference scaffolding exists locally in `external/chatterbox`
- the first Hydra dataset has already been built from the best greedy Medusa corpus
- the first Hydra `h2/l1` checkpoint has already been trained:
  - `runs/t3_hydra_ar_short_40k_h2_run1/checkpoint_step_022910`
  - `eval_base_top1 = 0.6808`
  - `eval_hydra_head_0_top1 = 0.4787`
  - `eval_hydra_head_1_top1 = 0.3756`
- the current best Hydra checkpoint is now uploaded as a reference artifact:
  - private Hugging Face model repo: `Hishambarakat/hydra-chatterbox-t3-enhancement`
  - uploaded payload: `README.md`, `t3_hydra_config.json`, `t3_hydra_heads.safetensors`
  - `CLOUD_GPU_QUICKSTART.md` now includes the canonical `HYDRA_CHECKPOINT_DIR` download flow using `huggingface_hub.snapshot_download(...)` from the `chatterbox-s3` env
- the first Hydra speculative benchmarks are complete:
  - `k2`: `speedup = 18.88%`, `acceptance = 0.7907`, `exact_token_match = true`, `rebuild_count = 0`
  - `k3`: `speedup = 24.34%`, `acceptance = 0.6078`, `exact_token_match = true`, `rebuild_count = 0`
- current read:
  - Hydra is now ahead of the best Medusa result on the single-request planner benchmark
  - the new best speculative setting is Hydra `h2` trained, infer with `k3`
  - runtime integration is now implemented in the scheduled path
  - the first scheduled+Hydra concurrency run on the newer cloud GPU completed with `errors=[]` through `concurrency=8`
  - measured planner stats remained stable under scheduler load:
    - `stage_t3_acceptance_rate_mean = 0.6078`
    - `stage_t3_rounds_mean = 34`
  - same-machine A/B against scheduled baseline on the newer cloud GPU shows:
    - scheduled+Hydra improves measured `T3` time at every tested concurrency
    - scheduled+Hydra improves total throughput at `c1/c2/c4`
    - scheduled+Hydra loses total throughput at `c8`
  - but this is not yet a clean end-to-end win because the outputs are shorter:
    - scheduled+Hydra: `81600` samples
    - scheduled baseline: `122880` samples
- current next step is therefore not more planner training; it is decode-contract / output-equivalence debugging inside the scheduled Hydra path
- current side branch:
  - the `T3` stage timing breakdown now shows:
    - `hydra_verify_forward` and `hydra_replay_forward` do not scale badly
    - `t3_wait_s` is the suspicious orchestration signal at `c8`
    - `S3` is large enough to justify focused tracing next
  - a selective `S3` trace mode now exists in the concurrency benchmark:
    - `--trace-s3-shapes`
  - `architecture/s3_shape_contract.md` is now the new downstream debugging anchor
- achieved first in the `concurrent` A/B runtime path using request-local `T3` decode state plus a coarse full-decode `T3` lock
- improved further in the new `scheduled` A/B runtime path using batched `T3` cohorts
- validated as correct through `concurrency=4`
- the hardened scheduler now exists and VRAM is measured
- stage timing now exists and points to active `T3` compute as the larger current limiter
- current next step is to validate staggered arrivals and then profile `T3` further before blaming `S3`

## Current Baseline

The baseline is the current open-source `Chatterbox` multilingual stack.

Current mental model:

```text
text
  -> multilingual tokenizer
  -> T3 speech-token LM
  -> S3 token-to-mel decoder
  -> vocoder
  -> waveform
```

We are treating the current implementation as the reference system to beat.

Serving-shape visual:

- [chatterbox_serving_shape_current_vs_target.html](/Users/hisham/Code/Bahraini_TTS/architecture/chatterbox_serving_shape_current_vs_target.html)
- [chatterbox_runtime_evolution.html](/Users/hisham/Code/Bahraini_TTS/architecture/chatterbox_runtime_evolution.html)
- [t3_shape_contract_flow.html](/Users/hisham/Code/Bahraini_TTS/architecture/t3_shape_contract_flow.html)
- [CLOUD_GPU_QUICKSTART.md](/Users/hisham/Code/Bahraini_TTS/CLOUD_GPU_QUICKSTART.md)
- [CHATTERBOX_STATE_FLOW.md](/Users/hisham/Code/Bahraini_TTS/CHATTERBOX_STATE_FLOW.md)
- [TRACE_RUN_RESULTS.md](/Users/hisham/Code/Bahraini_TTS/TRACE_RUN_RESULTS.md)

## What We Know

### 1. The stack is serial twice

- `T3` generates speech tokens autoregressively
- `S3` decodes those tokens with iterative flow

This is the core structural reason concurrency is hard.

### 2. The current runtime is not request-safe

In `mtl_tts.py`, the model instance stores and mutates shared `self.conds`.

That is bad for concurrent serving.

The current issue is therefore:

- runtime architecture problem
- plus serial model architecture problem

Not just one slow function.

There was also a separate baseline environment issue:

- on the tested `4060 Ti` env, the PyPI Perth package exposed `perth.PerthImplicitWatermarker` as `None`
- reinstalling Perth from source fixed that
- that was a dependency/runtime issue, not evidence against the streaming runtime work

Earlier benchmark result:

- both `baseline` and the current `streaming` wrapper break logically or structurally at `concurrency >= 2`
- the wrapper improved session-state isolation, but did not make the shared `T3` inference path safe
- the first concrete milestone is therefore not "scale hard", but "make `2` simultaneous requests correct"

The strongest current suspect is `T3.inference()`:

- it resets `self.compiled = False` per call
- rebuilds `AlignmentStreamAnalyzer`
- rebuilds `self.patched_model`
- stores those objects back on the shared `T3` instance

That means concurrent requests can still stomp on shared inference state even after the new session wrapper.

New validated result:

- the new `concurrent` runtime path completes `concurrency=2` with `errors=[]`
- both saved waveforms sounded correct on manual listening
- the first-pass fix works by:
  - moving `T3` backend/analyzer state into request-local objects
  - keeping shared weights shared
  - putting a coarse full-decode lock around `T3`

Current read:

- the original shared-state correctness bug is fixed for `concurrency=2`
- the remaining problem is now latency/throughput efficiency, not immediate correctness
- the new `concurrent` path also completes `concurrency=4` with `errors=[]`
- but throughput gain is still weak because `T3` is effectively queued behind a coarse full-decode lock
- the new `scheduled` path now batches multiple separate requests together for `T3` and is the current best validated runtime shape
- trace evidence confirms that `2` separate requests were actually grouped into one `T3` cohort:
  - `run_cohort requests 2`
  - `prefill.batch inputs_embeds (4, 72, 1024)`
- the scheduler keeps shared weights shared while keeping each request's mutable decode state separate
- the hardened scheduler now also keeps active cohorts and round-robins them, so new requests can enter the scheduler while older cohorts are still decoding
- current timing-enabled live benchmark read:
  - `concurrency=2` materially improves over `1`
  - `concurrency=4` also improves materially over `2`
  - GPU usage is clearly higher than before
  - scheduler wait is tiny under simultaneous arrivals, so the current limit is not simple queueing

### 3. T3 still looks like the current hot path

- Chatterbox README says `speech-token -> mel` was the bottleneck
- `S3` still does mel-space iterative decoding
- the decoder works on the longer mel timeline, not the shorter token timeline

But the latest timing-enabled run changes the current read:

- `T3` wait time is tiny under simultaneous arrivals
- active `T3` compute is still larger than `S3`
- so the current performance limit is still more `T3` than `S3`

Current order:

- first fix `T3` concurrency correctness for `2` simultaneous requests
- then profile and reduce `S3` serving cost

Updated order:

- `T3` correctness at `2` simultaneous requests: done
- `concurrency=4` correctness: also stable
- coarse full-decode `T3` serialization: replaced by the new `scheduled` path for same-shape cohorts
- next isolate where throughput is still being lost:
  - staggered-arrival / dynamic-admission behavior
  - then deeper `T3` cost under the less-serialized front half
  - then `S3` cost after that
- note:
  - under the old `concurrent` path, `S3` was not being stress-tested cleanly because `T3` was still queued behind a coarse lock
  - under the new timing-enabled `scheduled` path, `T3` still dominates `S3` in the current measurements

### 4. Chatterbox S3 comes from the CosyVoice family

Useful lineage:

- `Matcha-TTS` -> flow-matching acoustic decoder idea
- `CosyVoice` -> speech-token conditioning + prompt mel + speaker conditioning
- `Chatterbox S3` -> adapted from CosyVoice-style token-to-mel design

`CosyVoice 3` is a later improvement in the same family, but it still keeps:

- AR speech-token generation
- iterative flow decoding
- separate vocoder

So it is a better family member, not a full structural fix.

## Current Non-Goals

These are intentionally out of scope right now:

- Bahraini front end work
- Arabic-only specialization
- tokenizer redesign
- speech-token interface redesign
- quality tuning as the main objective

They can come back later. They are not the current task.

## Current Implementation Direction

Repo strategy:

- use `external/chatterbox/` as the working fork
- keep upstream file paths visible as baseline references
- duplicate only the files we actually need to change

Concrete fork plan:

- [CHATTERBOX_FORK_IMPLEMENTATION_PLAN.md](/Users/hisham/Code/Bahraini_TTS/CHATTERBOX_FORK_IMPLEMENTATION_PLAN.md)

### Phase 1: Fix the runtime shape

- remove shared mutable request state
- make per-request / per-session conditionals explicit
- define a streaming session abstraction
- make the runtime concurrency-safe

Current Layer 1 artifacts already exist locally:

- [mtl_tts_streaming.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/mtl_tts_streaming.py)
- [runtime/session.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/runtime/session.py)
- [runtime/types.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/runtime/types.py)
- [runtime/worker.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/runtime/worker.py)
- [compare_multilingual_runtime.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/compare_multilingual_runtime.py)
- [benchmark_multilingual_concurrency.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/benchmark_multilingual_concurrency.py)

Important current repo fact:

- these runtime changes live inside the local `external/chatterbox` submodule worktree
- the preferred execution path is now the forked `external/chatterbox` submodule plus quickstart
- primary artifact:
  - [CLOUD_GPU_QUICKSTART.md](/Users/hisham/Code/Bahraini_TTS/CLOUD_GPU_QUICKSTART.md)
- the patch file remains only as a fallback transport artifact

Current validated baseline smoke result:

- see [TRACE_RUN_RESULTS.md](/Users/hisham/Code/Bahraini_TTS/TRACE_RUN_RESULTS.md)

Current validated Layer 1 streaming-runtime smoke result:

- see [TRACE_RUN_RESULTS.md](/Users/hisham/Code/Bahraini_TTS/TRACE_RUN_RESULTS.md)

Immediate interpretation:

- Layer 1 runtime is functionally working
- it is slower than baseline on this single-request smoke test
- this does not yet answer the concurrency question
- the traced single-request flow now confirms the tensor/state path is sane before concurrency is introduced

The target runtime shape is:

- shared worker owns read-only model weights and helpers
- session object owns request conditionals, caches, and decode progress
- request-local `T3` decode path owns backend/analyzer state for each request
- one scheduler per shared `T3` worker batches compatible requests together

Current measured scheduler result:

- `scheduled c1` throughput: `1.0369 audio_seconds_per_second`
- `scheduled c2` throughput: `1.767 audio_seconds_per_second`
- `scheduled c4` throughput: `2.8324 audio_seconds_per_second`
- `scheduled c8` throughput: `3.2907 audio_seconds_per_second`
- compared with the coarse-lock `concurrent` path, that is:
  - about `+21.3%` at `c1`
  - about `+56.9%` at `c2`
  - about `+129.5%` at `c4`

Current operating-point read:

- `c1 -> c2` gives about `+70.4%` throughput
- `c2 -> c4` gives about `+60.3%` throughput
- `c4 -> c8` gives only about `+16.2%` throughput
- so the scheduler still scales through `c8`, but the latency cost gets much steeper after `c4`

Current measured VRAM read:

- `c1` peak allocated: `3514.9 MB`
- `c2` peak allocated: `3951.3 MB`
- `c4` peak allocated: `4713.0 MB`
- `c8` peak allocated: `6272.6 MB`
- memory is growing with active request state, as expected
- but on this `16 GB` card, VRAM is not the current hard limit

Current measured stage read:

- `c1`:
  - `T3 total = 3.5733s`
  - `S3 = 0.606s`
- `c2`:
  - `T3 total mean = 3.6417s`
  - `S3 mean = 0.9104s`
- `c4`:
  - `T3 total mean = 3.7658s`
  - `S3 mean = 1.4759s`
- `c8`:
  - `T3 total mean = 6.3571s`
  - `S3 mean = 2.2454s`
- `T3` wait time is tiny:
  - `c2 mean = 0.0112s`
  - `c4 mean = 0.0123s`
  - `c8 mean = 0.0276s`
- so the remaining limit is not scheduler queueing under simultaneous arrivals
- the new latency-KPI read is:
  - `c2 T3 first token mean = 56.5 ms`
  - `c4 T3 first token mean = 105.0 ms`
  - `c8 T3 first token mean = 368.0 ms`
  - `c2 audio ready mean = 4.5553s`
  - `c4 audio ready mean = 5.2462s`
  - `c8 audio ready mean = 8.6152s`
- so:
  - `T3` first-token latency is decent at `c2` and still near target at `c4`
  - but the current full-audio path is still far from low-latency streaming because audio is only ready seconds later

Current alignment-guard read:

- we briefly added analyzer benchmarking toggles and an alignment sweep to test whether the `T3` attention-based guardrail could be weakened or removed
- the practical result was clear:
  - `alignment off` produced long rambling tails, silence/noise, and garbled late speech
  - `inspect every 2` also degraded quality
  - disabling the `long_tail` force-EOS rule was clearly bad on the tested prompt
- current conclusion:
  - the scheduled alignment guard is doing real quality work
  - the current safe production assumption is still:
    - analyzer on
    - inspect every step
    - keep the existing EOS guard policies enabled
- the temporary alignment experiment knobs were removed after this conclusion so the runtime stays focused on the validated path
- latest implementation step:
  - the scheduled analyzer was rewritten to keep its rolling state on GPU instead of copying attention to CPU and growing a full CPU-side alignment matrix every decode step
  - the guard heuristics stayed the same in intent:
    - same selected heads
    - same EOS suppression
    - same long-tail / repetition forcing logic
  - but the state now keeps only rolling GPU-local summaries instead of a full accumulated alignment history
- latest benchmark read after that rewrite:
  - manual listening stayed clean
  - `errors=[]` still held through `concurrency=8`
  - the clearest win was at `c8`:
    - `wall_s`: `11.0954 -> 9.5139`
    - `audio_seconds_per_second`: `3.1941 -> 3.4518`
    - `stage_t3_s_mean`: `6.9425 -> 5.6515`
    - `stage_t3_first_token_s_mean`: `0.2016 -> 0.1561`
- cautious interpretation:
  - this removed a real chunk of scheduled-guard overhead
  - but it did not remove the deeper `output_attentions=True` cost
  - the next likely structural limiter inside the guard path is still the attention fallback itself
- isolated `T3` microbenchmark result:
  - `output_attentions=True` does impose a real decode-time tax
  - at `concurrency=8`, `decode_steps=64`, the isolated `T3` backend showed:
    - `prefill_overhead_pct = 1.16%`
    - `decode_overhead_pct = 14.83%`
    - `total_t3_overhead_pct = 13.71%`
- updated read after that A/B:
  - attention output is a meaningful cost
  - but it is not large enough by itself to explain the whole utilization gap
  - the deeper remaining issue is still the shape of autoregressive decode:
    - tiny per-step query length
    - CFG doubling the effective rows
    - many small decode steps instead of one large GPU-friendly workload

Important clarification:

- if four separate requests arrive with the same batch key, the scheduler can batch those four requests together for `T3`
- it is not "one request has four internal lanes"
- it is "four separate requests progress together inside one shared `T3` batch"
- the original first-pass scheduler ran a same-shape cohort to completion
- the hardened scheduler now admits new requests while older cohorts are still active
- but the current simultaneous-arrival benchmark does not fully prove how much that dynamic admission helps yet

### Phase 2: Improve streaming efficiency

- done first-pass:
  - replace the coarse full-decode `T3` lock with a cohort-based `T3` scheduler
- next:
  - validate the hardened scheduler with staggered-arrival benchmarks
  - profile deeper inside `T3`, since `T3` still dominates total compute in the current timing split
  - keep the alignment guardrail enabled while profiling, since the experiments showed it is necessary for output quality
  - treat the new GPU-local scheduled guard as the current best version of the analyzer path
  - next deeper guard question is no longer CPU copies/history growth, but whether `output_attentions=True` can be made cheaper or replaced
  - but the broader `T3` utilization question is now clearer:
    - the remaining bottleneck is not just the guard
    - it is also the underlying autoregressive decode shape itself
  - add true first-audio-chunk measurement once partial audio emission exists
  - only then decide whether `S3` becomes the next real bottleneck
  - keep tracking GPU utilization and `VRAM`
- step active requests through `T3` in a more concurrency-friendly way
- only then isolate `S3` as the next decoder hot path

### Phase 3: Re-evaluate architecture

If the runtime is request-safe but concurrency is still poor:

- decide whether S3 must be replaced
- decide whether T3 autoregression must also be reduced

## Current Medusa Checkpoint Status

The speculative-decoding / Medusa side path now has a published reference artifact for the
current best checkpoint.

Current best uploaded checkpoint:

- local run: `runs/t3_medusa_ar_short_40k_v5_greedy_h2_run1`
- local checkpoint: `runs/t3_medusa_ar_short_40k_v5_greedy_h2_run1/checkpoint_step_022910`
- private Hugging Face model repo: `Hishambarakat/TTS_Optimization`
- uploaded payload is intentionally minimal:
  - `README.md`
  - `t3_medusa_config.json`
  - `t3_medusa_heads.safetensors`
- this is a Medusa-heads checkpoint only, not a standalone full multilingual TTS model

Current best known Medusa training / serving read:

- dataset family: `data/t3_medusa_distill_ar_short_40000_384_v5_greedy`
- Medusa training shape: `h2` (`medusa_heads=2`, `medusa_layers=1`)
- frozen base: `true`
- best checkpoint config read:
  - `epochs = 5`
  - `lr = 3e-4`
  - `batch_size = 8`
  - `global_step = 22910`
- current best serving tradeoff is still:
  - train with `h2`
  - infer with `--speculate-k 2`
- current best benchmark read for that checkpoint:
  - `speedup = 14.09%`
  - `acceptance_rate = 0.7326`
  - `exact_token_match = true`
  - `rebuild_count = 0`

Operational note for other agents:

- `CLOUD_GPU_QUICKSTART.md` has been updated to point at this exact checkpoint, not the older `5k` run
- the quickstart now includes:
  - the current best training command
  - a private Hugging Face download step
  - the exact speculative benchmark command for this checkpoint
- the canonical local variable name in the quickstart is:
  - `MEDUSA_CHECKPOINT_DIR=$PWD/models/t3_medusa_ar_short_40k_v5_greedy_h2_checkpoint_step_022910`
- the download flow is:
  - export `HF_TOKEN`
  - use `huggingface_hub.snapshot_download(...)` from the `chatterbox-s3` env
  - allow only `README.md`, `t3_medusa_config.json`, and `t3_medusa_heads.safetensors`
  - pass the downloaded folder directly as `--medusa-checkpoint-dir`

This uploaded checkpoint is now the reference artifact to use when someone asks for:

- the best current Medusa checkpoint
- how to download the checkpoint on a new GPU box
- how to reproduce the current best `k2` speculative benchmark

## Current Decision

The shortest path is:

1. treat current Chatterbox as baseline
2. validate the new Layer 1 runtime path on GPU using the forked submodule + quickstart flow
3. compare baseline vs new runtime path under simultaneous requests
4. make `2` simultaneous requests work correctly on one shared model instance
5. treat `concurrency=4` stability as proof of correctness, not proof of scalability
6. design the next `T3` scheduling step
7. only then decide how much of the remaining bottleneck belongs to `S3`

Anything outside that path is context bloat for now.
