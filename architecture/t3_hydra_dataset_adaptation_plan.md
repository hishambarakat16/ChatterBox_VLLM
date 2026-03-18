# T3 Hydra Dataset Adaptation Plan

_Last updated: 2026-03-15_

## Purpose

This note records:

- whether the current Medusa distill dataset can be reused for `Hydra`
- exactly what is missing if we try to match the official Hydra training path
- what should change in our local dataset builder instead of forcing a bad fit
- why `Hydra` is currently a stronger next step than plain `Medusa` for multilingual `T3`

Relevant local files:

- [build_t3_medusa_distill_dataset.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/build_t3_medusa_distill_dataset.py)
- [t3_medusa_code_read_memo.md](/Users/hisham/Code/Bahraini_TTS/architecture/t3_medusa_code_read_memo.md)
- [t3_shape_contract.md](/Users/hisham/Code/Bahraini_TTS/architecture/t3_shape_contract.md)
- [t3_speculative_shape_contract.md](/Users/hisham/Code/Bahraini_TTS/architecture/t3_speculative_shape_contract.md)
- [external/Hydra/hydra/train/train.py](/Users/hisham/Code/Bahraini_TTS/external/Hydra/hydra/train/train.py)
- [external/Hydra/hydra/model/hydra_model.py](/Users/hisham/Code/Bahraini_TTS/external/Hydra/hydra/model/hydra_model.py)
- [external/Hydra/hydra/data/build_hidden_states.py](/Users/hisham/Code/Bahraini_TTS/external/Hydra/hydra/data/build_hidden_states.py)

## Direct Answer

The current Medusa distill dataset is reusable as a `Hydra` starting corpus, but not as a drop-in Hydra dataset.

What is reusable now:

- the sample list
- normalized text
- multilingual language choice
- prompt conditioning path
- target speech tokens
- teacher decode settings

What is not yet reusable as-is:

- the file format expected by the official Hydra repo
- the supervision layout expected by Hydra training
- the per-step hidden-state side data used by the stronger Hydra training path

The practical recommendation is:

- do not throw away the current Medusa dataset
- do not try to force it directly into the official Hydra repo unchanged
- convert or extend it into a Chatterbox-specific Hydra dataset

## Why Hydra Is The Better Next Step Than Plain Medusa

This is a recommendation for the current `T3` path, not a universal claim.

Why `Hydra` currently looks stronger than plain `Medusa`:

- it stays in the same general serving family as Medusa:
  - one frozen backbone
  - extra draft heads
  - no separate draft model to maintain
- its heads are sequentially dependent instead of mostly independent
- that directly targets the main weakness we already saw with naive multi-token drafting:
  - low behavioral closeness to the teacher
  - low acceptance
  - replay dominating runtime
- it is a more natural next attempt after:
  - self-draft proving correctness
  - separate untrained AR draft proving that token compatibility alone is not enough

Why this matters for our repo:

- current `T3` is bottlenecked by many small AR decode steps
- current draft failure suggests acceptance quality is the real issue
- `Hydra` is specifically trying to improve draft-head prediction quality over `Medusa`

So the current ordering is:

1. `Hydra`
2. `Medusa` fallback if Hydra proves too invasive
3. `EAGLE-3` later if we want a more aggressive feature-space path

## What The Current Medusa Builder Produces

The current dataset builder in [build_t3_medusa_distill_dataset.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/build_t3_medusa_distill_dataset.py) emits one JSONL record per sample with:

- `sample_id`
- `text`
- `normalized_text`
- `language_id`
- `audio_prompt_path`
- `conditionals_path`
- `text_tokens`
- `speech_tokens`
- `num_text_tokens`
- `num_speech_tokens`
- `teacher_decode`
- `source_wav_path`
- `source_duration`

That is already a good `T3` teacher corpus.

What it does not currently store:

- per-step base-model hidden states
- per-step teacher logits or teacher probabilities
- any Hydra-head-specific targets
- any explicit `input_ids / labels / attention_mask` arrays in the official Hydra format

