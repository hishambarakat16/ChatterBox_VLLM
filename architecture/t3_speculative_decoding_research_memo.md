# T3 Speculative Decoding Research Memo

_Last updated: 2026-03-14_

## Direct Answer

Partial.

- Speculative decoding is already a mature idea in `LLM` serving and already has strong practical implementations.
- I found solid adjacent evidence in speech from `Distil-Whisper`, which is explicitly designed to act as an assistant model for speculative decoding with Whisper.
- I did **not** find strong primary-source evidence that speculative decoding is already a standard, published, open-source solution for `AR speech-token TTS planners` in the `Chatterbox` / `VALL-E` / `CosyVoice` class.
- For this repo, the best practical speculative path is probably `classic draft-and-verify`, but only with a `new smaller multilingual draft T3` that is verifier-compatible. The existing `Chatterbox Turbo` path is too mismatched to be used as a drop-in draft model.

## Repo-Specific Status Update

Local prototype work has now changed the practical recommendation.

Confirmed locally:

- self-draft speculative decoding is mechanically correct
- self-draft is slower than baseline, which is expected because the same full model is acting as both draft and verifier
- the first real separate draft candidate, an untrained `12`-layer subset multilingual `T3`, is also mechanically correct
- that separate draft fails badly as a serving strategy:
  - `speculative_acceptance_rate_mean = 0.04`
  - `speculative_rebuild_count_mean = 74`
  - `speculative_rebuild_tokens_total_mean = 2877`
  - `70 / 75` rounds are zero-match rounds
  - `speculative_t3_s_mean ~= 31.00s` vs `baseline_t3_s_mean ~= 1.73s`

Current interpretation:

- speculative decoding remains useful here as a correctness harness
- naive `AR` draft shrinking is not enough
- the current best next step is a planner-local re-architecture, most likely `Medusa`-style or another semi-autoregressive chunked planner
- any new planner still has to preserve the current `T3 -> S3` token contract

## Local Architecture Constraints

Current multilingual `T3` matters because speculative decoding only helps if the draft and verifier line up with the real serving path.

Local facts:

- verifier model is a `Llama 520M` backbone with `30` layers and `16` attention heads in [llama_configs.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/llama_configs.py)
- multilingual `T3` uses `2454` text tokens and `8194` speech tokens in [t3_config.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/modules/t3_config.py)
- conditioning is not plain text-only; it includes speaker embedding, optional prompt speech tokens, optional emotion, and a perceiver-resampled prompt path in [cond_enc.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/modules/cond_enc.py)
- the current scheduled runtime already has a true `prefill + batched decode-step` shape with per-request KV state in [scheduled_decode.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/inference/scheduled_decode.py)
- current multilingual decode uses `CFG` by doubling rows and combining conditional/unconditional logits in [scheduled_decode.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/inference/scheduled_decode.py)
- the alignment guard can mutate EOS behavior during decode, so stop semantics are part of the runtime contract, not just the raw model logits

Why that matters:

- speculative decoding is easiest when the verifier path is already a clean `prefill + step` engine
- this repo now has that shape
- but compatibility is stricter than in plain text `LLM` serving because `T3` is not just a tokenizer plus a causal LM

## Ranked Top 3 Approaches

### 1. Medusa-Style Multi-Head Planner Upgrade

Why it now ranks first:

- it changes only the planner head, not the whole stack
- it preserves the current multilingual `T3` backbone, conditioning path, speech-token vocabulary, and `S3` interface
- it is the lowest-risk first step toward semi-autoregressive planner behavior under concurrency
- it fits what we already learned locally: interface compatibility matters, but a naive smaller `AR` draft is not close enough behaviorally

What still has to be checked:

- exact compatibility with the current `CFG` two-row path
- how future-token heads should be trained against the real post-`CFG` planner behavior
- shape and cache boundaries through the planner-only middle section during integration
- whether head-only training is enough, or whether partial backbone unfreezing is required

What it needs:

- same speech-token vocabulary and IDs
- same multilingual text tokenizer IDs and BOS/EOS conventions
- same conditioning layout
- future-token heads that predict `T3` speech tokens directly from the current hidden state
- a verification path that can be evaluated with the existing speculative prototype harness

Training requirement:

- yes

Expected upside:

- strongest near-term planner-local concurrency experiment
- does not require introducing a second tokenizer or a second full draft checkpoint

Main sources:

- `Medusa: Simple Framework for Accelerating LLM Generation with Multiple Decoding Heads`: <https://arxiv.org/abs/2401.10774>
- official repo: <https://github.com/FasterDecoding/Medusa>

### 2. Classic Draft-and-Verify With a Trained Smaller Multilingual Draft T3

Why it still matters:

- it still matches the current scheduler architecture directly
- the verifier path can remain the existing scheduled `T3` engine
- it remains the cleanest classical speculative-decoding baseline

Why it ranks below Medusa now:

- we already tested the closest no-training approximation of this idea
- the untrained `layer_subset` draft failed so badly that it is no longer the best next experiment
- a useful version now likely requires explicit distillation or training anyway

