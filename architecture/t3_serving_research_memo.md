# T3 Serving Research Memo

_Last updated: 2026-03-14_

## Direct Answer

Partial: there is already a close solution, but mostly as `TTS systems adopting LLM-serving engines`, not as a broadly standardized `TTS-native` serving architecture.

Strongest current read:

- `Fish Audio S2` is the clearest TTS-side evidence that this serving shape now exists in practice:
  - AR speech generation
  - one shared worker
  - scheduler-style concurrent serving
  - paged KV cache
  - prefix caching
  - continuous batching
  - all inherited from `SGLang`
  - source: <https://huggingface.co/fishaudio/s2-pro/blob/main/README.md>
- `CosyVoice 2/3` is also very close:
  - the official repo now supports `vLLM`
  - the repo contains an actual `add_request(...)` + `step()` integration around the speech-token LM
  - it also supports `TensorRT-LLM` runtime paths
  - source: <https://github.com/FunAudioLLM/CosyVoice>
- `Qwen3-TTS` is partial:
  - official repo says `vLLM-Omni` has day-0 support
  - batch offline inference exists
  - but the repo explicitly says open online serving comes later
  - source: <https://github.com/QwenLM/Qwen3-TTS>

So the most defensible conclusion is:

- `LLM-style prefill + step + scheduler serving is already solved in adjacent LLM systems`
- `it is now starting to appear in TTS through direct adaptation`
- `but I did not find a widely adopted, speech-specific, open-source standard serving layer for AR speech-token TTS front ends`

## Local Baseline

Current local Chatterbox state:

- correctness is fixed through `concurrency=4`
- but the current `concurrent` path still serializes `T3` with a coarse full-decode lock
- so it is not yet the final scalable design

Most direct local refs:

- [concurrent_decode.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/inference/concurrent_decode.py)
- [worker_concurrent.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/runtime/worker_concurrent.py)
- [t3_concurrent_inference_findings.md](/Users/hisham/Code/Bahraini_TTS/architecture/t3_concurrent_inference_findings.md)

## Comparison Table

