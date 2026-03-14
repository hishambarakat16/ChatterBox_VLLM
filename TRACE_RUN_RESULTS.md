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
- The next target was:
  - one shared model instance
  - `2` simultaneous requests
  - both outputs correct

## Concurrent Runtime Benchmark

Tested implementation:

- `benchmark_multilingual_concurrency.py --impl concurrent --concurrency-levels 1 2 --trace-shapes --output-dir benchmark_wavs`

Runtime shape:

- shared model weights
- coarse full-decode `T3` lock
- request-local `T3` backend and alignment analyzer
- `S3` still unchanged

### Concurrency = 1

Result:

- `load_s=22.2746`
- `wall_s=4.9795`
- `request_latencies_s=[4.9688]`
- `num_samples=[116160]`
- `audio_seconds_per_second=0.972`
- `errors=[]`

Trace highlights:

- `text_tokens`: `(2, 36)`
- `T3.embeds`: `(2, 71, 1024)`
- `T3.predicted_tokens`: `(1, 122)`
- filtered speech tokens: `(121,)`
- `S3.output_mels`: `(1, 80, 242)`
- `S3.output_wavs`: `(1, 116160)`

### Concurrency = 2

Result:

- `wall_s=6.8933`
- `request_latencies_s=[4.5455, 6.892]`
- `mean_latency_s=5.7187`
- `p95_latency_s=6.7747`
- `num_samples=[107520, 78720]`
- `audio_seconds_total=7.76`
- `audio_seconds_per_second=1.1257`
- `errors=[]`

Saved audio:

- `benchmark_wavs/concurrent_c2_r0.wav`
- `benchmark_wavs/concurrent_c2_r1.wav`

Human listening result:

- both saved concurrent outputs sounded fine
- no obvious corruption
- no collapsed short output

### What This Means

- The first-pass `T3` concurrency fix worked for the immediate milestone.
- `2` simultaneous requests now complete correctly on one shared model instance.
- The main fix was correctness, not efficiency:
  - request-local `T3` decode state
  - request-local alignment analyzer
  - coarse `T3` decode lock
- `S3` did not immediately break at `concurrency=2`.
- The remaining issue is now throughput and scheduling efficiency, not the original shared-state corruption bug.

## Higher-Concurrency Benchmark

Command shape:

- `benchmark_multilingual_concurrency.py --impl concurrent --concurrency-levels 1 4 --output-dir benchmark_wavs`

Important note:

- at this point `--trace-shapes` is only needed for debugging regressions
- it is no longer needed for normal benchmark runs

### Concurrency = 1

Result:

- `load_s=22.2732`
- `wall_s=5.2871`
- `request_latencies_s=[5.2846]`
- `num_samples=[108480]`
- `audio_seconds_total=4.52`
- `audio_seconds_per_second=0.8549`
- `errors=[]`

### Concurrency = 4

Result:

- `wall_s=12.7722`
- `request_latencies_s=[12.7467, 9.943, 3.3763, 6.479]`
- `mean_latency_s=8.1362`
- `p95_latency_s=12.3262`
- `num_samples=[95040, 104640, 80640, 97920]`
- `audio_seconds_total=15.76`
- `audio_seconds_per_second=1.2339`
- `errors=[]`

Saved audio:

- `benchmark_wavs/concurrent_c4_r0.wav`
- `benchmark_wavs/concurrent_c4_r1.wav`
- `benchmark_wavs/concurrent_c4_r2.wav`
- `benchmark_wavs/concurrent_c4_r3.wav`

### What This Means

- The `concurrent` runtime remains correct at `concurrency=4`.
- This is strong evidence that the original shared-state corruption bug was the right first target.
- But the system is still not scaling well:
  - `c1 audio_seconds_per_second = 0.8549`
  - `c4 audio_seconds_per_second = 1.2339`
- That is only about `1.44x` throughput improvement for `4x` concurrency.
- The coarse full-decode `T3` lock is now the main limiter.
- Because `T3` is serialized this way, we still do not have a clean answer to:
  - how well `S3` itself scales under a truly concurrent `T3` scheduler
- Updated interpretation:
  - correctness is restored
  - real scalability is not
  - the next architecture target is a `T3` scheduler or more granular `T3` stepping model
