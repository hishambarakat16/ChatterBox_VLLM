# T3 Engine Migration Memo

_Last updated: 2026-03-19_

## Scope

This memo evaluates whether the current multilingual `T3 + Hydra + turbo S3` stack should stay on the custom scheduled runtime or migrate the `T3` serving layer onto:

- `vLLM`
- `SGLang`
- `TensorRT-LLM`

The focus is narrow:

- `T3` only
- mixed-traffic scheduler behavior under realistic staggered arrivals
- `turbo S3` stays downstream
- `S3` is no longer treated as the primary bottleneck

Primary local inputs:

- [t3_shape_contract.md](/Users/hisham/Code/Bahraini_TTS/architecture/t3_shape_contract.md)
- [t3_mixed_traffic_scheduler_research_memo.md](/Users/hisham/Code/Bahraini_TTS/architecture/t3_mixed_traffic_scheduler_research_memo.md)
- [t3_serving_stack_layering_memo.md](/Users/hisham/Code/Bahraini_TTS/architecture/t3_serving_stack_layering_memo.md)
- [t3_scheduler.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/runtime/t3_scheduler.py)
- [worker_scheduled.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/runtime/worker_scheduled.py)
- [scheduled_decode.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/inference/scheduled_decode.py)
- [mtl_tts_scheduled.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/mtl_tts_scheduled.py)
- [mtl_tts_scheduled_turbo_s3.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/mtl_tts_scheduled_turbo_s3.py)
- [simulate_streaming_service.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/simulate_streaming_service.py)
- [benchmark_multilingual_concurrency.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/benchmark_multilingual_concurrency.py)

Primary official engine references:

- vLLM:
  - <https://docs.vllm.ai/en/latest/>
  - [external/vllm/docs/features/prompt_embeds.md](/Users/hisham/Code/Bahraini_TTS/external/vllm/docs/features/prompt_embeds.md)
  - [external/vllm/docs/configuration/optimization.md](/Users/hisham/Code/Bahraini_TTS/external/vllm/docs/configuration/optimization.md)
  - [external/vllm/docs/contributing/model/basic.md](/Users/hisham/Code/Bahraini_TTS/external/vllm/docs/contributing/model/basic.md)
  - [external/vllm/docs/features/speculative_decoding/README.md](/Users/hisham/Code/Bahraini_TTS/external/vllm/docs/features/speculative_decoding/README.md)
- SGLang:
  - <https://docs.sglang.ai/>
  - [external/sglang/docs/advanced_features/server_arguments.md](/Users/hisham/Code/Bahraini_TTS/external/sglang/docs/advanced_features/server_arguments.md)
  - [external/sglang/docs/advanced_features/speculative_decoding.md](/Users/hisham/Code/Bahraini_TTS/external/sglang/docs/advanced_features/speculative_decoding.md)
  - [external/sglang/docs/supported_models/extending/support_new_models.md](/Users/hisham/Code/Bahraini_TTS/external/sglang/docs/supported_models/extending/support_new_models.md)
  - [external/sglang/docs/supported_models/extending/transformers_fallback.md](/Users/hisham/Code/Bahraini_TTS/external/sglang/docs/supported_models/extending/transformers_fallback.md)
- TensorRT-LLM:
  - <https://nvidia.github.io/TensorRT-LLM/>
  - [external/TensorRT-LLM/docs/source/models/adding-new-model.md](/Users/hisham/Code/Bahraini_TTS/external/TensorRT-LLM/docs/source/models/adding-new-model.md)
  - [external/TensorRT-LLM/docs/source/torch/scheduler.md](/Users/hisham/Code/Bahraini_TTS/external/TensorRT-LLM/docs/source/torch/scheduler.md)
  - [external/TensorRT-LLM/docs/source/features/paged-attention-ifb-scheduler.md](/Users/hisham/Code/Bahraini_TTS/external/TensorRT-LLM/docs/source/features/paged-attention-ifb-scheduler.md)
  - [external/TensorRT-LLM/docs/source/features/speculative-decoding.md](/Users/hisham/Code/Bahraini_TTS/external/TensorRT-LLM/docs/source/features/speculative-decoding.md)

