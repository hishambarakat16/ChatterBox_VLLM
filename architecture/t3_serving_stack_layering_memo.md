# T3 Serving Stack Layering Memo

_Last updated: 2026-03-19_

## Scope

This memo explains how `vLLM`, `SGLang`, and `TensorRT-LLM` relate to the current multilingual `T3 + Hydra + turbo S3` stack.

The main goal is to answer:

- which layer each system belongs to
- which combinations are valid
- what the `T3` request path would look like before and after migration
- which option is the most mature for this codebase

## Direct Answer

You do **not** normally stack all three on the same request path.

The normal production pattern is:

- choose **one primary serving engine** for `T3`
- keep your app/runtime as a **thin adapter**
- keep `turbo S3` downstream unless you later replace that too

The practical choices are:

1. keep the custom scheduler and improve it
2. replace the `T3` scheduler/runtime with `vLLM`
3. replace the `T3` scheduler/runtime with `SGLang`
4. replace the `T3` scheduler/runtime with `TensorRT-LLM`

What is usually **not** done:

- `vLLM` on top of `SGLang`
- `SGLang` on top of `vLLM`
- `vLLM` on top of `TensorRT-LLM` as the main serving path for the same model

Those systems are mostly **alternatives**, not layers that all need to be combined.

## Layer Model

Think of the serving stack in four layers:

| Layer | Responsibility | Current owner | Candidate replacements |
| --- | --- | --- | --- |
| App / Adapter | accept requests, session setup, `T3 -> S3` handoff | custom Chatterbox runtime | keep custom |
| Scheduling / Serving Policy | continuous batching, request admission, rebatching, fairness, prefill/decode policy | custom `T3` scheduler | `vLLM`, `SGLang`, `TensorRT-LLM` |
| Execution Backend | kernels, KV cache, CUDA graphs, inflight batching, overlap | PyTorch + custom runtime | `TensorRT-LLM`, parts of `vLLM`, parts of `SGLang` |
| Renderer | speech tokens -> mel -> waveform | `turbo S3` | keep current for now |

Important correction:

- `TensorRT-LLM` is not only a low-level backend
- it also has its own serving/runtime features such as request scheduling, IFB, paged attention, and overlap scheduling

So in practice:

- `vLLM` and `SGLang` are primarily **full serving engines**
- `TensorRT-LLM` is both a **serving engine** and an **NVIDIA-optimized backend/runtime**

## Current T3 Path

Today the path is:

```text
Client
  -> custom service adapter
  -> custom T3 scheduler
  -> T3 + Hydra decode
  -> speech tokens
  -> turbo S3
  -> waveform
```

The main current weakness is the `custom T3 scheduler`, not `turbo S3`.

## Future Path Options

## Option A: Keep Custom Scheduler, Improve Policy

```text
Client
  -> custom service adapter
  -> improved custom T3 scheduler
  -> T3 + Hydra decode
  -> speech tokens
  -> turbo S3
  -> waveform
```

What changes:

- better admission policy
- continuous-batching-style behavior
- active cohort merge / rebatching
- decode-priority scheduling

Pros:

- lowest integration risk
- keeps all current `CFG`, Hydra, alignment, and speech-stop semantics local
- no forced model-port immediately

Cons:

- more scheduler engineering
- still limited by the custom runtime until it becomes much more mature

## Option B: Replace T3 Serving Layer With vLLM

```text
Client
  -> thin Chatterbox adapter
  -> vLLM engine
  -> ported T3 + Hydra decode
  -> speech tokens
  -> turbo S3
  -> waveform
```

What the adapter does:

- build request inputs
- collect compatible requests over a short admission window
- submit the resulting batch to one shared `vLLM` engine
- receive generated speech tokens
- call `turbo S3`

What disappears:

- most of the current custom `T3` scheduler logic

Pros:

- most mature general serving reference
- continuous batching, chunked prefill, KV management, streaming lifecycle already built
- the current local spike now confirms that this can work with the multilingual base `T3` path when the benchmark expresses concurrency as one batched `generate(...)` call

Cons:

- `T3` is not a standard text-only LLM path
- Hydra speculative flow and `CFG` duplication may require nontrivial engine work
- a true staggered online service still needs an admission queue or async-server style integration, not just the offline `LLM` class

## What Concurrency Means On vLLM

For this repo, the practical service meaning is:

- many customer requests can arrive independently
- each request still keeps its own session/state
- a front-side adapter catches arrivals over a short window
- it groups compatible requests into one batch
- that batch goes to one shared `vLLM` engine
- outputs are split back to the individual requests

That is still real logical concurrency from the product perspective.

It is just not “one separate model instance per customer request.”

Current local evidence from the `vLLM` spike:

