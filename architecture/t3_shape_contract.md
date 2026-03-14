# T3 Shape Contract

_Last updated: 2026-03-14_

## Purpose

This note freezes the current `T3` runtime boundary for the multilingual scheduled path.

The goal is to avoid speculative-decoding bugs caused by guessing tensor shapes, cache layout, or per-request state ownership.

This is not a final speculative design doc. It is the current shape and state contract for the production `scheduled` `T3` path.

## Scope

Focused path:

- [worker_scheduled.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/runtime/worker_scheduled.py)
- [scheduled_decode.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/inference/scheduled_decode.py)
- [t3.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/t3.py)
- [t3_hf_backend.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/inference/t3_hf_backend.py)
- [cond_enc.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/modules/cond_enc.py)

This file only describes the current `T3` planner path up to emitted speech tokens.

## High-Level Role

`T3` is the speech-token planner.

It takes:

- request-local conditioning
- text tokens
- previously generated speech tokens

and autoregressively predicts the next speech token.

`S3` is downstream and unchanged by this note.

## Runtime Boundary

### Request In

Current scheduled requests are created in [worker_scheduled.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/runtime/worker_scheduled.py#L81).

Fields:

- `session_id`
- `t3_cond`
- `text_tokens`
- `max_new_tokens`
- `temperature`
- `top_p`
- `min_p`
- `repetition_penalty`
- `cfg_weight`

### Request-State Inside T3

Current scheduled per-request mutable state is defined in [scheduled_decode.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/inference/scheduled_decode.py#L42).

Fields:

- `generated_ids`
- `predicted_tokens`
- `alignment_state`
- `past_key_values`
- `decode_step`
- `next_inputs_embeds`

### Output Out

The scheduled decode loop returns:

- `predicted_tokens` per request

Those tokens are then filtered and passed to `S3`.

## Exact Current Production Behavior

### 1. CFG Duplication Happens Before T3

In [worker_scheduled.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/runtime/worker_scheduled.py#L65), text tokens are duplicated before the scheduled decode request is created:

- `text_tokens = torch.cat([text_tokens, text_tokens], dim=0)`

That means one logical request already enters `T3` with `2` rows:

- row `0`: conditional
- row `1`: unconditional

So for the current scheduled multilingual path, a single logical request already has batch dimension `2` before `T3` prefill starts.

### 2. Prefill Input Assembly

In [t3.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/t3.py#L105), `prepare_input_embeds()` builds:

- `cond_emb`
- `text_emb`
- `speech_emb`

and concatenates them into `embeds`.

Then [scheduled_decode.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/inference/scheduled_decode.py#L114) creates a BOS speech embedding and appends it.

So the actual transformer prefill input is:

- `embeds` from `prepare_input_embeds()`
- plus one extra BOS speech embedding row

### 3. Decode Step Shape

After prefill, each later decode round sends exactly one new speech-token embedding back into the transformer with KV cache.

That happens in [scheduled_decode.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/inference/scheduled_decode.py#L221).

Per request, the shape is:

- `(2, 1, D)` `(cfg_rows, decode_step_token_len, hidden_size)`

where the `2` is the CFG cond/uncond pair.

### 4. Logit Combination

Raw step logits come back with both CFG rows. Then [scheduled_decode.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/inference/scheduled_decode.py#L241) combines them:

- `cond = logits_step[0::2, :]`
- `uncond = logits_step[1::2, :]`
- `logits = cond + cfg_weights * (cond - uncond)`

So:

- transformer raw output is still per CFG row
- committed sampling logits become one row per logical request

## Exact Shapes Confirmed From Trace

These came from the `scheduled`, `concurrency=1`, `--trace-shapes` runs on 2026-03-14.

Dimension labels used below are semantic mnemonics, not code symbols:

- `cfg_rows`
- `shared_pos_rows`
- `logical_request_rows`
- `cond_seq_len`
- `text_seq_len`
- `speech_seed_len`
- `bos_token_len`
- `prefill_seq_len_no_bos`
- `prefill_seq_len_with_bos`
- `decode_step_token_len`
- `cache_seq_len`
- `cache_seq_len_plus_1`
- `token_len`
- `hidden_size`
- `vocab_size`
- `num_heads`
- `head_dim`
- `emitted_token_len_with_eos`
- `emitted_token_len_no_eos`

### Worker Entry

- `text_tokens`: `(2, 36)` `(cfg_rows, text_seq_len)` `torch.int32` `cuda:0`

### T3 Input Embeddings

From [t3.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/t3.py):

- `cond_emb`: `(2, 34, 1024)` `(cfg_rows, cond_seq_len, hidden_size)` `torch.float32` `cuda:0`
- `text_emb`: `(2, 36, 1024)` `(cfg_rows, text_seq_len, hidden_size)` `torch.float32` `cuda:0`
- `speech_emb`: `(2, 1, 1024)` `(cfg_rows, speech_seed_len, hidden_size)` `torch.float32` `cuda:0`
- `embeds`: `(2, 71, 1024)` `(cfg_rows, prefill_seq_len_no_bos, hidden_size)` `torch.float32` `cuda:0`
- `len_cond`: `34`

Interpretation:

- hidden size `D = 1024`
- prefill sequence before extra BOS append is `34 + 36 + 1 = 71`

### Scheduled Prefill Batch

From [scheduled_decode.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/inference/scheduled_decode.py):

- `prefill.input text_tokens`: `(2, 36)` `(cfg_rows, text_seq_len)` `torch.int64` `cuda:0`
- `prefill.input embeds`: `(2, 71, 1024)` `(cfg_rows, prefill_seq_len_no_bos, hidden_size)` `torch.float32` `cuda:0`
- `prefill.bos bos_pos_embed`: `(1, 1, 1024)` `(shared_pos_rows, bos_token_len, hidden_size)` `torch.float32` `cuda:0`
- `prefill.bos bos_embed`: `(2, 1, 1024)` `(cfg_rows, bos_token_len, hidden_size)` `torch.float32` `cuda:0`
- `prefill.batch inputs_embeds`: `(2, 72, 1024)` `(cfg_rows, prefill_seq_len_with_bos, hidden_size)` `torch.float32` `cuda:0`
- `prefill.output logits`: `(2, 72, 8194)` `(cfg_rows, prefill_seq_len_with_bos, vocab_size)` `torch.float32` `cuda:0`
- `prefill.output past_key_values[0][0]`: `(2, 16, 72, 64)` `(cfg_rows, num_heads, cache_seq_len, head_dim)` `torch.float32` `cuda:0`
- `prefill.output past_key_values[0][1]`: `(2, 16, 72, 64)` `(cfg_rows, num_heads, cache_seq_len, head_dim)` `torch.float32` `cuda:0`

Interpretation:

- scheduled runtime appends one BOS speech embed after `prepare_input_embeds()`
- final prefill sequence length in this trace is `72`
- speech-token vocabulary `V` is confirmed as `8194`
- first-layer KV cache shape confirms:
  - `2` CFG rows
  - `16` attention heads
  - cached sequence length `72`
  - head dimension `64`

### Cached Decode Step

Repeated decode rounds show:

- `decode.batch inputs_embeds`: `(2, 1, 1024)` `(cfg_rows, decode_step_token_len, hidden_size)` `torch.float32` `cuda:0`
- `decode.next_token_pos_embed`: `(1, 1, 1024)` `(shared_pos_rows, decode_step_token_len, hidden_size)` `torch.float32` `cuda:0`
- `decode.next_token_embed_base`: `(1, 1, 1024)` `(logical_request_rows, decode_step_token_len, hidden_size)` `torch.float32` `cuda:0`
- `decode.output.first_cached_step logits`: `(2, 1, 8194)` `(cfg_rows, decode_step_token_len, vocab_size)` `torch.float32` `cuda:0`
- `decode.output.first_cached_step past_key_values[0][0]`: `(2, 16, 73, 64)` `(cfg_rows, num_heads, cache_seq_len_plus_1, head_dim)` `torch.float32` `cuda:0`
- `decode.output.first_cached_step past_key_values[0][1]`: `(2, 16, 73, 64)` `(cfg_rows, num_heads, cache_seq_len_plus_1, head_dim)` `torch.float32` `cuda:0`

Interpretation:

- after prefill, the entire decode loop is a sequence of extremely narrow cached steps
- this is one of the main reasons GPU saturation is poor
- one newly sampled token is embedded as `(1, 1, 1024)` `(logical_request_rows, decode_step_token_len, hidden_size)` and then duplicated back to `(2, 1, 1024)` `(cfg_rows, decode_step_token_len, hidden_size)` for CFG
- raw first cached-step logits are now explicitly confirmed as `(2, 1, 8194)` `(cfg_rows, decode_step_token_len, vocab_size)`
- first-layer KV cache grows from sequence length `72` to `73` after one cached decode step, exactly as expected

### Final Token Output

From the two trace runs:

- `predicted_tokens`: `(1, 94)` `(logical_request_rows, emitted_token_len_with_eos)` `torch.int64` `cuda:0`
- filtered `speech_tokens`: `(93,)` `(emitted_token_len_no_eos,)` `torch.int64` `cuda:0`
- `predicted_tokens`: `(1, 96)` `(logical_request_rows, emitted_token_len_with_eos)` `torch.int64` `cuda:0`
- filtered `speech_tokens`: `(95,)` `(emitted_token_len_no_eos,)` `torch.int64` `cuda:0`

Interpretation:

- one EOS token was emitted and then removed before `S3`

## Invariants We Now Know

These are strong enough to treat as the current production contract.

### Per Logical Request

- CFG expands each request into exactly `2` rows inside `T3`
- hidden size is currently `1024`
- current prefill shape is `(<cfg_rows>, <prefill_seq_len_with_bos>, <hidden_size>)`
- current cached decode step shape is always `(<cfg_rows>, <decode_step_token_len>, <hidden_size>)`

### State Ownership

Per request we already know we need:

- request-local `past_key_values`
- request-local `generated_ids`
- request-local `predicted_tokens`
- request-local `decode_step`
- request-local alignment state

That means speculative decoding should wrap the existing per-request decode state, not replace the outer request boundary.

### Where Speculation Would Fit

Speculation belongs inside the current one-token decode loop in [scheduled_decode.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/inference/scheduled_decode.py#L190).

The outer boundary should remain:

- same request in
- same speech tokens out

Only the inner decode engine changes.

## Missing Shape Details Still Needed

These are the remaining items not yet fully locked down by the current trace.

### Transformer Output Shapes

Already confirmed:

- prefill `output.logits.shape = (2, 72, 8194)` `(cfg_rows, prefill_seq_len_with_bos, vocab_size)`
- first cached decode-step `output.logits.shape = (2, 1, 8194)` `(cfg_rows, decode_step_token_len, vocab_size)`

### KV Cache Shapes

Already confirmed:

- prefill `past_key_values[0][0].shape = (2, 16, 72, 64)` `(cfg_rows, num_heads, cache_seq_len, head_dim)`
- prefill `past_key_values[0][1].shape = (2, 16, 72, 64)` `(cfg_rows, num_heads, cache_seq_len, head_dim)`
- first cached decode-step `past_key_values[0][0].shape = (2, 16, 73, 64)` `(cfg_rows, num_heads, cache_seq_len_plus_1, head_dim)`
- first cached decode-step `past_key_values[0][1].shape = (2, 16, 73, 64)` `(cfg_rows, num_heads, cache_seq_len_plus_1, head_dim)`

### Positional Embedding Shape

Already confirmed:

- `speech_pos_emb.get_fixed_embedding(0).shape = (1, 1, 1024)` `(shared_pos_rows, token_len, hidden_size)`
- first decode-step positional embedding shape is also `(1, 1, 1024)` `(shared_pos_rows, token_len, hidden_size)`

This means the current positional-embedding boundary is consistent with a blockwise speculative design, but later positions should still be assumed to use the same fixed-embedding API rather than hard-coded.

### One Useful Trace Observation

The first cached-step trace is now confirmed, and it matches the expected cache-growth pattern exactly:

- prefill cache length: `72`
- first cached-step cache length: `73`

That means the scheduled runtime’s current cache evolution is consistent with a speculative prototype that:

- reuses prefill KV state
- feeds one or more cached speech-token embeddings afterward
- expects sequence length to grow by the number of verified tokens

## What Is Still Missing

At this point, the main remaining uncertainty is no longer tensor shape.

The main remaining correctness risk is:

- causal verifier alignment

Concretely:

- when the target verifies a block of proposed speech tokens, which returned logits correspond to which proposed token positions
- how accepted-prefix and correction-token replay should align with the target KV cache

That is the place where speculative-decoding implementations usually go wrong.

### Causal Verification Alignment

Need one correctness trace or code-level check for:

- which verifier logits correspond to draft token `t1`
- which correspond to `t2`
- and so on

This is the main place speculative-decoding pseudocode is often wrong.

## Why This Matters For Speculative Decoding

The speculative path must be built around the real current shape contract, not a generic LLM assumption.

Current production `T3` has these repo-specific properties:

- CFG duplication already exists before scheduled decode
- per-request runtime state already exists
- alignment guard can mutate logits before token commit
- cached decode step is extremely narrow: `(2, 1, 1024)` `(cfg_rows, decode_step_token_len, hidden_size)`

So the right mental model is:

- speculation does not replace `T3`
- speculation wraps the current scheduled `T3` decode loop
- the target model is still the real multilingual `T3`
- the draft model only proposes candidate speech tokens

## Recommended Next Step

The shape contract is now good enough for a speculative prototype.

The next work should focus on:

- correct `prefill`
- correct one-step cached decode
- correct block-verification alignment
- hard runtime asserts around:
  - logits shape
  - KV cache length growth
  - accepted-prefix / correction-token alignment

In other words:

- the remaining blocker is mostly logic correctness, not missing tensor metadata.
