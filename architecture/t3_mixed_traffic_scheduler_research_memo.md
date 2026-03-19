# T3 Mixed-Traffic Scheduler Research Memo

_Last updated: 2026-03-19_

## Scope

This memo presents the current research findings for the multilingual `T3 + Hydra + turbo S3` serving stack after `turbo S3` reduced the downstream renderer cost enough that `T3` scheduling became the dominant remaining systems bottleneck.

This note is specifically about:

- staggered arrivals
- mixed-length traffic
- one shared `T3` worker on one GPU
- request-local decode state
- scheduler policy under realistic load

This note is not primarily about:

- `S3` quality or `S3` acceleration
- vocoder acceleration
- model-quality changes
- speculative-decoding theory in general

It is about the scheduler shape now that the current stack is closer to a production-serving problem than a pure model-inference problem.

## Executive Summary

The current failure mode is not best understood as “`T3` is slow.”

It is better understood as:

- staggered arrivals create small windows of overlap
- exact text-length matching is too strict
- requests fragment into singleton or tiny cohorts
- many active cohorts are then round-robined
- submit-to-finish latency inflates sharply
- GPU work becomes structurally inefficient even if individual kernels are correct

The highest-ROI path is:

1. keep the custom `T3` scheduler
2. widen admission enough to capture real overlap
3. batch by coarse buckets with padding tolerance, not exact text length
4. cap active cohorts
5. prioritize decode-heavy active cohorts over spawning too many new ones
6. later add safe step-boundary rebatching / merge

The strongest prior art does not come from TTS-native serving systems. It comes from LLM-serving systems:

- `Orca`
- `vLLM`
- `Sarathi-Serve`
- `FastServe`
- `SGLang`
- `TensorRT-LLM`
- `DistServe`
- `Llumnix`

The best practical interpretation for this repo is:

- do not replace the whole runtime with a generic serving engine yet
- do borrow the scheduler policy ideas from those systems
- do treat the current problem as continuous-batching fragmentation under mixed traffic

## Direct Answer

For the current codebase, the best next optimization route is a scheduler-policy upgrade around the existing `T3` boundary, not a full serving-engine migration and not a raw GPU-concurrency push.

If forced into one sentence:

> Keep the custom `T3` scheduler, make it behave more like `Orca/vLLM/Sarathi`, and only consider deeper runtime/backend replacement later if the improved scheduler policy still leaves large losses.

## Local Problem Statement

Current production-shaped problem:

- requests arrive around every `250 ms`
- the batching admission window was too narrow
- exact length matching caused requests to miss each other
- most requests formed singleton cohorts
- many tiny active cohorts were then advanced in round-robin order
- `T3` submit-to-finish time inflated badly
- `S3` stayed stable enough that the main remaining bottleneck moved upstream to `T3`

This means the current problem is primarily scheduler shape, not just low-level kernel efficiency.

The wrong mental model would be:

- “we just need more GPU overlap”

The better mental model is:

- “we need to increase useful batch density over time while avoiding queueing pathologies”

## Why Existing LLM-Serving Work Applies

Although this is a TTS stack, the `T3` planner is serving a very LLM-like workload:

- autoregressive decode
- per-request mutable decode state
- shared immutable weights
- heterogeneous request lengths
- staggered arrivals
- a batching opportunity that changes over time

That is why LLM-serving literature is highly relevant here.

The nearest transferable ideas are:

- iteration-level scheduling
- continuous batching
- chunked prefill
- request-local KV/cache state
- fairness-aware active queue management
- active-batch compaction / rebatching

The parts that remain more speech-specific are:

- `CFG` duplication
- alignment guardrails
- speech-token stop conditions
- `T3 -> turbo S3` handoff behavior

So the core scheduling problem is not novel, but its exact constraints in this TTS stack are not a trivial drop-in of an off-the-shelf engine either.

## Prior-Art Findings

## 1. Orca

Most important idea:

- iteration-level scheduling instead of request-level run-to-completion scheduling

Why it matters:

- it is the conceptual origin of the shift from “whole request batches” to “active requests sharing decode steps”
- it directly addresses the inefficiency of letting different requests monopolize the worker independently

Why it maps to local `T3`:

- your current mixed-traffic failure is exactly what happens when the runtime lacks a good step-level scheduling policy under staggered arrivals