- the shared `T3/vLLM` batch reached `stage_t3_batch_size_mean=4.0`
- `stage_t3_s_mean=0.9728`
- `wall_s=5.6751`
- `audio_seconds_per_second=3.3057`
- the same pattern continued at `c16`:
  - `stage_t3_batch_size_mean=16.0`
  - `stage_t3_s_mean=1.0512`
  - `wall_s=8.1052`
  - `audio_seconds_per_second=9.9096`

So the current read is:

- one shared engine can already serve multiple logical requests efficiently
- after `T3` batching is fixed, the next larger remaining cost is downstream `S3`
- but quality parity is not done yet:
  - the current `vLLM` path does not carry over the original multilingual alignment-based EOS controller
  - some batched rows therefore run into the token cap and produce lingering noisy tails
  - the strongest observed failure shape is batch-position-specific:
    - row `0` stops naturally
    - later rows in the same identical batch hit the token cap
  - that makes prefix-cache interaction in the custom prompt-embed path a concrete next suspect
  - the current code now exposes stop diagnostics and applies a conservative repetitive-tail trim for length-capped rows, but that is still a mitigation rather than true parity

## Option C: Replace T3 Serving Layer With SGLang

```text
Client
  -> thin Chatterbox adapter
  -> SGLang runtime
  -> ported T3 + Hydra decode
  -> speech tokens
  -> turbo S3
  -> waveform
```

Pros:

- strong runtime design
- very strong modern serving features
- router and PD-disaggregation ecosystem is attractive later

Cons:

- less conservative choice than `vLLM`
- still requires model/runtime porting for `T3 + Hydra`

## Option D: Replace T3 Serving Layer With TensorRT-LLM

```text
Client
  -> thin Chatterbox adapter
  -> TensorRT-LLM runtime
  -> ported/compiled T3 + Hydra decode
  -> speech tokens
  -> turbo S3
  -> waveform
```

Pros:

- strongest NVIDIA-focused performance path
- built-in IFB, request scheduling, paged attention, overlap scheduling, CUDA graph style optimization

Cons:

- highest model-porting cost
- likely hardest path for custom `T3 + Hydra + CFG`
- best after the model boundary is made more engine-friendly

## What Can Be Combined

## Valid / Common Combinations

### 1. Custom app + vLLM

Use when:

- `vLLM` owns serving and batching
- your app remains a thin front-end plus `S3` handoff layer

### 2. Custom app + SGLang

Use when:

- `SGLang` owns serving and batching
- your app still does session handling and `S3`

### 3. Custom app + TensorRT-LLM

Use when:

- `TensorRT-LLM` owns both serving/runtime and backend optimization
- your app becomes a request adapter plus `S3` handoff

### 4. Higher-level orchestrator routing across multiple engines

Use when:

- different models or replicas are served by different runtimes
- a router or platform decides where traffic goes

Example:

- `OME` can manage `SGLang`, `vLLM`, and `TensorRT-LLM` as runtime choices

This is orchestration across backends, not “all three inside one request path.”

## Usually Not Worth Doing

### 1. Keep current scheduler and only add TensorRT-LLM kernels

This may improve raw execution efficiency, but it does **not** solve the core scheduler-fragmentation problem by itself.

### 2. Run vLLM and SGLang together for the same request path

These are competing serving engines. One should usually own the request lifecycle.

### 3. Stack all three on the same inference path

This usually creates more integration complexity than benefit.

## Which Option Is Most Mature

If the question is “which is the safest general serving baseline?”:

- `vLLM`

If the question is “which has the strongest modern runtime/scheduler design?”:

- `SGLang`

If the question is “which is the strongest NVIDIA-specific performance target?”:

- `TensorRT-LLM`

## Practical Difference Between vLLM, SGLang, and TensorRT-LLM

| System | Best thought of as | Main gain for this repo | Why you would choose it | Main risk for this repo |
| --- | --- | --- | --- | --- |
| `vLLM` | mature general-purpose serving engine | strongest near-term reduction in scheduler engineering risk | continuous batching, PagedAttention, chunked prefill, CUDA/HIP graph execution, broad ecosystem maturity | custom `T3 + Hydra + CFG` port may still be nontrivial |
| `SGLang` | modern high-performance serving/runtime system | strongest alternative if you want a more aggressive runtime stack and richer serving features | continuous batching, router/gateway support, PD disaggregation, HiCache, speculative-decoding ecosystem, strong observability and runtime features | less conservative migration target, more moving parts |
| `TensorRT-LLM` | NVIDIA-optimized serving runtime plus backend | highest upside on pure backend efficiency once the model boundary is engine-friendly | inflight batching, paged attention, chunked prefill, overlap scheduler, quantization, speculative decoding, strong NVIDIA optimization path | highest porting cost and most likely to force model/runtime refactors |

## What SGLang Gives You That vLLM Usually Does Not

The most meaningful `SGLang`-leaning features for this repo are:

- router / gateway ecosystem for multi-backend serving
- PD disaggregation and related serving patterns
- HiCache / hierarchical KV caching features
- strong speculative-decoding support and ecosystem alignment
- a more runtime-centric design philosophy

