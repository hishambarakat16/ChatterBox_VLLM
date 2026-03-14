# T3 Speculative Shape Contract

_Last updated: 2026-03-14_

## Purpose

This note freezes the current working contract for the experimental `T3` speculative-decoding prototype.

The goal is to preserve the exact shapes, boundaries, and correctness signals that were confirmed to work, so future changes do not have to re-discover them by trial and error.

This is not a production-serving design doc. It is a confirmed prototype contract.

## Scope

Prototype files:

- [draft_model.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/inference/draft_model.py)
- [speculative_decode.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/inference/speculative_decode.py)
- [benchmark_t3_speculative_prototype.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/benchmark_t3_speculative_prototype.py)

Reference production path:

- [scheduled_decode.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/inference/scheduled_decode.py)
- [t3.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/t3.py)

## Current Working Mode

The prototype currently runs in:

- self-draft mode
- greedy decode
- `cfg_weight=0.5` kept on
- alignment guard off

That means:

- the current multilingual `T3` acts as both draft and verifier
- the prototype proves correctness and shape alignment
- it does not yet prove real production speedup

A separate draft-model scaffold now also exists:

- `draft_mode = layer_subset`
- same multilingual token interface
- same conditioning path
- same BOS/EOS semantics
- same embeddings and output heads
- fewer transformer layers selected from the base multilingual `T3`

## External Boundary

Inputs into the prototype:

- `ScheduledDecodeRequest`
- real multilingual `t3_cond`
- real duplicated CFG `text_tokens`
- real session options from the scheduled runtime path

Outputs from the prototype:

- `speech_tokens`
- speculative bookkeeping:
  - `rounds`
  - `proposed_tokens_total`
  - `accepted_draft_tokens_total`
  - `correction_tokens_total`

The prototype does not change `S3`.

## Confirmed Request Shape

From the prototype benchmark run:

- `text_tokens_shape = (2, 36)`

Interpretation:

- one logical request already enters `T3` as 2 CFG rows
- row `0` is conditional
- row `1` is unconditional

## Confirmed Prefill Contract

Observed working shapes:

- `cond_emb = (2, 34, 1024)`
- `text_emb = (2, 36, 1024)`
- `speech_emb = (2, 1, 1024)`
- `embeds = (2, 71, 1024)`
- `bos_pos_embed = (1, 1, 1024)`
- `bos_embed = (2, 1, 1024)`
- `inputs_embeds = (2, 72, 1024)`
- `raw_logits = (2, 72, 8194)`
- `next_logits = (1, 8194)`
- initial `kv_seq_len = 72`

Interpretation:

- hidden size is `1024`
- speech-token vocab is `8194`
- prefill returns one CFG-combined next-token distribution with shape `(1, 8194)`

## Confirmed Step-Input Contract

### Single Token Step

Observed working shapes:

- `tokens = (1, 1)`
- `base_embed = (1, 1, 1024)`
- `pos_embed = (1, 1, 1024)`
- `duplicated = (2, 1, 1024)`

Interpretation:

- one sampled token is embedded once
- positional embedding is added at shape `(1, 1, 1024)`
- the result is duplicated back to `2` rows for CFG

### Verify Block Step

For `speculate_k = 4`, observed working shapes:

- `tokens = (1, 4)`
- `base_embed = (1, 4, 1024)`
- `pos_embed = (1, 4, 1024)`
- `duplicated = (2, 4, 1024)`

Interpretation:

- block verification is already confirmed to work on multi-token inputs
- the verifier block is built by embedding the full draft block, then duplicating to CFG rows

## Confirmed Verify Contract

For `speculate_k = 4`, observed working shapes:

- `block_inputs = (2, 4, 1024)`
- `raw_block_logits = (2, 4, 8194)`
- `cfg_block_logits = (1, 4, 8194)`

Interpretation:

- verifier forward over a token block works correctly
- CFG combine reduces the 2-row verifier output to a single logical request row