What to borrow:

- schedule at decode-step granularity
- batch compatible active requests dynamically
- avoid treating each request as a self-contained exclusive execution unit

Practical value:

- very high conceptual value
- lower direct implementation specificity than `vLLM` or `Sarathi-Serve`

Reference:

- `Orca: A Distributed Serving System for Transformer-Based Generative Models`

## 2. vLLM

Most important ideas:

- continuous batching
- request-local KV state
- chunked prefill
- practical serving-engine API around `add_request()` plus iterative engine `step()`

Why it matters:

- it is the most mature practical reference for how active-request scheduling should feel operationally
- it turns the abstract Orca scheduling idea into a stable serving architecture

Why it maps to local `T3`:

- the current stack already has a request-local decode-state mindset
- what is missing is a better policy for admission and active cohort evolution under mixed-length traffic

What to borrow:

- a scheduler should think in token budgets, not just request counts
- decode requests often deserve priority over fresh long prefills
- chunking long prefills is often better than letting them stall active decode traffic

Practical value:

- highest practical policy reference
- strongest template for request lifecycle and scheduler ownership

Limitations for direct adoption:

- current `T3` is not a plain engine-compatible text-only model boundary
- `CFG`, alignment logic, and speech stop rules are custom

References:

- `vLLM: Easy, Fast, and Cheap LLM Serving with PagedAttention`
- official optimization docs

## 3. Sarathi-Serve

Most important ideas:

- chunked prefill
- decode-aware scheduling
- minimizing prefill interference with active decoding

Why it matters:

- this is the strongest paper for the exact “mixed short and long requests under latency constraints” problem
- it addresses the case where long arrivals poison latency by consuming too much attention budget at the wrong time

Why it maps to local `T3`:

- once requests are staggered and have different lengths, the scheduler needs to decide whether to keep decode moving or admit more prefill
- that is the exact tradeoff Sarathi-Serve studies

What to borrow:

- give ongoing decode traffic priority
- chunk long prefills instead of letting them monopolize service
- measure latency/throughput tradeoff under realistic arrival patterns, not just simultaneous starts

Published results that matter:

- the paper reports substantial serving-capacity improvements under latency constraints versus `vLLM`

Practical value:

- strongest policy reference for your current next step

Reference:

- `Sarathi-Serve: Taming Throughput-Latency Trade-off in LLM Inference with Chunked Prefills`

## 4. FastServe

Most important ideas:

- preemptive scheduling
- queueing-aware policy
- explicit optimization of completion time and tail behavior

Why it matters:

- once active cohorts diverge enough, pure round-robin is usually not the best policy
- some active work is more valuable to keep moving than other work

Why it maps to local `T3`:

- your runtime already has active cohorts
- the next scheduler step after fixing admission is deciding how to prioritize them

What to borrow:

- fairness-aware prioritization
- willingness to reduce naive fairness if it improves job completion time materially
- treat scheduler choice as a policy problem, not only a batching problem

Practical value:

- very useful for later-stage policy design
- not necessarily the first thing to implement before admission cleanup

Reference:

- `Fast Distributed Inference Serving for Large Language Models`

## 5. SGLang

Most important ideas:

- low-overhead scheduler/runtime design
- continuous batching
- prefix-aware serving concepts

Why it matters:

- it shows what a production-serving engine looks like when scheduling overhead itself is treated as a first-class systems problem
- it is also one of the clearest examples of these ideas crossing into real TTS deployments indirectly

Why it maps to local `T3`:

- the current codebase should care not just about model work but about scheduler overhead, CPU overhead, and batching friction

What to borrow:

- keep the scheduler lightweight
- minimize host-side overhead around active-request management
- avoid building elaborate policies that destroy their own gains

Practical value:

- strong runtime-design reference

Reference:

- `SGLang` paper and docs

## 6. TensorRT-LLM

Most important ideas:

- inflight batching
- request scheduling
- chunked context
- overlap scheduler
- backend-level performance tools once the serving pattern stabilizes

Why it matters:

- it is highly relevant if the current `T3` boundary later becomes backend-friendly enough for a more optimized execution layer

Why it maps to local `T3`:

- after the scheduler policy is stabilized, backend execution efficiency may become the next limit

What to borrow:

- request scheduling abstractions
- shape stabilization for graph capture
- overlap only when profiling shows real headroom

Practical value:

- strong later-stage optimization reference
- less useful as the first answer to the current singleton-fragmentation issue

Reference:

- TensorRT-LLM docs

## 7. DistServe and Llumnix

Most important ideas:

- separate prefill and decode service
- multi-instance load rebalancing
- KV-aware migration / disaggregation

Why they matter:

- they show what comes next when single-worker policy tuning is no longer enough

Why they are lower priority locally:

- current evidence still points to a single-worker scheduler-policy problem
- jumping to multi-instance/disaggregated serving now would likely add too much complexity too early

Practical value:

- future architecture references, not immediate next steps

References:

- `DistServe`
- `Llumnix`

## Ranked Options For This Stack

Expected impact below is an engineering estimate for this specific stack and workload shape. It is not a direct claim from any one paper.

| Rank | Option | Why it fits this stack | Expected impact | Engineering complexity | Quality / correctness risk | Main operational risk |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Wider admission window plus coarse length bucketing | Directly attacks singleton fragmentation | High, often the largest immediate win | Low to medium | Low | Early requests may wait slightly longer if the window is too wide |
| 2 | `max_active_cohorts` plus fill-existing-cohort bias | Prevents active-cohort explosion | Medium to high | Medium | Low | Starvation if there is no age escape |
| 3 | Decode-priority scheduling | Protects active decode from long arrivals | Medium | Medium | Low | May delay admission for very long requests |
| 4 | Step-boundary rebatching / active cohort merge | Fixes later-stage underfilled active cohorts | Medium to high | High | Medium | State management bugs and harder debugging |
| 5 | Chunked prefill for long requests | Good under long/short traffic mixes | Medium | Medium to high | Low | More scheduler complexity |
| 6 | Fairness / aging / short-job bias | Improves tail behavior and starvation resistance | Medium for latency, low for throughput | Medium | Low | Can lower average throughput if over-applied |
| 7 | CUDA graphs / backend stabilization | Good once shapes stabilize | Medium later | Medium to high | Low | Premature optimization before scheduler shape settles |
| 8 | Multi-instance / disaggregated serving | Future architecture option | Potentially high later | High | Medium | Too much complexity too early |
| 9 | More CUDA streams on one worker | Usually not the answer first | Low or negative in this phase | Medium | Low | Oversubscription and fragmented batches |

## Detailed Recommendation For This Codebase

## Recommendation 1: widen admission and use coarse buckets

This should be the first production change to validate.

Reasoning:

- current problem begins before active scheduling even starts
- once requests miss each other at admission time, the rest of the scheduler is already operating on bad structure
- exact-length purity is not worth the fragmentation cost under staggered traffic

Suggested policy:

- bucket on coarse prompt/text length ranges
- allow padding within a bounded tolerance
- log padding waste explicitly

What success looks like:

- singleton rate drops
- mean cohort size rises
- submit-to-finish time drops
- throughput rises even if some padding overhead appears

## Recommendation 2: add `max_active_cohorts`

This is the most important guardrail after admission cleanup.

Reasoning:

- without a cap, any burst of staggered requests can create too many tiny active groups
- round-robin across too many tiny cohorts destroys decode efficiency

Suggested policy:

- keep a hard or soft cap on simultaneously active cohorts
- when the cap is hit, bias toward filling existing compatible cohorts
- allow an age-based escape hatch so old requests are eventually admitted

What success looks like:

- active cohort count stays bounded
- throughput is more stable under bursty traffic
- tail latency stops exploding as load rises

## Recommendation 3: add decode-priority scheduling

This is the next scheduler policy change after the cohort structure becomes reasonable.

Reasoning:

- long prefills can harm decode-heavy traffic disproportionately
- active decode cohorts often give better latency return than admitting another large fresh prefill immediately

Suggested policy:

- prioritize active decode cohorts
- fit fresh prefills into the remaining budget
- consider chunking large prefills if needed

What success looks like:

- less latency inflation under long/short mixed traffic
- better submit-to-first-token for already-active requests

## Recommendation 4: add step-boundary merge / rebatching

This is probably the best high-effort optimization after the earlier policy fixes.

Reasoning:

- even if admission is better, requests still diverge over time
- fixed cohorts lose density as requests finish or drift apart
- step-boundary merge is the natural way to restore density