That is why `SGLang` is the more aggressive choice:

- it gives you more serving/runtime machinery
- but also asks you to accept more migration complexity and more decisions

## What vLLM Gives You Over SGLang

The most meaningful `vLLM`-leaning advantages for this repo are:

- the clearest “safe first engine” story
- a very mature continuous-batching mental model
- broad adoption and easier baseline comparability
- a strong serving default without forcing as many runtime choices up front

That is why `vLLM` is the conservative first target:

- less flashy
- more predictable as a first feasibility spike

## What TensorRT-LLM Gives You That The Others Usually Do Not

The most meaningful `TensorRT-LLM`-leaning advantages for this repo are:

- the strongest NVIDIA-specific execution path
- highly optimized backend behavior on supported hardware
- overlap scheduler and inflight batching integrated with backend execution
- very strong later-stage optimization path once the model/runtime boundary is stable

That is why `TensorRT-LLM` is usually the “performance-max” target rather than the “first migration” target.

## Expected Improvement Shape

These are engineering estimates for this repo, not promises from vendor benchmarks.

| Option | Likely near-term win | Likely longer-term ceiling |
| --- | --- | --- |
| better custom scheduler | medium | medium |
| `vLLM` migration if feasible | medium to high | high |
| `SGLang` migration if feasible | medium to high | high |
| `TensorRT-LLM` migration if feasible | low to medium at first due to porting cost, then potentially very high | very high on NVIDIA |

Interpretation:

- `vLLM` and `SGLang` are most compelling when the current problem is scheduler shape
- `TensorRT-LLM` is most compelling when the current problem has shifted toward backend execution efficiency after the scheduler shape is already sane

## Practical Ranking For This Repo

| Rank | Option | Why |
| --- | --- | --- |
| 1 | keep custom app + improve scheduler policy | lowest risk, fastest path to learn, no immediate model-port |
| 2 | feasibility spike for `vLLM` | best maturity/reference point for serving replacement |
| 3 | feasibility spike for `SGLang` | strong alternative if runtime flexibility matters more |
| 4 | `TensorRT-LLM` migration later | strongest backend path, highest model-port cost |

## What The Scheduler Does In Each Option

## Today

The scheduler does:

- request admission
- cohort creation
- decode-step scheduling
- fairness implicitly via round-robin
- `T3` lifecycle ownership

## If vLLM/SGLang/TensorRT-LLM Own T3

Your custom scheduler mostly becomes unnecessary.

Your local code would mainly do:

- session creation / prompt conditioning
- translate request into engine input format
- submit request
- collect returned speech tokens
- hand off tokens to `turbo S3`

So the role becomes:

- **adapter**, not **scheduler**

## What Still Remains Custom Even After Migration

Even with an external serving engine, you still need local code for:

- multilingual session conditioning
- `T3` request construction
- speech-token postprocessing
- `turbo S3` invocation
- end-to-end service API
- evaluation and profiling

So the architecture does **not** become engine-only. It becomes:

- engine for `T3`
- custom glue around it

## Current Recommendation

For this codebase, the most defensible near-term sequence is:

1. finish learning from the custom scheduler path
2. stop over-investing in long admission-window tuning
3. treat `vLLM` as the first serving-engine feasibility target
4. treat `SGLang` as the second serving-engine feasibility target
5. treat `TensorRT-LLM` as the high-performance NVIDIA path once the `T3` execution boundary is cleaner

In other words:

- do **not** assume you need all three
- do **not** assume `TensorRT-LLM` must be first
- do **not** assume the custom scheduler should survive forever

The likely end state is:

- one primary `T3` serving engine
- one thin custom Chatterbox adapter
- one `turbo S3` renderer stage

## Recommended Next Document

The next useful artifact after this memo is an HTML or diagram version with three side-by-side flows:

1. current custom scheduler flow
2. `vLLM`-owned `T3` flow
3. `TensorRT-LLM`-owned `T3` flow

That will make the migration boundary much easier to reason about visually.

## Sources

- [T3 Mixed Traffic Scheduler Research Memo](/Users/hisham/Code/Bahraini_TTS/architecture/t3_mixed_traffic_scheduler_research_memo.md)
- [vLLM docs](https://docs.vllm.ai/en/v0.10.0/)
- [vLLM site](https://vllm.ai/)
- [SGLang docs](https://docs.sglang.ai/)
- [SGLang router docs](https://docs.sglang.ai/router/router.html)
- [SGLang OME docs](https://docs.sglang.ai/ome/)
- [TensorRT-LLM overview](https://nvidia.github.io/TensorRT-LLM/latest/overview.html)
- [TensorRT-LLM LLM API](https://nvidia.github.io/TensorRT-LLM/llm-api/)
- [TensorRT-LLM overlap scheduler](https://nvidia.github.io/TensorRT-LLM/1.0.0rc2/torch/features/overlap_scheduler.html)