## Direct Answer

Most defensible migration order:

1. `vLLM` is the best **first feasibility target**
2. `SGLang` is the best **later optimization target**
3. `TensorRT-LLM` is **not recommended for the current migration stage**

Reason:

- `vLLM` gives the cleanest first external scheduler/runtime replacement with the least speculative-engine risk
- `SGLang` is stronger if we later want a more aggressive serving/runtime platform or a better long-term home for a rewritten speculative path
- `TensorRT-LLM` offers the deepest backend upside, but it requires the largest model-boundary rewrite and is the worst fit for the current `T3 + Hydra + CFG + speech-conditioning` boundary

Most important conclusion:

- none of the three engines is a drop-in replacement for the current `T3`
- the hard part is not generic batching
- the hard part is the current `T3` contract:
  - custom `t3_cond`
  - custom prompt-speech conditioning
  - CFG row duplication
  - Hydra verify/replay
  - speech-token EOS / filtering / multilingual setup

New migration-spike conclusion:

- `vLLM` is now proven as a feasible first engine target for the base multilingual `T3` path
- the first apparent multi-request `vLLM` failure was an integration-shape mistake:
  - we initially called the same offline `LLM.generate()` from multiple Python threads
  - the correct offline `vLLM` pattern is one batched `generate(...)` call containing many prompts
- once that was fixed, the `T3` stage batched correctly on the `RTX A6000` box:
  - `stage_t3_batch_size_mean=4.0`
  - `stage_t3_s_mean=0.9728`
  - `wall_s=5.6751`
  - `audio_seconds_per_second=3.3057`
- the batching shape still holds at larger batch sizes:
  - `stage_t3_batch_size_mean=16.0`
  - `stage_t3_s_mean=1.0512`
  - `wall_s=8.1052`
  - `audio_seconds_per_second=9.9096`
- the later `c16` A/B clarified a crucial nuance:
  - part of that earlier throughput number was inflated by bad lingering tail audio
  - once prefix caching was disabled for the custom prompt-embed path:
    - all rows emitted a real stop token
    - `wall_s` improved to `7.4000`
    - `mean_latency_s` improved to `5.8158`
    - `audio_seconds_total` dropped because the hallucinated tails disappeared
- updated local read:
  - one shared `vLLM` engine can express logical request concurrency through admission batching
  - this does **not** mean one model copy per request
  - after batched `T3` worked, downstream `S3` became the larger remaining wall-time stage on the tested `c4` run
  - the same admission rule also applies to the mixed-traffic simulator:
    - threaded `generate_with_session(...)` calls against the same offline engine are invalid
    - the simulator must queue arrivals and issue batched `generate_many_with_sessions(...)` cohorts instead
  - later simulator debugging exposed one more rule for the current spike:
    - mixed-shape prompt-embed service traffic is not yet stable on the compiled / CUDA-graph `vLLM` path
    - even after disabling prefix caching and fixing the threaded-call bug, a later singleton request with a different prompt/text shape could still trigger a CUDA device-side assert
    - current safe operating rule:
      - keep prefix caching disabled
      - use eager mode for mixed-traffic `vllm_turbo_s3` simulation
      - treat the compiled path as a fixed-shape benchmark path for now
  - however, stop-quality parity is still incomplete:
    - the current `vLLM` spike does not implement the original multilingual `AlignmentStreamAnalyzer`
    - that means some rows can hit the `max_new_tokens` cap instead of emitting a clean stop token
    - saved WAVs showed lingering noisy tails on some batched outputs
    - the later `c16` diagnostics narrowed that down further:
      - row `0` stopped naturally
      - rows `1..15` hit the `128` token cap
      - so the current failure pattern is batch-position-specific, not just generic decode drift
    - confirmed cause for this specific batch-row failure:
      - the custom prompt-embed path was not interacting correctly with `vLLM` prefix-cache reads for later identical rows
    - current operating rule:
      - keep prefix caching disabled by default for this `vLLM` path
    - current mitigation is only a fallback:
      - expose stop diagnostics per row
      - trim clearly repetitive suffixes when a row ends by length cap
    - this is not equivalent to full decode-time alignment-stop control

