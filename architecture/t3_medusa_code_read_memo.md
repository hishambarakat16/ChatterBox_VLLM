# T3 Medusa Code Read Memo

_Last updated: 2026-03-14_

## Purpose

This note records what the official `Medusa` code actually does, which parts are relevant to multilingual `T3`, and what the safest first integration boundary looks like for this repo.

Reference clone:

- [external/Medusa](//Users/hisham/Code/Bahraini_TTS/external/Medusa)

Reference local planner code:

- [t3.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/t3.py)
- [speculative_decode.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/inference/speculative_decode.py)

Official Medusa commit inspected:

- `e2a5d20c048a9b0a4092e6933c34313687422518`

## Direct Answer

`Medusa` is compatible with our planner problem in spirit, but not as a direct drop-in.

Why:

- Medusa is designed for standard causal-LM `input_ids` decoding
- multilingual `T3` decode uses `inputs_embeds`, `CFG` row duplication, custom conditioning, and speech-position embeddings
- the official Medusa inference path also assumes a custom tree-attention path and a patched KV-cache-aware Hugging Face model

So the right first move is:

- reuse the Medusa idea
- not reuse the official inference code wholesale

The cleanest first adaptation is:

- add Medusa-style future-token heads to `T3`
- keep the current `T3` speech head as the verifier for the immediate next token
- use the existing speculative prototype as the verification harness

## What The Official Medusa Code Actually Does

### Core files

- [medusa_model.py](/Users/hisham/Code/Bahraini_TTS/external/Medusa/medusa/model/medusa_model.py)
- [medusa_model_legacy.py](/Users/hisham/Code/Bahraini_TTS/external/Medusa/medusa/model/medusa_model_legacy.py)
- [utils.py](/Users/hisham/Code/Bahraini_TTS/external/Medusa/medusa/model/utils.py)
- [kv_cache.py](/Users/hisham/Code/Bahraini_TTS/external/Medusa/medusa/model/kv_cache.py)
- [medusa_choices.py](/Users/hisham/Code/Bahraini_TTS/external/Medusa/medusa/model/medusa_choices.py)
- [train_legacy.py](/Users/hisham/Code/Bahraini_TTS/external/Medusa/medusa/train/train_legacy.py)

### Model structure

The official Medusa implementation adds extra heads on top of the last hidden state of the base model.

In [medusa_model.py](/Users/hisham/Code/Bahraini_TTS/external/Medusa/medusa/model/medusa_model.py):

- each head is a small `ResBlock` stack plus a vocab projection
- the heads operate on the final hidden state tensor from the base model
- the outputs are stacked as:
  - `medusa_logits: (num_heads, batch, seq, vocab)`

The original model head is still used separately for the immediate next token.

This is important:

- Medusa heads are not primarily replacing the base next-token head
- they are predicting further future positions from the same current hidden state

### Training logic

The clearest training code in this repo is in [train_legacy.py](/Users/hisham/Code/Bahraini_TTS/external/Medusa/medusa/train/train_legacy.py).

Key behavior:

- load base causal LM
- freeze the base model
- attach Medusa heads
- train only the new heads

The loss loop is the most important part:

- for head `i`, logits are shifted against labels by `2 + i`
- this means the base LM predicts the immediate next token
- Medusa head `0` predicts the token after that
- Medusa head `1` predicts one further ahead
- and so on

So if there are `H` Medusa heads:

- base head predicts offset `+1`
- Medusa heads predict offsets `+2 ... +(H+1)`

### Inference logic

Official Medusa inference is more than “top-1 from every head.”

In [utils.py](/Users/hisham/Code/Bahraini_TTS/external/Medusa/medusa/model/utils.py):

- `generate_medusa_buffers(...)` builds a tree-attention mask and retrieval maps
- `generate_candidates(...)` takes:
  - greedy or sampled base next token
  - top-k tokens from every Medusa head
  - combines them into a tree of candidate sequences
- `tree_decoding(...)` verifies all tree candidates in one forward pass
- `evaluate_posterior(...)` selects the best accepted prefix
- `update_inference_inputs(...)` updates the input sequence and rewrites the KV cache accordingly

So official Medusa is:

- multi-head future prediction
- plus tree-structured candidate verification
- plus custom cache/index rewriting

## Why Official Medusa Is Not A Direct Drop-In For T3

### 1. `T3` decode is embed-driven, not token-id-driven

Medusa expects:

- `input_ids`
- standard tokenizer-driven causal LM flow

Current multilingual `T3` decode uses:

- prepared conditioning embeddings
- custom speech token embeddings
- custom speech positional embeddings
- `inputs_embeds`
- manual `CFG` row duplication

So the official Medusa inference entrypoint cannot simply be pasted over `T3`.

### 2. `CFG` changes the correct boundary

Current `T3` speculative flow is built around two rows:

- conditional row
- unconditional row

Then logits are combined into one logical request row.

That means the Medusa-compatible boundary for `T3` is not:

- one hidden state in
- one head out

It is:

- hidden states from both CFG rows
- per-head logits for both rows
- then `CFG` combination per head

### 3. The official Medusa tree path assumes patched base-model internals

Medusa uses:

- custom `KVCache`
- custom `position_ids`
- custom tree masks
- patched `Llama` / `Mistral` model classes

That is a lot more invasive than what we want for the first `T3` experiment.

## Best First T3-Medusa Integration Boundary

The safest first adaptation is a simpler one than official Medusa inference.

### Proposed first integration

1. Keep the current `T3` backbone and current `speech_head`.
2. Add `H` Medusa-style future-token heads on top of the final hidden state.
3. During decode:
   - use current `speech_head` for token offset `+1`
   - use Medusa heads for offsets `+2 ... +(H+1)`
4. Build one linear proposed block from those predictions.
5. Verify that block with the existing speculative verifier in [speculative_decode.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/inference/speculative_decode.py).

This avoids:

- official tree-attention integration
- official custom KV rewriting logic
- immediate runtime surgery in the scheduled engine

It lets us answer the most important question first:

- are future-token heads behaviorally useful enough for `T3`?

## T3-Medusa Shape Boundary We Need To Confirm

For multilingual `T3`, the important hidden boundary is the last transformer hidden state before `speech_head`.

From the current confirmed speculative contract:

- prefill input embeds: `(2, 72, 1024)`
- prefill raw logits: `(2, 72, 8194)`
- decode step input embeds: `(2, 1, 1024)`
- verify block input: `(2, 4, 1024)`

### Likely Medusa head shapes for T3

If we attach `H` future-token heads to `T3`:

- decode hidden state into heads:
  - input hidden: `(2, 1, 1024)`
- per-head raw logits:
  - `(2, 1, 8194)`
- stacked raw Medusa logits:
  - `(H, 2, 1, 8194)`
- after CFG combine per head:
  - `(H, 1, 1, 8194)` or squeezed `(H, 8194)`

Then the first linear proposal block would be:

- base next token from current `speech_head`: shape `(1, 1)`
- Medusa future tokens from heads: shape `(1, H)`
- combined proposal block: `(1, H + 1)`

The verifier then sees:

- block inputs: `(2, H + 1, 1024)`
- block logits: `(2, H + 1, 8194)`
- CFG-combined block logits: `(1, H + 1, 8194)`

### Most important alignment fact

The official Medusa training shift means:

- base head corresponds to offset `+1`
- first Medusa head corresponds to offset `+2`

So for `T3`, head `0` should not duplicate the base `speech_head`.

That needs to remain explicit in our implementation and tracing.

## Exact Compatibility Checks To Run Before Integration

We should trace only the planner-middle section first.

### Check 1: decode hidden-state boundary

Need to log:

- final hidden state shape before `speech_head`
- both on prefill and on cached single-step decode

Expected:

- prefill hidden: `(2, seq, 1024)`
- cached step hidden: `(2, 1, 1024)`

### Check 2: Medusa head output boundary

Need to log:

- one head raw logits
- stacked head logits
- headwise CFG-combined logits

Expected:

- single head raw: `(2, 1, 8194)`
- stacked raw: `(H, 2, 1, 8194)`
- stacked CFG-combined: `(H, 1, 1, 8194)` or `(H, 8194)`

### Check 3: block proposal boundary

Need to log:

- base next token
- Medusa future tokens
- combined proposed block

Expected:

- base next token: `(1, 1)`
- future block: `(1, H)`
- full proposal: `(1, H + 1)`

### Check 4: verifier boundary

Use the existing verifier path to confirm:

- verify input embeds shape
- block logits shape
- accepted prefix length
- cache growth by accepted token count

This is the exact place where the current speculative harness remains useful.

## What Parts Of Medusa We Should Reuse Conceptually

### Reuse directly in spirit

- residual head structure
- shifted multi-head training objective
- idea that future-token heads sit on top of the current final hidden state

### Do not copy directly at first

- tree-attention path
- patched Hugging Face causal-LM internals
- custom KV rewriting code
- chat tokenizer / chat-template data pipeline

That is too invasive for a first `T3` integration.

## Training Plan For T3-Medusa

### Simplest first training recipe

`Medusa-1` style:

- freeze current multilingual `T3` backbone
- freeze current embeddings, conditioning path, and base `speech_head`
- train only the new future-token heads

This is the lowest-risk first experiment.

### Training target

Use the current `T3` speech-token prediction alignment.

At each valid speech position:

- base `speech_head` already corresponds to the immediate next token
- future heads should predict the next `H` future speech tokens beyond that

Loss shape idea:

- head `0` predicts offset `+2`
- head `1` predicts offset `+3`
- ...
- head `H-1` predicts offset `+(H+1)`

This should be implemented only on valid speech positions and padded with ignore indices where future tokens do not exist.

### Important local caveat

Before writing the loss, verify the exact speech-token training alignment in `T3` with a small traced batch.

Do not assume the shift from a plain text causal LM without checking the local speech-token convention first.

## If We Need To Create The Training Dataset

The official Medusa repo uses chat data and self-distillation utilities, but that is not our problem shape.

For `T3`, the right dataset unit is not a conversation.
It is a speech-token planning example.

### Best case: original paired training data exists

Then use real supervised examples containing:

- text
- language ID
- prompt audio / prompt speech tokens if used
- speaker conditioning
- target speech-token sequence

This is the best option because the student is anchored to real data, not only teacher outputs.

### If original data is unavailable: self-distillation dataset

Then generate a teacher dataset from the current multilingual `T3`.

For each example, store:

- text input
- language ID
- conditioning payload needed to rebuild `t3_cond`
- generated speech-token sequence from the current teacher

This gives a token-level imitation dataset for Medusa-head training.

### Practical dataset schema for this repo

Each sample should minimally contain:

- `text`
- `language_id`
- `speaker_embedding` or a reproducible pointer to it
- `prompt_speech_tokens` if used
- `prompt_features` / prompt metadata if needed to rebuild conditioning
- `speech_tokens`

If file size matters, save tokenized / preprocessed forms directly:

- `text_tokens`
- serialized conditioning tensors
- `speech_tokens`

### How To Generate It

1. Choose a text corpus or reuse existing training texts.
2. Pair each text with a prompt/voice conditioning source.
3. Run current multilingual `T3` greedily or with the target serving decode settings.
4. Save only the planner-relevant outputs:
   - text tokens
   - conditioning tensors or references
   - generated speech tokens
5. Use those sequences for shifted Medusa-head training.

### What Not To Do

- do not reuse Medusa's ShareGPT/chat pipeline directly
- do not build the dataset around text-only chat templates
- do not make the first dataset depend on an external OpenAI-compatible server

That is specific to their LLM setting, not ours.

## Recommended First Experiment

1. Add `H=3` or `H=4` future-token heads to `T3`.
2. Freeze the existing `T3` backbone.
3. Train only the new heads.
4. Use teacher-forced or self-distilled speech-token data.
5. During inference, build a linear proposal block:
   - base next token
   - plus top-1 future tokens from Medusa heads
6. Reuse the current speculative verifier to measure:
   - exact token match
   - acceptance rate
   - correction count
   - rebuild count
   - concurrency timing

Only after that should we consider:

- tree-style branching
- more invasive cache logic
- partial backbone unfreezing

## Bottom Line

Medusa is relevant, but the official implementation is not the integration blueprint.

The right first `T3` adaptation is:

- planner-local future-token heads
- `CFG`-aware head logits
- existing speculative verifier reused as the acceptance harness
- a local speech-token distillation dataset instead of Medusa's chat data pipeline

That is the shortest path that preserves our current `T3 -> S3` contract while testing whether Medusa-style planner acceleration is actually viable here.