Fit to Chatterbox `T3`:

- very good if a truly behaviorally close smaller multilingual draft can be trained
- still valid, but no longer the first thing to try next

Training requirement:

- yes

Expected upside:

- strong if you are willing to retrain the main model family
- cleaner long-term maintenance story than a separate draft model

Main sources:

- `Fast Inference from Transformers via Speculative Decoding` (Leviathan et al., 2023): <https://arxiv.org/abs/2211.17192>
- `Accelerating Large Language Model Decoding with Speculative Sampling` (Chen et al., 2023): <https://arxiv.org/abs/2302.01318>
- `Draft & Verify: Lossless Large Language Model Acceleration via Self-Speculative Decoding` (Zhang et al., 2023): <https://arxiv.org/abs/2309.08168>

### 3. Self-Speculative Decoding / LayerSkip-Style Early Exit

Why it is still interesting:

- no separate tokenizer mismatch
- no separate speech vocabulary mismatch
- no separate conditioning encoder mismatch
- no second model to keep in sync

Why it is not the first training target:

- the open LayerSkip recipe requires a model trained for early exit
- it is not a drop-in switch for an arbitrary pretrained model
- current `T3` would need retraining or continued training with an early-exit objective

Fit to Chatterbox `T3`:

- very good long-term fit because it preserves one model family
- especially attractive if we later want a self-speculative variant without a separate draft checkpoint

Training requirement:

- yes

Expected upside:

- strong if you are willing to retrain the main model family
- cleaner long-term maintenance story than a separate draft model

Main sources:

- `LayerSkip: Enabling Early Exit Inference and Self-Speculative Decoding`: <https://arxiv.org/abs/2404.16710>
- official repo: <https://github.com/facebookresearch/LayerSkip>

## Lower-Fit Variants

### Blockwise / Lookahead / Jacobi-Style Parallel Decoding

These are interesting, but they are not my top recommendation for this repo.

Why:

- they are less standard in serving stacks than classic draft-and-verify
- they are less proven for a speech-token LM with sampling, `CFG`, and runtime EOS guardrails
- the current repo already has the right boundary for a draft/verifier design, so the simpler path is not to invent a more exotic speculative algorithm first

Main source:

- `Break the Sequential Dependency of LLM Inference Using Lookahead Decoding`: <https://arxiv.org/abs/2402.02057>

## Required Compatibility Constraints

Any serious draft model for this repo should match these constraints:

### Required for exact practical use

- same speech-token vocabulary size and token IDs as multilingual `T3`
  - current verifier uses `8194` speech tokens
  - current speech BOS/EOS are `6561` and `6562`
- same multilingual text-token vocabulary and BOS/EOS conventions
  - current multilingual verifier uses `2454` text tokens
- same conditioning contract
  - speaker embedding shape and projection path
  - prompt speech token path
  - perceiver-resampler behavior if present
  - emotion conditioning behavior if present
- same speech-position embedding convention
- same stop-token semantics
- same or deliberately matched sampling-time logits processors
  - repetition penalty
  - temperature / top-p / min-p
  - alignment/EOS guard behavior if it is applied before token commit

### Required for best acceptance

- same `CFG` semantics as the verifier, or a draft trained to approximate the verifier's post-`CFG` token distribution
- similar multilingual coverage and prompt-following behavior
- similar behavior near EOS and alignment completion

### Important non-obvious constraint

`HF` assistant-model support is not a drop-in answer here.

Official docs say:

- assisted/speculative decoding currently does not support batched inputs
- assistant and target usually need the same tokenizer
- `Universal Assisted Decoding` exists for different tokenizers, but that assumes text decode/re-encode behavior

That is a poor fit for `speech-token` generation, because your generated objects are discrete speech tokens, not text strings. Source: <https://huggingface.co/docs/transformers/generation_strategies>

## Has This Been Applied To Speech Yet?

### Strong adjacent speech evidence

- `Distil-Whisper` is explicitly designed to act as an assistant model for Whisper and claims `2x` faster inference with mathematically identical outputs under speculative decoding
- this is strong evidence that speculative decoding is not text-only in practice
- but it is `ASR text decoding`, not `speech-token TTS`

Sources:

- official repo README: <https://github.com/huggingface/distil-whisper>
- paper: <https://arxiv.org/abs/2311.00430>

### What I did not find

- I did not find a strong primary-source claim that `CosyVoice`, `Fish Speech`, `VALL-E`, or `Chatterbox` already use speculative decoding in their published open-source AR speech-token planners
- local repo search across `external/chatterbox` and `external/CosyVoice` did not find an implemented speculative-decoding path in those codebases
- the notable exception in this repo is `external/F5-TTS`, which vendors `TensorRT-LLM` patch code for `Eagle`, `Medusa`, and `ReDrafter`; that shows serving-backend support exists, but not that the `TTS planner itself` already uses speculative decoding

## Chatterbox Turbo: Useful or Not?

### Useful as a reference