## Current Local T3 Boundary

## Current request path

```text
Client request
  -> app/session layer
  -> worker_scheduled.generate()
     -> clone conditionals
     -> text tokenize
     -> duplicate CFG rows
     -> add BOT/EOT
     -> ScheduledDecodeRequest
  -> T3DecodeScheduler
     -> admission window
     -> prompt-length grouping
     -> text-length bucket grouping
     -> active cohort rotation
  -> prepare_scheduled_cohort()
     -> build request-local state
     -> build prefill embeds
  -> advance_scheduled_cohort()
     -> prefill
     -> cached decode steps
     -> CFG combine
     -> optional Hydra propose / verify / replay
     -> stop on EOS or max tokens
  -> speech_tokens
  -> drop_invalid_tokens()
  -> turbo S3
  -> waveform
```

## Why this is not a standard LLM serving problem

The current `T3` boundary is not just `token_ids -> logits`.

It has four engine-hostile features:

1. `T3` depends on `t3_cond`, not just text tokens
2. one logical request becomes two rows because CFG duplicates cond/uncond inputs
3. Hydra is embedded inside the decode loop, not attached as a clean external speculator
4. the output is not natural-language text but speech tokens with custom stop and filtering behavior

Concrete local evidence:

- `worker_scheduled.generate()` duplicates text tokens for CFG before submit in [worker_scheduled.py:86](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/runtime/worker_scheduled.py#L86)
- the scheduler groups by `(text_len, prompt_len)` in [scheduled_decode.py:37](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/inference/scheduled_decode.py#L37) and [t3_scheduler.py:128](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/runtime/t3_scheduler.py#L128)
- `t3_cond` includes `speaker_emb`, `cond_prompt_speech_tokens`, and `emotion_adv` in [cond_enc.py:11](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/modules/cond_enc.py#L11)
- `prepare_conditioning()` converts prompt speech tokens into embeddings in [t3.py:95](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/t3.py#L95)
- `_cfg_combine_rows()` assumes paired cond/uncond rows in [scheduled_decode.py:155](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/inference/scheduled_decode.py#L155)
- Hydra proposal / verify / replay is deeply embedded in [scheduled_decode.py:607](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/inference/scheduled_decode.py#L607) and [scheduled_decode.py:790](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/inference/scheduled_decode.py#L790)

## Current ownership split

| Layer | Current owner | Notes |
| --- | --- | --- |
| App/session layer | custom | request setup, conditionals, tokenizer, `T3 -> S3` handoff |
| T3 scheduler/runtime | custom | `batching_window_ms`, bucketing, active cohorts, step loop |
| T3 model | custom | multilingual `T3`, CFG row semantics, custom conditioning |
| Speculative path | custom Hydra | verify/replay tied to current decode loop |
| Renderer | `turbo S3` | stable and no longer the main bottleneck |

## Re-engineering Problem Breakdown

Any migration must be evaluated in six buckets.

## 1. Thin adapter work

This is the code that should stay custom:

- app/session lifecycle
- WAV prompt -> conditionals
- tokenizer / punctuation normalization
- `speech_tokens -> turbo S3`
- metrics harnesses and service simulation

## 2. Scheduler/runtime replacement

This is the code an external engine would replace:

- [t3_scheduler.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/runtime/t3_scheduler.py)
- most of the scheduling and cohort-advancement logic in [scheduled_decode.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/inference/scheduled_decode.py)

## 3. Model boundary changes

This is the hardest part:

- representing `t3_cond`
- representing `cond_prompt_speech_tokens`
- representing `inputs_embeds`-first prefill
- preserving speech-token `LM head`
- preserving the current speech-token EOS behavior

## 4. Hydra compatibility

Current Hydra is not a clean engine plug-in.

It depends on:

- `next_logits`
- `next_hidden`
- request-local KV state
- verify/replay forwards through the same target model

That means Hydra is not a trivial “turn on built-in speculative decoding” feature in any of the three engines.

## 5. CFG compatibility

Current CFG is not a standard sampler flag. It is implemented by:

- expanding each logical request into two rows
- zeroing the uncond text row
- running both rows through the model
- recombining logits outside the model

This is a major migration tax.

## 6. Speech-token stop / multilingual conditioning

These must remain correct after migration:

- `stop_speech_token`
- `drop_invalid_tokens()`
- multilingual text tokenization
- prompt-speech conditioning
- speaker / emotion conditioning

## Option 1: vLLM

## High-level fit

`vLLM` is the best first external target because it gives:

- mature continuous batching
- chunked prefill
- paged KV management
- prompt-embeds support
- a documented custom-model porting path

Important official facts:

- prompt embeddings are officially supported in [prompt_embeds.md:1](/Users/hisham/Code/Bahraini_TTS/external/vllm/docs/features/prompt_embeds.md#L1)
- chunked prefill is enabled by default when possible in [optimization.md:41](/Users/hisham/Code/Bahraini_TTS/external/vllm/docs/configuration/optimization.md#L41)
- custom model porting requires custom model classes, flattened inputs, and possibly custom attention layers in [basic.md:14](/Users/hisham/Code/Bahraini_TTS/external/vllm/docs/contributing/model/basic.md#L14)
- speculative decoding is supported, but the feature matrix says `prompt-embeds x speculative decoding = ❌` in [features/README.md:39](/Users/hisham/Code/Bahraini_TTS/external/vllm/docs/features/README.md#L39)

That last point is decisive for Hydra planning.

## Proposed vLLM architecture

```text
Client
  -> custom session/app adapter
     -> short admission/batching window
     -> build request-local T3 conditioning
     -> build prefill prompt_embeds
  -> vLLM engine
     -> continuous batching
     -> decode-priority scheduling
     -> chunked prefill
     -> paged KV cache
     -> custom T3 model runner
  -> speech tokens
  -> custom filtering / stop accounting
  -> turbo S3
  -> waveform
```

Important clarification:

- for the offline `LLM` API, service-style concurrency should be expressed as:
  - many independent requests arrive
  - the adapter groups them into one batch
  - the batch is sent through one shared `vLLM` engine
  - outputs are then split back to the individual requests
- this is still legitimate customer-visible concurrency
- it is just implemented through admission batching rather than “N Python threads directly calling the same engine method at once”

## Thin adapter work

Keep:

- session creation
- voice prompt conditioning
- `MTLTokenizer`
- punctuation normalization
- `drop_invalid_tokens`
- `turbo S3`

Add:

- `vLLM` request builder for `T3`
- admission batching in front of the shared engine
- later, either:
  - a custom request queue around one shared engine, or
  - a move to `AsyncLLMEngine` / server-style integration for a true staggered online path
- precompute `prompt_embeds` for the prefill path
- output adapter from `vLLM` tokens back to current `speech_tokens`

## Scheduler/runtime replacement

`vLLM` would replace:

- [t3_scheduler.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/runtime/t3_scheduler.py)
- almost all cohort admission / active cohort rotation
- most batched prefill/decode stepping in [scheduled_decode.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/inference/scheduled_decode.py)

This is the cleanest part of the migration.

## Model boundary changes

Two viable shapes exist.

### Shape A: prompt-embeds first spike

The adapter precomputes:

- `cond_emb`
- `text_emb`
- BOS speech embed

and submits them as `prompt_embeds`.

Advantages:

- easiest way to preserve current `t3_cond` semantics without teaching `vLLM` a new request schema
- avoids forcing `t3_cond` into token IDs

Cost:

- first migration likely cannot use `Hydra`, because official `vLLM` docs mark `prompt-embeds` as incompatible with speculative decoding

### Shape B: deeper model-native port

Port `T3` into `vLLM` as a true custom model that accepts richer side inputs or a multimodal-style processor.

Advantages:

- better long-term shape
- less reliance on raw `prompt_embeds`
- potentially reopens the door to engine-native speculative decoding later

Cost:

- higher first-spike engineering risk

## Hydra compatibility

Recommendation: **defer Hydra for the vLLM first spike**

Reason:

- current Hydra is not one of `vLLM`’s standard speculator forms
- official docs support speculation, but the same official feature matrix marks `prompt-embeds` as incompatible with speculation
- current Hydra relies on internal hidden-state access and replay, which would fight the engine abstraction

If Hydra comes back later, it should be treated as one of:

- retrain/repackage as a `vLLM`-native speculator
- retrain as MTP/draft model
- abandon Hydra and keep the runtime gains only

## CFG compatibility

Recommendation: **defer CFG or run `cfg_weight = 0.0` for the first spike**

Reason:

- no native `vLLM` CFG primitive matches current paired-row semantics
- emulating current CFG means duplicating each request and recombining logits
- that would partially undo the throughput gains from the engine migration

Later options:

- custom paired-row model runner inside `vLLM`
- adapter-level paired requests with custom merge
- remove CFG permanently if quality allows

## Speech-token stop / multilingual conditioning concerns

These stay custom:

- `speech EOS` mapping
- `drop_invalid_tokens`
- multilingual text tokenization
- speaker / emotion / prompt-speech conditioning

The main migration question is only where that conditioning is turned into embeddings:

- in the adapter
- or inside a custom `vLLM` model

## What disappears

- [t3_scheduler.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/runtime/t3_scheduler.py)
- most of [scheduled_decode.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/inference/scheduled_decode.py)
- the T3-specific scheduling logic inside [worker_scheduled.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/runtime/worker_scheduled.py)

## What remains custom

- session/app layer
- condition-building path
- tokenizer path
- output filtering
- `turbo S3`
- streaming simulation and benchmark harnesses

## What must be rewritten

- new `vLLM`-side `T3` model wrapper
- request adapter
- stop/output integration
- any later CFG or Hydra path

## vLLM recommendation

- category: **first feasibility target**
- engineering difficulty: **medium-high**
- likely upside: **high**
- why: best balance between mature scheduler replacement and manageable first port

## Option 2: SGLang

## High-level fit

`SGLang` is the strongest later runtime platform if we want:

- richer scheduling controls
- stronger speculative runtime surface
- aggressive serving optimization
- a platform that already exposes more server policy knobs than the current custom scheduler

Important official facts:

- SGLang positions itself as a serving framework with continuous batching, chunked prefill, speculative decoding, paged attention, and prefill-decode disaggregation in [README.md:57](/Users/hisham/Code/Bahraini_TTS/external/sglang/README.md#L57)
- server/runtime knobs include `max-running-requests`, `max-queued-requests`, `chunked-prefill-size`, `schedule-policy`, and priority scheduling in [server_arguments.md:123](/Users/hisham/Code/Bahraini_TTS/external/sglang/docs/advanced_features/server_arguments.md#L123)
- SGLang has a documented new-model path and external model registration in [support_new_models.md:1](/Users/hisham/Code/Bahraini_TTS/external/sglang/docs/supported_models/extending/support_new_models.md#L1)
- SGLang also has a transformers fallback path in [transformers_fallback.md:1](/Users/hisham/Code/Bahraini_TTS/external/sglang/docs/supported_models/extending/transformers_fallback.md#L1)
- official speculative runtime is powerful, but it is framed around `EAGLE`, `MTP`, standalone draft models, and `NGRAM` in [speculative_decoding.md:1](/Users/hisham/Code/Bahraini_TTS/external/sglang/docs/advanced_features/speculative_decoding.md#L1)

## Proposed SGLang architecture

```text
Client
  -> custom session/app adapter
     -> build request-local T3 conditioning
  -> SGLang runtime
     -> continuous batching
     -> chunked prefill
     -> scheduling policy / queue caps
     -> custom T3 model or transformers fallback
  -> speech tokens
  -> custom filtering / stop accounting
  -> turbo S3
  -> waveform
```

## Thin adapter work

Keep:

- app/session layer
- voice conditioning
- tokenizer
- `turbo S3`

Add:

- SGLang engine/server adapter
- request serialization for `T3`
- output adapter back into current speech-token path

## Scheduler/runtime replacement

SGLang would replace:

- custom admission windowing
- cohort grouping
- active cohort round-robin policy
- much of the hand-written decode scheduling now inside [t3_scheduler.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/runtime/t3_scheduler.py)

This is attractive because mixed-traffic scheduling is exactly where the current pain lives.

## Model boundary changes

SGLang is more promising than it first appears.

Why:

- official new-model docs say most new language models are added with a single model file
- official docs explicitly describe porting a model from `vLLM` to `SGLang`
- SGLang model implementations already accept `input_embeds` in many places

But the port is still deeper than `vLLM` Shape A.

Expected shape:

- implement a native SGLang `T3` model class
- or first use transformers fallback if a HF-compatible wrapper is created
- teach the model path how to consume `t3_cond` or precomputed embeddings

This is real model porting work, not just an adapter.

## Hydra compatibility

Recommendation: **defer Hydra on the first SGLang migration**

Reason:

- SGLang’s speculation surface is rich, but it is not the same object as current Hydra
- current Hydra is a custom in-loop verifier/replay design, not a native SGLang draft model
- integrating current Hydra directly would mean bending SGLang around a custom speculation scheme instead of using the engine as intended

Longer-term, SGLang is the most plausible home if Hydra is rewritten into:

- MTP-style target heads
- an EAGLE-like draft path
- a real separate draft model

That is why SGLang is a strong later target, not the best first one.

## CFG compatibility

Recommendation: **defer CFG in the first port**

Same reason as `vLLM`:

- no drop-in equivalent for current paired-row CFG
- if we keep it, we either duplicate requests internally or rewrite the model forward path to hide the duplication

SGLang can probably tolerate a custom model-internal duplication strategy better than `vLLM`, but it is still nontrivial.

## Speech-token stop / multilingual conditioning concerns

These remain custom:

- speech EOS semantics
- invalid-token filtering
- multilingual tokenizer path
- voice/emotion/prompt conditioning

Most likely long-term path:

- a native SGLang `T3` model class that computes or consumes the conditioning inside the model boundary

## What disappears

- [t3_scheduler.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/runtime/t3_scheduler.py)
- most of scheduled cohort stepping in [scheduled_decode.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/inference/scheduled_decode.py)

## What remains custom

- app/session layer
- conditionals building
- tokenizer / multilingual normalization
- output filtering
- `turbo S3`

## What must be rewritten

- a native SGLang `T3` model path or fallback wrapper
- request adapter
- any later Hydra or CFG integration

## SGLang recommendation

- category: **later optimization target**
- engineering difficulty: **high**
- likely upside: **high to very high**
- why: best later target if we want a stronger runtime platform, but not the safest first port

## Option 3: TensorRT-LLM

## High-level fit

`TensorRT-LLM` is the highest-upside backend/runtime path and the worst current fit.

Important official facts:

- TensorRT-LLM supports in-flight batching / continuous batching, paged KV cache, and scheduling in [paged-attention-ifb-scheduler.md:1](/Users/hisham/Code/Bahraini_TTS/external/TensorRT-LLM/docs/source/features/paged-attention-ifb-scheduler.md#L1)
- its PyTorch backend scheduler is explicitly step-level and customizable in [torch/scheduler.md:1](/Users/hisham/Code/Bahraini_TTS/external/TensorRT-LLM/docs/source/torch/scheduler.md#L1)
- adding a new model requires new model configuration, model definition, weight loading, registration, and packed-input compatibility in [adding-new-model.md:1](/Users/hisham/Code/Bahraini_TTS/external/TensorRT-LLM/docs/source/models/adding-new-model.md#L1)
- official docs say IFB requires packed inputs and context-phase sequences must come before generation sequences in [paged-attention-ifb-scheduler.md:5](/Users/hisham/Code/Bahraini_TTS/external/TensorRT-LLM/docs/source/features/paged-attention-ifb-scheduler.md#L5)
- official speculative docs are powerful, but for `trtllm-serve` / `trtllm-bench` the PyTorch backend note says only `Eagle3` is supported there in [speculative-decoding.md:165](/Users/hisham/Code/Bahraini_TTS/external/TensorRT-LLM/docs/source/features/speculative-decoding.md#L165)

## Proposed TensorRT-LLM architecture

```text
Client
  -> custom session/app adapter
     -> pack request tensors + metadata
  -> TensorRT-LLM runtime
     -> IFB scheduler
     -> packed prefill / generation batches
     -> paged KV cache
     -> custom T3 DecoderModelForCausalLM
  -> speech tokens
  -> custom filtering / stop accounting
  -> turbo S3
  -> waveform
```

## Thin adapter work

Adapter work is small relative to the rest, but it is not the main problem.

The real cost is the model port and runtime integration.

## Scheduler/runtime replacement

TensorRT-LLM could replace the current scheduler very effectively.

But this is not enough by itself, because the runtime assumes:

- packed no-padding execution
- explicit runtime metadata
- a model rewritten to TensorRT-LLM attention/runtime contracts

## Model boundary changes

This is the main blocker.

To run `T3` inside TensorRT-LLM, we would need:

- a TensorRT-LLM model configuration for `T3`
- a TensorRT-LLM decoder model definition
- correct packed-input behavior
- correct attention metadata flow
- a weight-loading path from current Chatterbox weights
- a correct speech-token LM head

This is a real engine port, not an adapter.

## Hydra compatibility

Recommendation: **drop Hydra for the current TensorRT-LLM migration idea**

Reason:

- current Hydra is not aligned with the engine’s standard speculation path
- official docs are strongest around `Eagle3`, `draft-target`, `NGram`, `PARD`, `SA`, and some model-specific MTP
- current Hydra checkpoints would need major redesign or retraining to fit TensorRT-LLM speculation cleanly

There is a `UserProvidedDecodingConfig` in the LLM API, but building current Hydra into that path is still a large systems project, not a practical first migration.

## CFG compatibility

Recommendation: **treat CFG as hostile to a first TensorRT-LLM port**

Why:

- current CFG doubles rows per logical request
- TensorRT-LLM IFB is most efficient with tightly packed request tokens
- hiding cond/uncond duplication inside the model or scheduler would add substantial complexity to the packed execution path

If TensorRT-LLM is ever pursued, the likely first move is:

- `cfg_weight = 0.0`
- no Hydra
- simplest greedy or ordinary sampling only

## Speech-token stop / multilingual conditioning concerns

These stay custom, but TensorRT-LLM makes them harder, not easier, because the request path becomes more rigid:

- packed request tensors
- attention metadata
- engine-managed scheduling

This is the least flexible place to preserve the current `t3_cond` contract.

## What disappears

- the current custom `T3` scheduler
- most custom cohort logic

## What remains custom

- app/session layer
- tokenizer / multilingual setup
- `turbo S3`
- speech-token stop/filter behavior

## What must be rewritten

- almost the entire `T3` serving boundary
- model port
- runtime integration
- likely much of the speculation path

## TensorRT-LLM recommendation

- category: **not recommended for the current migration stage**
- engineering difficulty: **very high**
- likely upside: **very high later, poor immediate ROI now**
- why: best considered only after the `T3` boundary is simplified and stabilized

## Comparison Table

| Option | Thin adapter work | Scheduler/runtime replacement | Model boundary changes | Hydra | CFG | Speech-token / multilingual concerns | What disappears | What stays custom | Difficulty | Likely upside | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `vLLM` | moderate | strong fit | medium-high | defer | defer or disable first | manageable if conditioning becomes `prompt_embeds` or a custom model input | current custom `T3` scheduler and most cohort stepping | app/session, conditionals, tokenizer, `turbo S3`, filtering | medium-high | high | first feasibility target |
| `SGLang` | moderate | very strong fit | high | defer first, maybe later rewrite into native speculation | defer first | manageable but best with a native SGLang `T3` model | current custom `T3` scheduler and most cohort stepping | app/session, conditionals, tokenizer, `turbo S3`, filtering | high | high to very high | later optimization target |
| `TensorRT-LLM` | small relative to total work | very strong fit | very high | drop for now | disable first | hardest fit because of packed runtime and custom side inputs | current custom `T3` scheduler | app/session, tokenizer, `turbo S3`, filtering | very high | very high only later | not recommended now |

## Recommended Migration Order

## Stage 0: keep current custom stack while mixed-traffic fixes continue

Do not throw away the current scheduler work yet.

Reason:

- it already captures the current `T3` contract correctly
- it is still the best correctness reference
- it is the easiest place to keep benchmarking mixed-traffic behavior

## Stage 1: first external spike on vLLM

Target:

- one external-engine `T3` path
- no Hydra
- `cfg_weight = 0.0`
- `turbo S3` unchanged

Reason:

- this isolates the core question:
  - is the current scheduling problem mostly solved by a mature external engine once we stop carrying Hydra and CFG?

## Stage 2: decide whether to stay on vLLM or move toward SGLang

If `vLLM` spike wins materially:

- keep `vLLM`
- reintroduce features selectively

If `vLLM` is too constraining:

- use what we learned to port the simplified `T3` to `SGLang`

## Stage 3: only then revisit speculation

At this point choose one:

- keep no-Hydra if scheduler/runtime win is already enough
- retrain Hydra into an engine-friendly speculator
- switch to a different speculator family entirely

## Stage 4: consider TensorRT-LLM only after the model boundary is simplified

Do this only if:

- `T3` model boundary is stable
- Hydra is removed or fully redesigned
- CFG is removed or re-expressed in an engine-friendly way

## Minimal First Spike Plan For The Best Option

## Best option: `vLLM`

The minimal useful spike is not “full parity”.

The minimal useful spike is:

- external engine owns scheduling
- current custom app/session and `turbo S3` stay intact
- one simplified `T3` path proves whether a mature serving engine fixes mixed-traffic behavior

## First-spike target architecture

```text
Current:
  custom app/session
    -> custom T3 scheduler
    -> custom T3 decode loop
    -> turbo S3

Spike:
  custom app/session
    -> vLLM adapter
    -> vLLM scheduler/runtime
    -> simplified T3 model
    -> turbo S3
```

## First-spike rules

Keep:

- multilingual tokenizer
- current session/conditioning layer
- current `turbo S3`
- current speech-token filtering and benchmarking harnesses

Disable:

- Hydra
- CFG
- alignment guard extras that are not required for basic correctness

Preserve:

- exact `t3_cond` semantics
- same speech-token EOS
- same output token vocabulary

## Suggested implementation steps

1. Build a minimal HF-like `T3` wrapper around the current backbone.
   The wrapper should expose:
   - `inputs_embeds` prefill
   - speech-token `embed_input_ids`
   - speech-token LM head

2. Build a `vLLM` custom model around that wrapper.
   Follow the official `vLLM` custom model rules:
   - `prefix` arguments
   - flattened inputs
   - weight loading logic

3. Keep conditioning outside the engine for the first spike.
   The adapter should precompute:
   - `cond_emb`
   - `text_emb`
   - BOS speech embed
   - final `prompt_embeds`

4. Submit one request as `prompt_embeds`, then let `vLLM` run decode.

5. Map output speech tokens back into the current downstream path:
   - speech EOS
   - `drop_invalid_tokens`
   - `turbo S3`

6. Re-run the existing mixed-traffic simulation and benchmark tools.

## Success criteria for the first spike

Minimum success:

- same speech-token vocabulary and EOS semantics
- valid waveform end-to-end through `turbo S3`
- no regressions in correctness on simple Arabic prompts
- better mixed-traffic stability than the custom scheduler baseline

What does not need to be true yet:

- Hydra parity
- CFG parity
- exact audio parity on every sample
- perfect prompt-cache reuse

## Why this is the right first spike

- smallest external-engine experiment that still answers the real serving question
- preserves the expensive downstream `turbo S3` integration work
- avoids locking the migration to the current Hydra design
- produces a clean branch point:
  - stay on `vLLM`
  - move later to `SGLang`
  - or abandon engine migration and continue custom scheduler work

## Bottom Line

- `vLLM` is the best first external-engine experiment
- `SGLang` is the best later runtime target if we want a stronger long-term platform
- `TensorRT-LLM` is too invasive for the current `T3` boundary
- Hydra should be **deferred** in any first migration
- CFG should also be **deferred or disabled** in any first migration
- the first useful external-engine spike is:
  - multilingual `T3`
  - no Hydra
  - no CFG
  - `turbo S3` unchanged
  - benchmark mixed-traffic behavior directly