## Confirmed KV Cache Contract

Observed working KV behavior:

- prefill `kv_seq_len = 72`
- after first accepted block: `76`
- then `80`, `84`, `88`, ...

Interpretation:

- accepted block length `K` increases cache length by exactly `+K`
- with `speculate_k = 4`, the verifier KV grows by `+4` per fully accepted round

This is one of the most important confirmed invariants.

## Confirmed Prototype Correctness

From the successful prototype run:

- `speculate_k = 4`
- `max_new_tokens = 64`
- `speculative_rounds = 16`
- `speculative_proposed_tokens_total = 64`
- `speculative_accepted_draft_tokens_total = 64`
- `speculative_correction_tokens_total = 0`
- `speculative_acceptance_rate = 1.0000`
- `exact_token_match = True`
- `first_mismatch_index = None`

Interpretation:

- self-draft speculative decoding is wired correctly
- verifier alignment is correct
- cache advancement is correct
- committed speculative tokens exactly matched baseline greedy tokens

## Confirmed Audio Output Contract

Observed rendered output:

- `baseline_rendered_token_count = 64`
- `speculative_rendered_token_count = 64`
- `baseline_rendered_num_samples = 61440`
- `speculative_rendered_num_samples = 61440`

Interpretation:

- both paths rendered the same token count
- both paths rendered the same waveform length
- the prototype preserved end-to-end token equivalence through `S3`

## What This Does Prove

- the speculative wrapper can sit around the current `T3` decode loop
- the prefill, draft, verify, and commit boundaries are shape-correct
- causal verifier alignment is correct for the current greedy self-draft mode
- block verification with CFG row duplication is working

## What This Does Not Prove

- it does not yet prove real GPU-saturation improvement
- it does not yet prove production latency improvement
- it does not yet prove concurrency improvement
- it does not yet prove anything about a smaller external draft model

Important updated caution:

The fair repeated benchmark now shows that self-draft is slower and heavier than baseline.

Measured with:

- `max_new_tokens = 128`
- `warmup_runs = 2`
- `runs = 6`
- alternating order between baseline-first and speculative-first

Observed:

- `baseline_t3_s_mean ~= 1.68s`
- `speculative_t3_s_mean ~= 2.12s`
- `speculative_vs_baseline_speedup_pct ~= -26%`
- `baseline_peak_allocated_delta_mb ~= 151.8`
- `speculative_peak_allocated_delta_mb ~= 230.5`
- `exact_token_match = True`
- `speculative_acceptance_rate_mean = 1.0`

Interpretation:

- self-draft remains a correctness scaffold
- it is not a performance path
- the benchmark is now telling the truth

## Likely Explanation For Audio Tail Trimming

The benchmark was run with:

- `max_new_tokens = 64`

So if the output sounds slightly clipped at the end, the first suspect is the hard token cap, not speculative-decoding mismatch.

That matches the observed facts:

- exact token match was true
- both baseline and speculative outputs rendered exactly 64 tokens

Follow-up confirmation:

- rerunning with `max_new_tokens = 128` produced natural stopping at `86` tokens
- rendered audio sounded correct with no tail clipping
- so the earlier clipping was effectively confirmed to be a token-cap artifact

## Current Safe Next Steps

1. Keep this prototype as the correctness reference path.
2. Make latency measurement fair with warmup and alternating benchmark order.
3. Use a real smaller compatible draft model instead of self-draft.
4. Start with the layer-subset multilingual draft scaffold.
5. Only then treat throughput or GPU-saturation numbers as architecture evidence.

## Short Summary

The speculative prototype is currently correct in the ways that matter most for implementation safety:

- shapes line up
- cache growth lines up
- verifier alignment lines up
- emitted tokens match baseline exactly

The remaining uncertainty is no longer shape correctness. The remaining uncertainty is whether a real draft model can improve GPU utilization and latency under realistic serving conditions.