- yes, as a conceptual reminder that a smaller, faster planner can still be product-useful
- yes, as a speed/quality comparison point
- yes, as a training-shape reference for how much model simplification the product family will tolerate

### Not useful as a direct draft model

- no, not for verifier-compatible speculative decoding

Why:

- different backbone family: `GPT-2 medium` vs multilingual `Llama 520M`
- different text tokenizer size: `50276` vs `2454`
- different speech vocabulary size: `6563` vs `8194`
- different conditioning behavior: no perceiver-resampler, no emotion conditioning
- English-only instead of multilingual
- not shaped as the same `CFG` multilingual path

Local refs:

- [tts_turbo.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/tts_turbo.py)
- [t3.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/t3.py)

Bottom line:

- `Turbo` is a conceptual draft reference
- it is not a real verifier/draft pair for the current multilingual `T3`

## Practical Recommendation

### Best Near-Term Planner Experiment For This Repo

`Medusa`-style multi-head planner upgrade on top of the current multilingual `T3`, using the existing speculative prototype as the compatibility and verification harness.

Why this is the best near-term move now:

- it targets the real concurrency bottleneck, the planner decode loop
- it keeps the rest of the stack fixed, especially `S3`
- it avoids introducing a second full draft model before we know a planner-local head approach is enough
- it gives a clean research story: planner-only re-architecture under a fixed `T3 -> S3` contract

### Role Of The Existing Speculative Prototype

The current speculative code should be kept.

Why:

- it already proved the external request/output contract and cache boundaries
- it is the cleanest place to verify future multi-token planner proposals against the existing `T3`
- it already measures:
  - token agreement
  - acceptance / mismatch behavior
  - replay churn
  - timing and memory

Practical next use:

- reuse it as the harness for Medusa-style planner verification
- rerun shape/boundary tracing on the planner-only middle section once the new heads exist
- confirm the exact hidden-state -> future-token-head -> verify-block boundary before any scheduled-runtime integration

### What can be done without training

Very little that looks production-credible.

Realistically:

- you can prototype the verifier-side acceptance path
- you can add interfaces for `draft_prefill`, `draft_step`, and `verify_block`
- you can benchmark hypothetical verifier costs
- you can maybe try a crude layer-dropped draft as a feasibility probe

But:

- there is no serious zero-training drop-in draft model in the repo today
- `Turbo` is too mismatched
- HF assistant decoding is not a good drop-in because of batching and tokenizer assumptions

### What requires training

- a smaller multilingual draft `T3`
- a self-speculative `LayerSkip`-style model
- a `Medusa`-style multi-head draft path

## Recommended Next Step

1. Keep the current scheduled verifier path as the reference `T3`.
2. Add a small internal design note for a speculative runtime boundary:
   - `prefill_request`
   - `draft_k_tokens`
   - `verify_block`
   - `commit_prefix`
3. Define a draft-model spec that is actually compatible with multilingual `T3`:
   - same text vocab
   - same speech vocab
   - same conditioning
   - same BOS/EOS
   - same `CFG` contract
4. If you want the fastest practical experiment, train or derive a first small multilingual draft `T3` in the `100M-250M` class.
5. Measure the real acceptance rate under your current runtime settings:
   - `cfg_weight`
   - temperature
   - top-p / min-p
   - alignment guard on

Most likely outcome:

- this will tell you quickly whether speculative decoding is a real win here or whether `CFG` plus speech-token entropy kills the acceptance rate

## Risks / Open Questions

- `CFG` may reduce acceptance if the draft does not model the same post-`CFG` distribution
- alignment/EOS guard logic may create late-stage rejection spikes even when mid-utterance acceptance is decent
- multilingual behavior may require a larger draft than expected
- speculative verification may interact badly with batched heterogeneous request lengths if the block size is not adaptive
- if acceptance is weak, the extra draft work can become pure overhead
- if acceptance is strong only at low temperature / low `cfg_weight`, the practical win may be narrower than expected

## Source Notes

Downloaded local reference bundle:

- `References/speculative_decoding/2211.17192_fast_inference_speculative_decoding.pdf`
  - original speculative-decoding paper
- `References/speculative_decoding/2309.08168_draft_and_verify.pdf`
  - self-speculative draft/verify variant
- `References/speculative_decoding/2401.10774_medusa.pdf`
  - multi-head drafting
- `References/speculative_decoding/2402.02057_lookahead_decoding.pdf`
  - training-free lookahead variant
- `References/speculative_decoding/2024_acl_layerskip.pdf`
  - early exit / self-speculative decoding
- `References/speculative_decoding/Distil_Whisper.pdf`
  - speech-domain adjacent evidence

Other primary sources used:

- Hugging Face speculative decoding docs: <https://huggingface.co/docs/transformers/generation_strategies>
- vLLM speculative decoding docs: <https://docs.vllm.ai/en/latest/features/spec_decode.html>
- `Distil-Whisper` official repo: <https://github.com/huggingface/distil-whisper>
- `Medusa` official repo: <https://github.com/FasterDecoding/Medusa>
- `LayerSkip` official repo: <https://github.com/facebookresearch/LayerSkip>