## What Official Hydra Expects

The official Hydra repo supports two broad data paths.

### Path A: raw dataset

In [train.py](/Users/hisham/Code/Bahraini_TTS/external/Hydra/hydra/train/train.py), the raw dataset path expects standard causal-LM-style tensors:

- `input_ids`
- `labels`
- `attention_mask`

This is built around text-token chat data, not our `T3` planner interface.

### Path B: precomputed dataset

The precomputed path in [train.py](/Users/hisham/Code/Bahraini_TTS/external/Hydra/hydra/train/train.py) and [build_hidden_states.py](/Users/hisham/Code/Bahraini_TTS/external/Hydra/hydra/data/build_hidden_states.py) expects:

- `input_ids.npy`
- `labels.npy`
- `attention_masks.npy`
- `base_hidden_states.npy`

So the stronger official Hydra path uses precomputed base hidden states, but they are not conceptually part of our current Medusa dataset.

## Why The Official Hydra Dataset Shape Does Not Match T3 Cleanly

Official Hydra assumes a normal causal LM that consumes token IDs directly.

Current multilingual `T3` does not work like that.

From [t3_shape_contract.md](/Users/hisham/Code/Bahraini_TTS/architecture/t3_shape_contract.md) and [t3_speculative_shape_contract.md](/Users/hisham/Code/Bahraini_TTS/architecture/t3_speculative_shape_contract.md), the important current facts are:

- one logical request becomes `2` CFG rows inside `T3`
- prefill uses `inputs_embeds`, not just plain `input_ids`
- traced prefill embed shape is `(2, 72, 1024)`
- traced cached decode-step embed shape is `(2, 1, 1024)`
- traced raw logits are `(2, 1, 8194)` at each cached step
- speech-token vocabulary is `8194`

So if we try to match Hydra literally, we would be pretending that `T3` is a normal token-ID causal LM. It is not.

That is why the right target is not:

- "make our dataset look exactly like ShareGPT Hydra data"

The right target is:

- "make a Chatterbox-native Hydra dataset aligned to the real `T3` planner boundary"

## What Needs To Change In Our Dataset For Hydra

There are two different answers depending on the goal.

### Option 1: match the official Hydra repo literally

This is possible in principle, but it is not the recommended path.

You would need to convert each training sample into:

- `input_ids`
- `labels`
- `attention_mask`
- optionally `base_hidden_states`

And you would still need a substantial `T3` adapter because:

- `T3` uses prompt conditioning from `conditionals_path`
- `T3` uses CFG two-row behavior
- `T3` predicts speech tokens, not text continuation tokens
- `T3` decode uses custom embedding assembly before the backbone

So this path adds conversion work but still does not remove the model-integration work.

### Option 2: build a Chatterbox-native Hydra dataset

This is the recommended path.

Keep the current JSONL sample structure and add the missing planner-side supervision we actually need.

What to add:

- a stable `sample_index` for array-backed sidecar features
- optional cached base hidden states for the planner decode positions
- optional cached teacher logits or top-k teacher targets for those positions
- explicit metadata that tells the trainer which decode positions are valid for Hydra-head supervision

What can stay:

- `text_tokens`
- `speech_tokens`
- `conditionals_path`
- `language_id`
- `teacher_decode`

## Recommended Builder Changes

Recommended new builder path:

- keep [build_t3_medusa_distill_dataset.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/build_t3_medusa_distill_dataset.py) as the current baseline builder
- add a new Hydra-specific companion builder instead of mutating the Medusa builder too aggressively

Suggested file:

- `external/chatterbox/build_t3_hydra_distill_dataset.py`

Why a separate builder is cleaner:

- the current builder is already useful and correct for Medusa-style work
- Hydra needs extra per-step supervision, not just final emitted speech tokens
- separating the builders avoids breaking the already-valid Medusa corpus format

## Exact New Data We Should Add

