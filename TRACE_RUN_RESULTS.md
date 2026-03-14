# Trace Run Results

_Last updated: 2026-03-14_

## Purpose

This file stores concrete traced runs from the cloud GPU so the main project docs do not need to repeat long terminal output.

Current trusted environment:

- GPU: `RTX 4060 Ti`
- PyTorch: stock `2.6.0+cu124`
- Perth: installed from source, not PyPI

## Single-Request Trace Runs

Prompt file:

- `SPK_17_000003.wav`

Text:

- `مرحبا، هذا اختبار للبنية الحالية.`

### Baseline

Command shape:

- `compare_multilingual_runtime.py --impl baseline --runs 1 --trace-shapes --output-wav baseline_trace.wav`

Result:

- `load_s=21.0098`
- `latency_s=[4.3412]`
- `num_samples=81600`

Observed traced shapes:

- `embed_ref.prompt_token`: `(1, 150)`
- `embed_ref.prompt_feat`: `(1, 300, 80)`
- `embed_ref.embedding`: `(1, 192)`
- `prepare_conditionals.speaker_emb`: `(1, 256)`
- `generate.text_tokens`: `(2, 36)`
- `T3.cond_emb`: `(2, 34, 1024)`
- `T3.text_emb`: `(2, 36, 1024)`
- `T3.speech_emb`: `(2, 1, 1024)`
- `T3.embeds`: `(2, 71, 1024)`
- `T3.predicted_tokens`: `(1, 86)`
- filtered speech tokens: `(85,)`
- `S3.output_mels`: `(1, 80, 170)`
- `S3.output_wavs`: `(1, 81600)`

Termination note:

- single-request baseline hit `forcing EOS` due to token repetition detection
- output still sounded acceptable to HM
- this confirms `forcing EOS` is not automatically a hard failure

### Streaming Runtime

Command shape:

- `compare_multilingual_runtime.py --impl streaming --runs 1 --trace-shapes --output-wav streaming_trace.wav`

Result:

- `load_s=21.1393`
- `latency_s=[4.46]`
- `num_samples=100800`

Observed traced shapes:

- `embed_ref.prompt_token`: `(1, 150)`
- `embed_ref.prompt_feat`: `(1, 300, 80)`
- `embed_ref.embedding`: `(1, 192)`
- `build_conditionals_from_wav.speaker_emb`: `(1, 256)`
- `generate.text_tokens`: `(2, 36)`
- `T3.cond_emb`: `(2, 34, 1024)`
- `T3.text_emb`: `(2, 36, 1024)`
- `T3.speech_emb`: `(2, 1, 1024)`
- `T3.embeds`: `(2, 71, 1024)`
- `T3.predicted_tokens`: `(1, 106)`
- filtered speech tokens: `(105,)`
- `S3.output_mels`: `(1, 80, 210)`
- `S3.output_wavs`: `(1, 100800)`

Termination note:

- single-request streaming hit `forcing EOS` with `long_tail=True`
- output still completed normally

## What We Learned

- The single-request flow is structurally healthy in both baseline and streaming wrappers.
- The traced tensor shapes match the current mental model in [CHATTERBOX_STATE_FLOW.md](/Users/hisham/Code/Bahraini_TTS/CHATTERBOX_STATE_FLOW.md).
- `CFG` duplication is visible at the text-token stage: `(1, T)` becomes `(2, T)`.
- For this prompt/text pair, `T3` conditioning length is concretely `34`.
- For this prompt/text pair, `text_tokens` length after start/stop padding is concretely `36`.
- `T3` total initial embed length is `71 = 34 + 36 + 1`.
- `S3` still obeys `token_mel_ratio = 2` in practice:
  - `85 -> 170`
  - `105 -> 210`
- `forcing EOS` appears in healthy single-request runs, so it should be treated as a warning signal, not as failure by itself.
- The main remaining problem is still concurrency correctness, not single-request shape flow.

## Current Interpretation

- Baseline and streaming wrappers both work for single request.
- The wrapper did not break the end-to-end tensor flow.
- The next target remains:
  - one shared model instance
  - `2` simultaneous requests
  - both outputs correct
