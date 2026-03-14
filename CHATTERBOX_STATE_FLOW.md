# Chatterbox State Flow

## Purpose

This file is the concrete reference for how data and state move through the current Chatterbox multilingual stack.

Use it for two things:

- avoid guessing about tensor shapes while changing concurrency behavior
- separate `shared immutable model state` from `per-request mutable decode state`

Visual companion:

- [architecture/chatterbox_serving_shape_current_vs_target.html](/Users/hisham/Code/Bahraini_TTS/architecture/chatterbox_serving_shape_current_vs_target.html)

Current status:

- the `concurrent` path now completes `2` and `4` simultaneous requests correctly on one shared model instance
- the next goal is to replace the coarse full-decode `T3` lock with a better scheduling model

## State Categories

### Shared Immutable Model State

These should stay on the long-lived worker and should not be rebuilt per request:

- `T3.tfmr`
- `T3.text_emb`
- `T3.speech_emb`
- `T3.speech_head`
- `S3Gen` weights
- `VoiceEncoder` weights
- `MTLTokenizer` vocab

### Per-Request Mutable State

These must not live on the shared `T3` object during active concurrent inference:

- `past_key_values`
- generated speech token history
- repetition / alignment state
- request prompt conditionals
- decode progress
- finished/error flags

### Shared Synchronized State

This belongs to a future scheduler, not the model object:

- pending request queue
- active request map
- batching window
- result handles

## Baseline End-To-End Flow

### 1. Request Entry

File:

- [external/chatterbox/src/chatterbox/mtl_tts.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/mtl_tts.py)

Function:

- `ChatterboxMultilingualTTS.generate(...)`

Input:

- `text: str`
- `language_id: str`
- `audio_prompt_path: str | None`
- generation scalars:
  - `exaggeration: float`
  - `cfg_weight: float`
  - `temperature: float`
  - `repetition_penalty: float`
  - `min_p: float`
  - `top_p: float`

Output:

- `torch.Tensor` waveform with shape roughly `[1, T_wav]`

Concurrency risk:

- baseline path mutates `self.conds` on the shared model object

### 2. Prompt Conditioning Build

File:

- [external/chatterbox/src/chatterbox/mtl_tts.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/mtl_tts.py)

Function:

- `prepare_conditionals(wav_fpath, exaggeration=0.5)`

Input:

- prompt wav path

Intermediate outputs:

- `s3gen_ref_wav`: `np.ndarray`, resampled to `24000 Hz`, truncated to `10 * 24000 = 240000` samples
- `ref_16k_wav`: `np.ndarray`, resampled to `16000 Hz`, truncated to `6 * 16000 = 96000` samples for T3 prompt-token use

Built T3 conditionals:

- `speaker_emb`: tensor `[1, 256]`
- `cond_prompt_speech_tokens`: tensor `[1, T_prompt]`, where `T_prompt <= 150`
- `emotion_adv`: tensor `[1, 1, 1]`

Built S3 reference dict:

- `prompt_token`: tensor `[1, T_ref_tokens]`
- `prompt_token_len`: tensor `[1]`
- `prompt_feat`: tensor `[1, T_ref_mels, 80]`
- `prompt_feat_len`: currently `None`
- `embedding`: speaker embedding tensor from CAMPPlus, typically utterance-level `[1, 192]`

Important invariant:

- `prompt_feat.shape[1] == 2 * prompt_token.shape[1]` after internal trimming

### 3. Text Normalization And Tokenization

Files:

- [external/chatterbox/src/chatterbox/mtl_tts.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/mtl_tts.py)
- [external/chatterbox/src/chatterbox/models/tokenizers/tokenizer.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/tokenizers/tokenizer.py)

Steps:

- `punc_norm(text)` returns normalized `str`
- `MTLTokenizer.text_to_tokens(...)` returns `torch.IntTensor` with shape `[1, T_text_raw]`
- baseline then duplicates for CFG:
  - `[1, T_text_raw] -> [2, T_text_raw]`
- start/stop tokens are padded:
  - final `text_tokens` shape is `[2, T_text_raw + 2]`

Token IDs from config:

- `start_text_token = 255`
- `stop_text_token = 0`

### 4. T3 Input Embedding Build

Files:

- [external/chatterbox/src/chatterbox/models/t3/t3.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/t3.py)
- [external/chatterbox/src/chatterbox/models/t3/modules/cond_enc.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/modules/cond_enc.py)

Function:

- `T3.prepare_input_embeds(...)`

Input:

- `t3_cond: T3Cond`
- `text_tokens: [2, T_text]`
- `speech_tokens`: initial BOS speech token(s), usually `[2, 1]`

Derived tensors:

- `cond_emb`: `[B, T_cond, D]`
- `text_emb`: `[B, T_text, D]`
- `speech_emb`: `[B, T_speech, D]`

Where:

- `B = 2` because of CFG
- `D = hidden_size` from `Llama_520M`
- `T_cond` is typically:
  - `1` speaker token
  - `+ perceiver-resampled prompt speech conditioning`
  - `+ 1` emotion token

Output:

- `embeds: [2, T_cond + T_text + T_speech, D]`
- `len_cond: int`

### 5. T3 Speech-Token Decode

