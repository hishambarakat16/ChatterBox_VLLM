# T3 Concurrent Inference Findings

_Last updated: 2026-03-14_

## Scope

Focused only on thread-safe concurrent inference for the shared `T3` stage in local `Chatterbox`.

Files inspected:

- [t3.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/t3.py)
- [alignment_stream_analyzer.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/inference/alignment_stream_analyzer.py)
- [t3_hf_backend.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/inference/t3_hf_backend.py)
- [mtl_tts_streaming.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/mtl_tts_streaming.py)
- [worker.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/runtime/worker.py)

## Agent 1 Handoff

- I am `Agent 1`.
- HM asked for a narrow investigation of why `T3` breaks under concurrent requests on one shared model instance.
- Immediate milestone remains:
  - `2` simultaneous requests on one shared `T3` instance
  - both requests must complete correctly

## Main Findings

### 1. Shared `T3` object stores request-local decode state

In [t3.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/t3.py):

- `self.compiled` is reset inside `inference()`
- `self.patched_model` is rebuilt inside `inference()`
- the decode loop keeps reading `self.patched_model`

That means two requests can overwrite each other's backend and analyzer mid-generation.

Most direct lines:

- [t3.py:273](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/t3.py#L273)
- [t3.py:290](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/t3.py#L290)
- [t3.py:297](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/t3.py#L297)
- [t3.py:340](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/t3.py#L340)
- [t3.py:361](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/t3.py#L361)
- [t3.py:400](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/t3.py#L400)

### 2. `AlignmentStreamAnalyzer` installs global hooks on shared layers

In [alignment_stream_analyzer.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/inference/alignment_stream_analyzer.py):

- each analyzer instance calls `register_forward_hook()` on shared transformer attention layers
- hook handles are not saved
- hooks are never removed

So every request permanently adds more hooks to the same shared `tfmr`.

Most direct lines:

- [alignment_stream_analyzer.py:63](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/inference/alignment_stream_analyzer.py#L63)
- [alignment_stream_analyzer.py:84](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/inference/alignment_stream_analyzer.py#L84)

### 3. The analyzer also mutates shared model config

The analyzer forces `tfmr.config.output_attentions = True` and never restores it.

That makes attention output behavior global instead of request-local.

Most direct lines:

- [alignment_stream_analyzer.py:85](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/inference/alignment_stream_analyzer.py#L85)
- [alignment_stream_analyzer.py:87](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/inference/alignment_stream_analyzer.py#L87)

### 4. Analyzer state is correctly per-request in concept, but not in wiring

These fields are request-local:

- `alignment`
- `curr_frame_pos`
- `text_position`
- `generated_tokens`
- `complete`
- `last_aligned_attns`

But because they are populated through shared hooks on shared layers, they can observe another request's forwards.

That makes EOS suppression or forced EOS logically unsafe across concurrent requests.

### 5. `T3HuggingfaceBackend` is also stateful

In [t3_hf_backend.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/inference/t3_hf_backend.py):

- `_added_cond` is mutable backend state
- this becomes a correctness problem immediately if the HF `generate()` path is used on a shared backend object

Most direct lines:

- [t3_hf_backend.py:32](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/inference/t3_hf_backend.py#L32)
- [t3_hf_backend.py:59](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/inference/t3_hf_backend.py#L59)
- [t3_hf_backend.py:64](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/inference/t3_hf_backend.py#L64)

### 6. The current streaming runtime already solves part of the problem

In [worker.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/runtime/worker.py) and [session.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/runtime/session.py):

- conditionals are cloned per request
- session/request state already has a home

So the first remaining correctness blocker is not prompt state anymore. It is shared mutable `T3` inference internals.

Most direct lines:

- [worker.py:95](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/runtime/worker.py#L95)
- [worker.py:109](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/runtime/worker.py#L109)
- [session.py:24](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/runtime/session.py#L24)
- [session.py:42](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/runtime/session.py#L42)

### 7. KV cache itself is not the main race here

`past` / `past_key_values` inside [t3.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/t3.py) are local variables in the current loop.

That means the immediate corruption is more about shared model-side mutable state than direct cache aliasing.

## State Ownership

### Shared immutable model state

Safe to keep on the shared `T3` object:

- `self.tfmr`
- `self.text_emb`
- `self.speech_emb`
- `self.text_head`
- `self.speech_head`
- learned positional embeddings
- read-only config and hparams

### Per-request mutable inference state

Must not live on the shared `T3` object:

- cloned `T3Cond`
- prepared prompt embeddings
- `past_key_values`
- `cache_position`
- `generated_ids`
- logits processor state
- RNG / `torch.Generator`
- alignment tracking
- stop flags
- temporary backend wrapper

### Scheduler / synchronized shared state

May be shared, but must be explicitly synchronized:

- request queue
- active request table
- decode scheduler
- KV slot allocation metadata
- cancellation / completion bookkeeping
- metrics
- any temporary coarse decode lock

## Option Evaluation

### Full model copy per request

Pros:

- simplest path to correctness
- isolates all mutable state

Cons:

- very poor VRAM density
- wrong direction for one-worker-many-sessions serving

Verdict:

- useful as a diagnostic control
- not the target architecture

### Global lock around `T3.inference()`

Pros:

- fastest correctness fix
- easiest way to hit the milestone of `concurrency=2` correctness

Cons:

- serializes `T3`
- no same-model T3 throughput win

Verdict:

- best short-term fix if the only near-term goal is correctness on one shared instance

### Per-request inference context with shared weights

Pros:

- correct state ownership
- preserves one shared copy of weights
- necessary foundation for real batching later

Cons:

- requires refactor in `T3` and analyzer path

Verdict:

- best structural fix before a scheduler

### Centralized batched decode scheduler

Pros:

- best long-term GPU saturation path
- supports many active requests with one shared model copy
- matches how modern LLM/TGI serving systems stay dense

Cons:

- most implementation complexity
- requires explicit request contexts and batch assembly

Verdict:

- best long-term design

## Best Short-Term Fix For Correctness At Concurrency 2

Use a coarse model-level lock around the full `T3` autoregressive decode path, and remove request-local objects from shared `self`.

Minimum correctness patch:

1. do not write `self.patched_model` inside `inference()`
2. do not toggle `self.compiled` inside `inference()`
3. create backend/analyzer as local variables only
4. disable shared forward hooks in concurrent mode, or remove the analyzer temporarily
5. wrap the whole T3 decode loop in one mutex

Why this is the best short-term fix:

- it directly stops cross-request state corruption
- it is small enough to verify quickly
- it gets to the current milestone without pretending to solve density

## Best Long-Term Design

Move to one shared immutable `T3` worker plus per-request decode contexts managed by a centralized batched scheduler.

Shape:

```text
shared T3 weights
  -> read-only transformer / embeddings / heads

request context
  -> prompt state
  -> kv cache
  -> generated ids
  -> alignment state
  -> sampling state

decode scheduler
  -> picks active requests
  -> batches current decode step
  -> updates each request context
  -> streams outputs back
```

That is the only design here that can improve both correctness and sessions-per-GPU density.

## Safer Alternatives To Shared Forward Hooks

Best options:

### 1. Use attentions returned from the current forward result

- ask the model call for attentions only when needed
- read the target layer/head from `output.attentions`
- pass that tensor into a request-local analyzer

This avoids shared hook registration entirely.

### 2. Fork a narrow attention path that emits only the needed layer/head

- add a small model-side path that returns the selected attention slice directly
- keep it tied to the current request call

This is cleaner than global hooks if attention extraction must stay cheap and explicit.

### 3. Temporary hooks only under exclusive execution

Only acceptable as a fallback:

- register hooks inside the request
- save `RemovableHandle`s
- remove them in `finally`
- restore any config flag in `finally`
- use only while a full model lock is held

This is still weaker than avoiding hooks completely.

## Concrete Implementation Plan

1. add `T3InferenceContext` or equivalent request-owned state object
2. refactor `T3.inference()` so backend/analyzer are locals, not `self` fields
3. add a model-level `Lock` around the full `T3` decode path
4. remove shared forward hooks from `AlignmentStreamAnalyzer`
5. first safe analyzer version:
   - consume attentions from current forward outputs
   - keep all analyzer state request-local
6. add a deterministic `concurrency=2` regression test on one shared `T3` instance
7. after correctness is stable, move decode ownership into a centralized batched scheduler

## Risks And Tradeoffs

- a full `T3` lock fixes correctness but not throughput
- returning attentions can slow decoding and may disable optimized attention kernels
- full model copies isolate state but waste VRAM
- per-request contexts without batching are correct but still not density-optimal
- centralized scheduling is the right long-term answer, but it is the highest-complexity change

## Primary Sources

- PyTorch forward hooks: <https://docs.pytorch.org/docs/stable/generated/torch.nn.Module.html>
- PyTorch inference mode: <https://docs.pytorch.org/docs/stable/generated/torch.autograd.grad_mode.inference_mode.html>
- Hugging Face model outputs: <https://huggingface.co/docs/transformers/main/en/main_classes/output>
- Hugging Face cache explanation: <https://huggingface.co/docs/transformers/main/cache_explanation>
- Hugging Face continuous batching: <https://huggingface.co/docs/transformers/main/continuous_batching>
- Hugging Face TGI overview: <https://huggingface.co/docs/inference-endpoints/main/en/engines/tgi>
- PyTorch forum note on inference thread safety for read-only modules: <https://discuss.pytorch.org/t/is-inference-thread-safe/88583/2>
