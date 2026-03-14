# T3 Compatible Draft Model

_Last updated: 2026-03-14_

## Purpose

This note records the first practical draft-model candidate for multilingual `T3` speculative decoding.

The goal is to keep the speculative interface compatible while making the draft materially cheaper than the target model.

Current status:

- this document now records a failed but informative baseline
- the layer-subset draft remains useful as evidence about compatibility vs behavioral closeness
- it is no longer the preferred next architecture direction

## What We Learned First

Self-draft speculative decoding was useful, but only for correctness.

It proved:

- speculative shapes line up
- verifier alignment is correct
- emitted tokens can match baseline exactly

It did not improve performance.

Fair repeated benchmark result:

- self-draft was about `26%` slower than baseline
- self-draft used more peak allocated memory

That is expected because the same full model was acting as both draft and verifier.

## Current Draft Candidate

The first real compatible draft candidate is a layer-subset multilingual `T3`.

Implementation:

- [draft_model.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/inference/draft_model.py)

Benchmark entry point:

- [benchmark_t3_speculative_prototype.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/benchmark_t3_speculative_prototype.py)

## First Benchmark Result

The first real separate draft benchmark was run with:

```bash
PYTHONPATH=external/chatterbox/src python external/chatterbox/benchmark_t3_speculative_prototype.py \
  --device cuda \
  --language-id ar \
  --audio-prompt-path "$PROMPT_AUDIO" \
  --text "مرحبا، هذا اختبار للبنية الحالية." \
  --max-new-tokens 128 \
  --speculate-k 4 \
  --draft-mode layer_subset \
  --draft-layers 12 \
  --draft-layer-selection even \
  --warmup-runs 2 \
  --runs 6
```

Observed:

- `draft_layer_indices = [0, 3, 5, 8, 11, 13, 16, 18, 21, 24, 26, 29]`
- `baseline_t3_s_mean ~= 1.73s`
- `speculative_t3_s_mean ~= 31.00s`
- `speculative_vs_baseline_speedup_pct ~= -1688%`
- `speculative_acceptance_rate_mean = 0.04`
- `speculative_rebuild_count_mean = 74`
- `speculative_rebuild_tokens_total_mean = 2877`
- `exact_token_match = True`

Interpretation:

- the draft remains token-compatible enough for correctness
- but it is not close enough to the teacher to function as a useful speculative draft
- most rounds are zero-match rounds, so replay/rebuild work dominates runtime

This means the first untrained layer-subset draft is a valid baseline experiment, but not a viable serving solution.

That is the main reason the next step is shifting toward a planner-local `Medusa`-style upgrade rather than more naive draft shrinking.

## Why This Candidate Exists

We need a draft model that keeps:

- the same text-token interface
- the same speech-token vocabulary
- the same start/stop speech token semantics
- the same conditioning format
- the same CFG layout expectations

But we also need it to be cheaper.

The safest first reduction is:

- keep hidden size the same
- keep embeddings and output heads the same
- keep conditioning the same
- reduce only the number of transformer layers

That avoids immediate token-interface breakage.

## Current Design

The draft builder creates a new draft `T3` that:

- reuses the base multilingual token/conditioning interface
- reuses:
  - `cond_enc`
  - `text_emb`
  - `speech_emb`
  - `text_pos_emb`
  - `speech_pos_emb`
  - `text_head`
  - `speech_head`
- reuses the backbone normalization / embedding stubs where relevant
- executes only a selected subset of transformer layers

Current layer-selection modes:

- `even`
- `first`
- `last`

## Why Hidden Size Was Not Reduced Yet

We did not shrink hidden size in this first draft candidate.

Reason:

- keeping hidden size fixed keeps the interface directly compatible with the existing embeddings, heads, and conditioning stack
- that lets us build a real cheaper draft candidate now, without first solving projection or remapping problems

This is a pragmatic first step, not the final optimized draft architecture.

## What This Candidate Should Prove

This layer-subset draft should answer:

- can a truly separate cheaper multilingual draft preserve enough acceptance rate to matter?
- how much latency changes once the draft is genuinely cheaper than the verifier?
- whether GPU behavior improves at all with a real draft

The first experiment answered this negatively for the untrained layer-subset version.

More concretely, it proved:

- interface compatibility can be preserved
- correctness can still hold end to end
- that alone is nowhere near enough if the draft is not behaviorally close to the teacher

## What It Does Not Solve Yet

- it is not trained or distilled specifically as a draft model
- acceptance rate may drop relative to self-draft
- mismatch resync still needs to be watched carefully
- it may still be too narrow to saturate GPU well at low concurrency

Based on the first benchmark, the most important missing ingredient is now explicit:

- the draft needs behavioral closeness to the teacher, not just interface compatibility

## Suggested First Test

Use the prototype benchmark with a real layer-subset draft, for example:

```bash
PYTHONPATH=external/chatterbox/src python external/chatterbox/benchmark_t3_speculative_prototype.py \
  --device cuda \
  --language-id ar \
  --audio-prompt-path "$PROMPT_AUDIO" \
  --text "مرحبا، هذا اختبار للبنية الحالية." \
  --max-new-tokens 128 \
  --speculate-k 4 \
  --draft-mode layer_subset \
  --draft-layers 12 \
  --draft-layer-selection even \
  --warmup-runs 2 \
  --runs 6
```

## What To Watch

- `exact_token_match`
- `first_mismatch_index`
- `speculative_acceptance_rate_mean`
- `speculative_rebuild_count_mean`
- `speculative_rebuild_tokens_total_mean`
- `speculative_match_len_hist_total`
- `speculative_t3_s_mean`
- `speculative_vs_baseline_speedup_pct`
- peak allocated memory deltas
- your observed GPU-util behavior during the run

With the current layer-subset draft, these replay metrics are the clearest explanation for the extreme slowdown.

## Updated Takeaway

The compatible-draft question is now more specific:

- interface compatibility alone is not enough
- a useful draft must also be behaviorally close to the teacher

That pushes the next step toward one of two directions:

1. a trained/distilled compatible draft model
2. a token-compatible planner re-architecture that is more parallel by design

Current preference:

- keep this layer-subset draft as the negative baseline
- move the next active work toward planner-local multi-token heads
- reuse the speculative harness to verify compatibility and shape boundaries during that work

## Short Summary

The first real draft-model direction is now clear:

- self-draft proved correctness
- layer-subset multilingual `T3` was the first actual cheaper compatible draft candidate
- that candidate failed badly on acceptance and triggered massive replay churn
- the next serious draft path is either trained/distilled compatibility or a `Medusa`-style planner re-architecture, not naive layer subsetting