Files:

- [external/chatterbox/src/chatterbox/models/t3/t3.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/t3.py)
- [external/chatterbox/src/chatterbox/models/t3/inference/t3_hf_backend.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/inference/t3_hf_backend.py)
- [external/chatterbox/src/chatterbox/models/t3/inference/alignment_stream_analyzer.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/inference/alignment_stream_analyzer.py)

Function:

- `T3.inference(...)`

Input:

- `t3_cond`
- `text_tokens: [2, T_text]`

Per-request mutable decode state that should exist here:

- `generated_ids`
- `predicted`
- `past_key_values`
- repetition processor state
- alignment analyzer state

Current shared-state problem:

- `self.compiled = False` is reset on each call
- `AlignmentStreamAnalyzer(...)` is rebuilt per call
- `self.patched_model` is rebuilt per call
- those objects are stored on the shared `T3` instance

Output:

- predicted speech tokens with shape `[1, T_speech_out]`

Speech token config:

- `start_speech_token = 6561`
- `stop_speech_token = 6562`
- `T3` speech vocab size = `8194`

Important note:

- `forcing EOS` is an alignment-integrity heuristic, not automatically a hard error
- it becomes suspicious only when it coincides with collapsed outputs or shape/runtime errors

### 6. Invalid Speech Token Drop

Files:

- [external/chatterbox/src/chatterbox/mtl_tts.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/mtl_tts.py)
- [external/chatterbox/src/chatterbox/models/s3gen/s3gen.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/s3gen/s3gen.py)

Function:

- `drop_invalid_tokens(speech_tokens)`

Input:

- `[T_speech_out]` or `[1, T_speech_out]`

Reason:

- `T3` can emit IDs up to `8193`
- `S3` codebook size is `6561`
- invalid IDs are removed before S3

Output:

- filtered speech token tensor containing only IDs `< 6561`

### 7. S3 Token-To-Mel

Files:

- [external/chatterbox/src/chatterbox/models/s3gen/s3gen.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/s3gen/s3gen.py)

Functions:

- `S3Gen.inference(...)`
- `S3Token2Mel.forward(...)`

Input:

- `speech_tokens`: `[1, T_speech_valid]`
- `ref_dict` from prompt conditioning stage

Internal note:

- current implementation assumes batch size `1`
- tokenizer name is `speech_tokenizer_v2_25hz`
- flow model uses `token_mel_ratio = 2`

Mel output:

- approximately `[1, 80, 2 * T_speech_valid]`

### 8. Vocoder

File:

- [external/chatterbox/src/chatterbox/models/s3gen/s3gen.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/s3gen/s3gen.py)

Function:

- `HiFTGenerator.inference(...)` via `S3Gen.hift_inference(...)`

Input:

- mel features `[1, 80, T_mel]`

Output:

- waveform `[1, T_wav]`

### 9. Watermark And Return

Files:

- [external/chatterbox/src/chatterbox/mtl_tts.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/mtl_tts.py)
- [external/chatterbox/src/chatterbox/watermarking.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/watermarking.py)

Steps:

- convert waveform to `numpy`
- apply watermark
- convert back to `torch.Tensor`

Final output:

- `[1, T_wav]`

## Current Concurrency Breakpoints

### Baseline Runtime

Problem file:

- [external/chatterbox/src/chatterbox/mtl_tts.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/mtl_tts.py)

Break:

- `self.conds` is shared mutable request state

### T3 Inference

Problem file:

- [external/chatterbox/src/chatterbox/models/t3/t3.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/t3.py)

Break:

- request-local decode state is stored on the shared model object

### Alignment Analyzer

Problem file:

- [external/chatterbox/src/chatterbox/models/t3/inference/alignment_stream_analyzer.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/inference/alignment_stream_analyzer.py)

Break:

- installs forward hooks on shared transformer attention layers
- this is likely unsafe for concurrent requests even if the analyzer object itself is per request

### S3

Problem file:

- [external/chatterbox/src/chatterbox/models/s3gen/s3gen.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/s3gen/s3gen.py)

Break:

- current implementation assumes batch size `1`
- still a likely performance hot path after T3 correctness is fixed

## What To Preserve In A Concurrent Redesign

Keep shared:

- T3 weights
- S3 weights
- tokenizer
- voice encoder

Move to per-request state:

- `past_key_values`
- `generated_ids`
- alignment / repetition tracker state
- request prompt conditionals
- decode progress

Move to scheduler:

- request queue
- active request set
- batched step execution

## Trace Mode

There is now an opt-in trace mode for shape debugging.

Preferred way:

```bash
--trace-shapes
```

This is supported by:

- [external/chatterbox/compare_multilingual_runtime.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/compare_multilingual_runtime.py)
- [external/chatterbox/benchmark_multilingual_concurrency.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/benchmark_multilingual_concurrency.py)

Fallback for ad-hoc Python snippets:

```bash
export CHATTERBOX_TRACE_SHAPES=1
```

This prints stage-level tensor summaries for:

- baseline runtime
- streaming runtime worker
- T3 embedding/decode path
- S3 reference embed and inference path

The output lines include the source file name so pasted logs are easy to follow.

Use it only for debugging. It will add console noise and may slightly perturb timings.