Suggested policy:

- at safe boundaries, merge underfilled cohorts that are close enough in shape/progress
- do not rebatch every step if that makes scheduler overhead dominate

What success looks like:

- later-stage cohort density stays higher
- long mixed workloads degrade more gracefully

## Recommendation 5: add fairness only after the throughput policy is sane

Reasoning:

- fairness matters, but throughput policy is the current blocker
- applying fairness too early can lock in an inefficient baseline

Suggested policy:

- age-based admission overrides
- optional short-job bias if tail behavior gets bad
- monitor `p95` and `p99`, not just mean metrics

## What To Avoid

These are the main anti-patterns suggested by both the local failure and the serving literature:

- exact text-length equality as the primary batching rule
- unlimited active cohorts
- pure round-robin without regard to batch density or request age
- many simultaneous GPU streams for tiny decode groups
- large architecture changes before the single-worker scheduler policy is validated
- judging scheduler quality only with simultaneous-start benchmarks

## Custom Scheduler Versus Existing Engines

## Why keeping the custom scheduler is the right call

The current `T3` stack already has local behavior that makes a full off-the-shelf engine swap unattractive right now:

- `CFG` duplication is custom
- alignment guardrails are custom
- speech-token stopping semantics are custom
- handoff into `turbo S3` is custom
- request-local decode state has already been shaped around this runtime

So the practical split is:

- keep the local scheduler and runtime ownership
- borrow policy designs from mature serving systems

## When `vLLM` / `SGLang` / `TensorRT-LLM` are useful

### `vLLM`

Best use now:

- serving-policy reference
- request-lifecycle reference
- chunked-prefill reference

Best use later:

- backend inspiration if the planner boundary gets simpler

### `SGLang`

Best use now:

- low-overhead scheduler design reference
- continuous-batching behavior reference

### `TensorRT-LLM`

Best use later:

- execution backend optimization
- graph-friendly stable shapes
- inflight-batching design ideas

### `Triton`

Best use later:

- deployment substrate
- stage serving shell

But:

- it does not solve the core decode scheduler policy for you

## Async / Multithread / Multi-Stream GPU Guidance

## What helps

- asynchronous host-side request preparation
- asynchronous scheduler bookkeeping
- clean separation of scheduler logic from model execution
- graph capture after shape families become stable

## What often hurts

- many concurrent GPU streams for tiny decode cohorts
- oversubscription that lowers effective batch density
- complicated host orchestration that costs more than it saves

## Practical rule for this stack

For the current single-worker `T3` problem:

- prefer one scheduler-controlled execution lane with dense batches
- do not prioritize stream count over batch density
- add multi-stream overlap only after profiling proves the GPU is underutilized in a way that overlap can actually fix

## Suggested Metrics

These should be part of the scheduler evaluation loop because they expose whether the scheduler is structurally improving:

- request submit-to-first-token
- request submit-to-finish
- active cohort count over time
- mean cohort size over time
- singleton cohort rate
- bucket fill rate
- padding waste
- rebatch / merge count
- queue wait before first admission
- per-request age at admission
- decode tokens per second at the `T3` stage
- acceptance of long versus short requests under load

If only a few can be added immediately, the most useful near-term set is:

- active cohort count
- singleton cohort rate
- mean cohort size
- padding waste
- submit-to-first-token
- submit-to-finish

## Practical Engineering Sequence

Recommended implementation order:

1. tune `batching_window_ms`
2. replace exact length equality with coarse buckets
3. log padding waste and singleton rate
4. add `max_active_cohorts`
5. add age-based admission escape
6. rerun staggered mixed-length benchmarks
7. add decode-priority scheduling
8. add chunked prefill for long arrivals if needed
9. add step-boundary merge / rebatching
10. only then consider lower-level backend overlap / CUDA-graph work

## Expected Wins And Risks

## Likely highest ROI

### Wider admission plus bucketing

Expected win:

- biggest immediate gain if the current traffic is mostly fragmenting

Risk:

- modest `TTFT` regression if the window is too aggressive

Why it is worth it:

- current structure is so inefficient that modest extra queueing can still produce net latency wins

### `max_active_cohorts`

Expected win:

- better stability under load
- less round-robin overhead

Risk:

