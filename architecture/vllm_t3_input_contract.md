# vLLM T3 Input Contract Debug Guide

This note is a focused debug guide for the T3 input boundary only.

Scope:
- compare baseline T3 input assembly vs vLLM prompt assembly
- do not run autoregressive decode
- do not run S3 or vocoder

## Why This Exists

The current failure class can produce:
- valid-length waveforms with low or empty content
- shape-stable runs for fixed text but failures for changing text

That usually means the request contract entering T3 is drifting, even when decode still runs.

## Contract Pieces

The current vLLM internal-prompt path assembles three pieces:
- text-side token ids
- prompt speech token path
- conditioning tensors

Concrete components in code:
- text ids and prompt token packing: `build_vllm_prompt(...)` in `src/chatterbox/vllm_t3_bridge.py`
- conditioning payload handoff: `multi_modal_data["conditioning"]` in `src/chatterbox/vllm_t3_bridge.py`
- served-model reconstruction of embeds: `ChatterboxT3ForCausalLM._build_inputs_embeds(...)` in `src/chatterbox/vllm_t3_model.py`
- baseline reference input assembly: `ChatterboxMultilingualTTS.generate(...)` and `T3.prepare_input_embeds(...)`

## New Diagnostic Script

Script path:
- `external/chatterbox/inspect_t3_input_contract.py`

What it does:
- loads baseline `ChatterboxMultilingualTTS`
- prepares conditionals from one prompt audio
- builds baseline text-token + conditioning + initial-speech input contract
- builds vLLM prompt + multimodal conditioning contract
- compares boundary invariants and token alignment
- writes optional JSON report

Important:
- this script intentionally stops before decode
- it is designed for contract debugging, not quality benchmarking

## Output Sections

The script prints:
- baseline contract summary
- vLLM contract summary
- alignment checks

Alignment checks currently include:
- exact match of baseline single-row text tokens vs vLLM text segment (after removing offset)
- `cond_seq_len` agreement
- boundary token checks (`conditioning_token_id`, two BOS speech prefix)
- first mismatch index when token lists diverge

## Run Command

From repo root:

```bash
cd /home/ubuntu/ChatterBox_S3_Concurrency
PYTHONPATH=external/chatterbox/src python external/chatterbox/inspect_t3_input_contract.py \
  --device cuda \
  --audio-prompt-path "$PROMPT_AUDIO" \
  --language-id ar \
  --text "مرحبا، هذا اختبار لعقد الإدخال بين baseline و vllm." \
  --cfg-weight 0 \
  --output-json prompt_contract_report.json
```

If you want to compare against a specific local checkpoint dir:

```bash
cd /home/ubuntu/ChatterBox_S3_Concurrency
PYTHONPATH=external/chatterbox/src python external/chatterbox/inspect_t3_input_contract.py \
  --device cuda \
  --checkpoint-dir ~/.cache/huggingface/hub/models--ResembleAI--chatterbox/snapshots/05e904af2b5c7f8e482687a9d7336c5c824467d9 \
  --audio-prompt-path "$PROMPT_AUDIO" \
  --language-id ar \
  --text "مرحبا، هذا اختبار لعقد الإدخال بين baseline و vllm." \
  --cfg-weight 0 \
  --output-json prompt_contract_report.json
```

## Reading The Result

Healthy minimum:
- `text_tokens_exact_match=true`
- `cond_seq_len_match=true`
- `conditioning_token_matches_layout=true`
- `last_two_prompt_tokens_are_bos=true`

If token mismatch appears:
- inspect `text_token_mismatch_index`
- inspect `baseline.single_row_text_tokens`
- inspect `vllm.prompt_token_parts.text_tokens_without_offset`

If `cond_seq_len` mismatch appears:
- inspect `baseline.len_cond`
- inspect `vllm.meta.cond_seq_len`
- inspect `get_conditioning_seq_len(...)` expectations

## Current Intent

Use this script before touching decode logic.
If this contract is not aligned, decode-side changes will hide root cause instead of fixing it.