| System / paper / repo | Date | Domain | AR speech-token LM or not | Has `prefill + step` split? | Has shared-worker concurrent scheduling? | Evidence | Relevance to Chatterbox T3 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Local `Chatterbox concurrent` path | 2026-03-14 | TTS | Yes | No public split yet; still one full-decode call | No; uses coarse full-decode `T3` lock | [concurrent_decode.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/inference/concurrent_decode.py), [worker_concurrent.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/runtime/worker_concurrent.py) | Exact current baseline and bottleneck |
| `CosyVoice 2/3` official repo | 2025-05 repo support; 2024-08 streaming+KV-cache support | TTS | Yes | Yes | Yes, via `vLLM` / `TensorRT-LLM`, not a bespoke TTS scheduler | Official repo says `vLLM` support and streaming inference with KV cache; local official code uses `LLMEngine.add_request()` and `step()` in the speech LM path: [README.md](/Users/hisham/Code/Bahraini_TTS/external/CosyVoice/README.md#L40), [README.md](/Users/hisham/Code/Bahraini_TTS/external/CosyVoice/README.md#L154), [llm.py:506](/Users/hisham/Code/Bahraini_TTS/external/CosyVoice/cosyvoice/llm/llm.py#L506), [model.py:281](/Users/hisham/Code/Bahraini_TTS/external/CosyVoice/cosyvoice/cli/model.py#L281), [vllm_example.py:15](/Users/hisham/Code/Bahraini_TTS/external/CosyVoice/vllm_example.py#L15), <https://github.com/FunAudioLLM/CosyVoice> | Closest open-source match to `Chatterbox T3` today |
| `Fish Audio S2 Pro` / `Fish Audio S2 Technical Report` | 2026-03 | TTS | Yes, Dual-AR acoustic token model | Effectively yes through SGLang serving stack | Yes | Official model card says S2 includes an `SGLang-based streaming inference engine` and inherits `continuous batching`, `paged KV cache`, `CUDA graph replay`, and `RadixAttention-based prefix caching`; official docs cite `Fish Audio S2 Technical Report`: <https://huggingface.co/fishaudio/s2-pro/blob/main/README.md>, <https://speech.fish.audio/> | Strongest evidence that the exact serving shape already exists in a TTS system |
| `Qwen3-TTS` / `Qwen3-TTS Technical Report` | 2026-01-22 repo release | TTS | Yes, discrete multi-codebook LM | Partial | Partial | Official repo says `vLLM officially provides day-0 support`, gives offline batch examples via `vLLM-Omni`, and explicitly says `Now only offline inference is supported. Online serving will be supported later.`: <https://github.com/QwenLM/Qwen3-TTS> | Strong evidence the field is moving this direction, but open online serving is not fully there |
| `Fish-Speech: Leveraging Large Language Models for Advanced Multilingual Text-to-Speech Synthesis` | 2024-11 | TTS | Yes | Not clearly exposed | Not evidenced in the official open-source repo | Official repo/tech report show LLM-based TTS and deploy-friendly inference server, but not a clear public `prefill + step + scheduler` architecture: <https://github.com/fishaudio/fish-speech>, <https://arxiv.org/abs/2411.01156> | Relevant family, but not the clearest serving answer |
| `Neural Codec Language Models are Zero-Shot Text to Speech Synthesizers` (`VALL-E`) | 2023-01 | TTS | Yes | No serving split described | No serving scheduler described | Official Microsoft Research paper page: <https://www.microsoft.com/en-us/research/publication/neural-codec-language-models-are-zero-shot-text-to-speech-synthesizers/> | Important model family origin, not a serving solution |
| `VALL-E R: Robust and Efficient Zero-Shot Text-to-Speech Synthesis via Monotonic Alignment` | 2024-06 | TTS | Yes | No serving split described | No serving scheduler described | Official Microsoft Research paper page says it reduces AR steps with monotonic alignment and codec merging, but this is model-side efficiency, not shared-worker scheduling: <https://www.microsoft.com/en-us/research/publication/vall-e-r-robust-and-efficient-zero-shot-text-to-speech-synthesis-via-monotonic-alignment/> | Relevant if you want fewer T3 steps, not a serving architecture answer |
| `vLLM` / `Efficient Memory Management for Large Language Model Serving with PagedAttention` | 2023 paper; current docs active | LLM serving | No | Yes | Yes | Official docs and Berkeley project page describe `PagedAttention`, `continuous batching`, `chunked prefill`, and the `LLMEngine.add_request()` / `step()` API: <https://docs.vllm.ai/>, <https://docs.vllm.ai/en/v0.6.3/dev/engine/llm_engine.html>, <https://sky.cs.berkeley.edu/project/vllm/> | Best direct architectural template |
| `Orca: A Distributed Serving System for Transformer-Based Generative Models` | 2022 | LLM serving | No | Yes, iteration-level scheduling | Yes | Official Friendli research page describes `iteration-level scheduling` and `selective batching`: <https://friendli.ai/research/orca> | Conceptual origin of the serving pattern |
| `SGLang` | 2024-2025 public engine maturity | LLM/VLM serving | No | Yes | Yes | Official repo lists `RadixAttention`, `zero-overhead batch scheduler`, `prefill-decode disaggregation`, `continuous batching`, and `paged attention`: <https://github.com/sgl-project/sglang> | Very high relevance, and already used by Fish Audio S2 |
| `TensorRT-LLM` | 2024-2025 docs | LLM serving | No | Yes | Yes | Official docs describe `in-flight batching`, `paged KV cache`, `chunked prefill`, `request scheduling`, and `disaggregated serving`: <https://nvidia.github.io/TensorRT-LLM/latest/overview.html>, <https://nvidia.github.io/TensorRT-LLM/advanced/gpt-attention.html>, <https://nvidia.github.io/TensorRT-LLM/torch/scheduler.html> | Strong backend option if you want max serving efficiency |
| `Text Generation Inference (TGI)` | 2023-2025 docs | LLM serving | No | Yes | Yes | Official docs list `continuous batching`, `Paged Attention`, `KV-caching`, and streaming; current docs also say TGI is in maintenance mode and recommend `vLLM` and `SGLang`: <https://huggingface.co/docs/text-generation-inference/index> | Good conceptual reference, but not the best current target |

## Closest Existing Solutions

### 1. Fish Audio S2 is the strongest TTS-specific evidence

- The official model card is unusually explicit.
- It says the model includes an `SGLang-based streaming inference engine`.
- It also says the model inherits `continuous batching`, `paged KV cache`, `CUDA graph replay`, and `RadixAttention-based prefix caching`.
- That is almost exactly the serving shape you are asking about, except implemented through `SGLang`, not through a brand-new TTS scheduler.
- Source: <https://huggingface.co/fishaudio/s2-pro/blob/main/README.md>

### 2. CosyVoice is the clearest open-source code-level precedent

- The official repo now supports `vLLM`.
- The local official code shows the speech LM using:
  - `LLMEngine.from_engine_args(...)`
  - `add_request(...)`
  - `step()`
  - per-request output queues
- The fallback path also has a per-request `cache` and `forward_one_step(...)`, which is the right model boundary for a `prefill + step` style refactor.
- This is not just a paper claim. It is code.
- Sources:
  - [llm.py:506](/Users/hisham/Code/Bahraini_TTS/external/CosyVoice/cosyvoice/llm/llm.py#L506)
  - [llm.py:537](/Users/hisham/Code/Bahraini_TTS/external/CosyVoice/cosyvoice/llm/llm.py#L537)
  - [model.py:281](/Users/hisham/Code/Bahraini_TTS/external/CosyVoice/cosyvoice/cli/model.py#L281)
  - <https://github.com/FunAudioLLM/CosyVoice>

### 3. Qwen3-TTS shows the direction, but not the full open-source serving answer yet

- Official repo says `vLLM-Omni` has day-0 support.
- It gives offline examples, including batched samples.
- But it explicitly says `Now only offline inference is supported. Online serving will be supported later.`
- So this is strong evidence of convergence toward LLM-style serving, but it is not yet a complete public answer for open concurrent online serving.
- Source: <https://github.com/QwenLM/Qwen3-TTS>

### 4. The underlying serving solution is already mature in LLM serving

- `vLLM`, `SGLang`, and `TensorRT-LLM` already solve the core systems problem:
  - prefill vs decode separation
  - scheduler-owned active request stepping
  - shared immutable weights
  - per-request KV/cache state
  - continuous batching / iteration-level scheduling
- So the core serving ideas are not open research anymore.
- What is new is their transfer into speech-token TTS front ends.
- Sources:
  - <https://docs.vllm.ai/>
  - <https://github.com/sgl-project/sglang>
  - <https://nvidia.github.io/TensorRT-LLM/latest/overview.html>
  - <https://friendli.ai/research/orca>

## What Seems Unsolved

- I did not find a widely adopted, open-source, `TTS-native` serving framework whose public abstraction is explicitly:
  - `prefill(request)`
  - `decode_step(active_requests)`
  - scheduler-owned request table
  - speech-specific cache / prompt reuse
  - speech-output aware streaming control
- I did not find an official open-source `VALL-E` family serving stack that exposes this architecture as a reusable runtime layer.
- I did not find a public `Chatterbox`-family implementation where the AR speech-token front half already has a first-class scheduler boundary independent of the rest of the TTS stack.
- I did not find evidence that this has become a standardized systems layer across TTS repos the way it already has in LLM serving.
- The closest TTS systems are mostly `wrapping or embedding LLM-serving engines`, not publishing a speech-native scheduler API of their own.

## Research Opportunity

If you build a proper `T3 prefill + step + scheduler` design for Chatterbox-style AR speech-token generation:

- it is probably `not novel as a core serving primitive`
- it is probably `novel enough as a TTS systems contribution`, especially if you do one or more of these well:
  - speech-prompt / voice-prefix KV reuse across requests
  - scheduler-aware handling of CFG duplication
  - scheduler-aware handling of speech stop conditions and alignment checks
  - real TTS metrics:
    - `TTFA`
    - acoustic-tokens/s
    - audio-seconds/s
    - prefix-cache hit rate for reused voices
    - latency under mixed prompt lengths
  - integration with the downstream `S3` stage without reintroducing queue bubbles

Best phrasing of the opportunity:

- `novel for TTS serving systemization`
- `mostly an adaptation of established LLM-serving ideas`
- `possibly publishable or thesis-worthy if the speech-specific constraints are handled explicitly and evaluated carefully`

Least defensible phrasing:

- `we invented prefill + step scheduling for AR generation`

That claim would be too strong because `Orca`, `vLLM`, `SGLang`, `TensorRT-LLM`, and `TGI` already cover the core serving pattern.

## Best Next Technical Direction

### Recommendation

Adapt an `LLM-serving design`, not a brand-new scheduler from scratch.

Most practical order:

1. make `T3` expose an explicit `prefill(...)` boundary
2. make `T3` expose a single-step `decode_step(...)` boundary
3. move all per-request decode state into a request/session object
4. introduce a scheduler that owns active request stepping
5. only after that, re-evaluate `S3`

### Best template to copy

Best architectural target:

- `vLLM` style request API:
  - add request
  - keep per-request state outside the model
  - one engine step advances all active requests
- `SGLang` style scheduling features:
  - continuous batching
  - prefix caching
  - prefill/decode separation
- optional `TensorRT-LLM` backend ideas later:
  - paged KV cache
  - inflight batching
  - disaggregated serving

### Best immediate move for Chatterbox

Do this next:

- turn current `run_concurrent_t3_inference(...)` into:
  - `t3_prefill(...)`
  - `t3_decode_step(...)`
- keep `past_key_values`, generated ids, sampler state, and analyzer state in request-local objects
- replace the coarse full-decode lock with a scheduler loop that batches active requests per token step

Why:

- it matches the strongest existing solutions
- it directly attacks the current limiter
- it preserves your current correctness work
- it keeps the problem narrowly on `T3`, which is exactly what matters right now

### When to treat it as a real research problem

Treat it as a true research problem only if, after adapting an LLM-serving shape, one of these remains hard:

- prompt-audio prefix caching does not map cleanly onto speech-token prompts
- CFG duplication makes batching materially inefficient
- alignment / repetition control needs speech-specific scheduler coupling
- the `T3 -> S3` handoff creates new queueing effects that standard LLM engines do not model

If those issues dominate, then the work becomes more than adaptation.

## Bottom Line

- `Yes, there is already a close solution.`
- `No, it is not broadly solved as a TTS-native standard layer.`
- `The closest mature answers are imported from LLM serving.`
- `For Chatterbox T3, the right next move is to adapt that design, not rediscover it.`

## Primary Sources

- Local repo context:
  - [CONTEXT.md](/Users/hisham/Code/Bahraini_TTS/CONTEXT.md)
  - [PROGRESS.md](/Users/hisham/Code/Bahraini_TTS/PROGRESS.md)
  - [TRACE_RUN_RESULTS.md](/Users/hisham/Code/Bahraini_TTS/TRACE_RUN_RESULTS.md)
  - [CHATTERBOX_SCALING_PLAN.md](/Users/hisham/Code/Bahraini_TTS/CHATTERBOX_SCALING_PLAN.md)
  - [t3_concurrent_inference_findings.md](/Users/hisham/Code/Bahraini_TTS/architecture/t3_concurrent_inference_findings.md)
  - [t3.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/t3.py)
  - [concurrent_decode.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/inference/concurrent_decode.py)
  - [alignment_stream_analyzer_concurrent.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/inference/alignment_stream_analyzer_concurrent.py)
  - [worker_concurrent.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/runtime/worker_concurrent.py)
- Official / primary external sources:
  - <https://github.com/FunAudioLLM/CosyVoice>
  - <https://huggingface.co/fishaudio/s2-pro/blob/main/README.md>
  - <https://speech.fish.audio/>
  - <https://github.com/QwenLM/Qwen3-TTS>
  - <https://www.microsoft.com/en-us/research/publication/neural-codec-language-models-are-zero-shot-text-to-speech-synthesizers/>
  - <https://www.microsoft.com/en-us/research/publication/vall-e-r-robust-and-efficient-zero-shot-text-to-speech-synthesis-via-monotonic-alignment/>
  - <https://sky.cs.berkeley.edu/project/vllm/>
  - <https://docs.vllm.ai/>
  - <https://friendli.ai/research/orca>
  - <https://github.com/sgl-project/sglang>
  - <https://nvidia.github.io/TensorRT-LLM/latest/overview.html>
  - <https://huggingface.co/docs/text-generation-inference/index>