For each sample, the Hydra path should add or derive:

### 1. Planner supervision target sequence

Already available:

- `speech_tokens`

This stays the primary target sequence.

### 2. Decode-position validity metadata

Add:

- `num_decode_positions`
- `hydra_supervision_len`

These should reflect the number of speech-token prediction steps used for head supervision.

### 3. Optional cached base hidden states

Add either:

- a per-sample `.pt` sidecar path

or:

- sharded array-backed storage like:
  - `base_hidden_states.fp16.npy`
  - `base_hidden_states.index.json`

Natural T3-aligned hidden-state target shape:

- per decode position: `(2, 1, 1024)` raw CFG-row hidden state before `speech_head`
- or squeezed per position: `(2, 1024)`
- over a full sample: `(decode_len, 2, 1024)`

If we later decide to supervise only CFG-combined planner state, a derived logical-row view would be:

- `(decode_len, 1024)`

But the safer first target is still the raw CFG-row state because that matches the real model boundary.

### 4. Optional teacher-logit side data

Add if needed:

- top-k teacher speech-token ids per decode position
- top-k teacher logprobs per decode position

This is optional, but useful if we want a lighter training target than full logits.

## Shape And Input Validation We Should Enforce

These checks should be added to the Hydra builder and trainer because they are already stable in the current `T3` notes.

### Sample-level validation

- `text_tokens` must include start and stop text tokens
- `speech_tokens` must contain only valid speech-token ids
- `conditionals_path` must exist
- `language_id` must be supported
- `num_speech_tokens > 0`

### T3 boundary validation

For traced or cached planner states, validate:

- CFG rows are exactly `2`
- hidden size is exactly `1024`
- speech vocab size is exactly `8194`
- decode-step hidden/logit sequence uses step length `1`

### Trainer-side alignment validation

- target offsets must preserve the current planner semantics:
  - base head predicts offset `+1`
  - Hydra heads predict future offsets after that
- supervision length must never overrun the actual decoded speech-token sequence
- cached hidden-state count must match the number of supervised decode positions

## What Should Change In The Current Medusa Builder

Minimal recommended changes to the existing Medusa builder:

- leave the current JSONL schema intact
- add a stable `sample_index`
- add an optional flag to emit a second Hydra-side manifest or sidecar index
- add an optional flag to save extra planner traces for Hydra training

What should not be forced into the Medusa builder by default:

- full Hydra hidden-state dumping for every run
- official Hydra repo memmap format
- any assumption that `T3` training examples look like chat `input_ids`

## Related Chatterbox Files That Will Need Hydra-Aware Follow-Up

Dataset/build side:

- [build_t3_medusa_distill_dataset.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/build_t3_medusa_distill_dataset.py)

Model/inference side:

- [t3.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/t3.py)
- [speculative_decode.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/inference/speculative_decode.py)
- [draft_model.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/inference/draft_model.py)

The main expected follow-up is:

- replace "separate smaller AR draft" assumptions with "same-backbone future heads" assumptions

## Recommended Plan

1. Keep the current Medusa dataset as the base teacher corpus.
2. Add a Hydra-specific dataset builder, not a breaking rewrite of the Medusa builder.
3. Emit or derive per-step planner hidden states at the real `T3` boundary.
4. Keep validation tied to the current `T3` shape contract:
   - `2` CFG rows
   - hidden size `1024`
   - speech vocab `8194`
5. Build Hydra training around the real `T3` planner interface, not around chat-LM `input_ids` assumptions.

## Bottom Line

The current Medusa dataset is not wasted.

It is already the right teacher corpus for Hydra in the sense that it contains:

- the right prompts
- the right conditionals
- the right target speech-token sequences

What Hydra still needs is not a different corpus. It needs richer planner-side supervision and a `T3`-native training format.

That is why the right next move is:

- extend the dataset
- not replace it
- and keep the extension aligned to the actual `T3` shape contract instead of the official Hydra repo's text-LM assumptions