- starvation without age-aware exceptions

### Step-boundary merge / rebatching

Expected win:

- probably the best next throughput improvement after admission cleanup

Risk:

- highest correctness and implementation complexity

## Lower ROI until later

### Multi-stream GPU scheduling

Expected win:

- uncertain and often small at this phase

Risk:

- can make the scheduler appear more concurrent while actually lowering batch density and hurting latency

### Multi-instance / disaggregation

Expected win:

- can be large later

Risk:

- operational complexity is too high relative to the current evidence

## Bottom Line

The current issue is not that the custom scheduler exists.

The current issue is that the scheduler policy is still too eager to fragment traffic and too willing to keep too many small cohorts alive at once.

Best current answer:

- keep the custom scheduler
- make it more like `Orca/vLLM/Sarathi`
- cap active cohort growth
- prioritize batch density over exact shape purity
- treat multi-stream and deeper backend work as later optimizations

## Downloaded Local Reference Bundle

Papers downloaded into [References/scheduler_serving](/Users/hisham/Code/Bahraini_TTS/References/scheduler_serving):

- [Orca_OSDI22.pdf](/Users/hisham/Code/Bahraini_TTS/References/scheduler_serving/Orca_OSDI22.pdf)
- [vLLM_PagedAttention_2309.06180.pdf](/Users/hisham/Code/Bahraini_TTS/References/scheduler_serving/vLLM_PagedAttention_2309.06180.pdf)
- [Sarathi-Serve_OSDI24.pdf](/Users/hisham/Code/Bahraini_TTS/References/scheduler_serving/Sarathi-Serve_OSDI24.pdf)
- [FastServe_2305.05920.pdf](/Users/hisham/Code/Bahraini_TTS/References/scheduler_serving/FastServe_2305.05920.pdf)
- [SGLang_2312.07104.pdf](/Users/hisham/Code/Bahraini_TTS/References/scheduler_serving/SGLang_2312.07104.pdf)
- [DistServe_OSDI24.pdf](/Users/hisham/Code/Bahraini_TTS/References/scheduler_serving/DistServe_OSDI24.pdf)
- [Llumnix_2406.03243.pdf](/Users/hisham/Code/Bahraini_TTS/References/scheduler_serving/Llumnix_2406.03243.pdf)

Repos cloned into `external/`:

- [vllm](/Users/hisham/Code/Bahraini_TTS/external/vllm)
- [sglang](/Users/hisham/Code/Bahraini_TTS/external/sglang)
- [sarathi-serve](/Users/hisham/Code/Bahraini_TTS/external/sarathi-serve)
- [FastServe](/Users/hisham/Code/Bahraini_TTS/external/FastServe)
- [TensorRT-LLM](/Users/hisham/Code/Bahraini_TTS/external/TensorRT-LLM)
- [DistServe](/Users/hisham/Code/Bahraini_TTS/external/DistServe)
- [llumnix-ray](/Users/hisham/Code/Bahraini_TTS/external/llumnix-ray)
- [triton-server](/Users/hisham/Code/Bahraini_TTS/external/triton-server)

## Primary Sources

- Orca paper: <https://www.usenix.org/system/files/osdi22-yu.pdf>
- vLLM paper: <https://arxiv.org/pdf/2309.06180.pdf>
- vLLM docs: <https://docs.vllm.ai/en/v0.9.0/performance/optimization.html>
- Sarathi-Serve paper: <https://www.usenix.org/system/files/osdi24-agrawal.pdf>
- FastServe paper: <https://arxiv.org/pdf/2305.05920.pdf>
- SGLang paper: <https://arxiv.org/pdf/2312.07104.pdf>
- SGLang docs: <https://docs.sglang.io/>
- TensorRT-LLM docs: <https://nvidia.github.io/TensorRT-LLM/>
- TensorRT-LLM scheduler docs: <https://nvidia.github.io/TensorRT-LLM/torch/scheduler.html>
- Triton scheduler docs: <https://docs.nvidia.com/deeplearning/triton-inference-server/archives/triton-inference-server-2480/user-guide/docs/user_guide/architecture.html>
- DistServe paper: <https://www.usenix.org/system/files/osdi24-zhong-yinmin.pdf>
- Llumnix paper: <https://arxiv.org/pdf/2406.03243.pdf>
