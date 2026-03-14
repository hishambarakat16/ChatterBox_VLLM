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
- These traces established that the single-request shape flow was healthy before concurrency work continued.

## Current Interpretation

- Baseline and streaming wrappers both work for single request.
- The wrapper did not break the end-to-end tensor flow.
- At that point, the next target was:
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

## Scheduled Runtime Benchmark

Tested implementation:

- `benchmark_multilingual_concurrency.py --impl scheduled`

Runtime shape:

- one shared `T3` weight copy on GPU
- one scheduler per shared `T3` worker
- one per-request mutable decode state object per active request
- batch-compatible `T3` prefill and batched `T3` decode steps
- `S3` still unchanged

Important semantic note:

- this batches multiple separate requests together for `T3`
- it is not "one request has four internal lanes"
- each request still has its own:
  - KV cache
  - generated token history
  - stop/alignment state
  - output waveform

### Non-Trace Benchmark

Command shape:

- `benchmark_multilingual_concurrency.py --impl scheduled --concurrency-levels 1 4 --output-dir benchmark_wavs`

#### Concurrency = 1

Result:

- `load_s=21.7485`
- `wall_s=3.8411`
- `request_latencies_s=[3.8402]`
- `num_samples=[95040]`
- `audio_seconds_total=3.96`
- `audio_seconds_per_second=1.0309`
- `saved_wavs=['benchmark_wavs/scheduled_c1_r0.wav']`
- `errors=[]`

#### Concurrency = 4

Result:

- `wall_s=10.0345`
- `request_latencies_s=[5.8106, 9.9176, 5.8108, 9.9207]`
- `mean_latency_s=7.8649`
- `p95_latency_s=9.9202`
- `num_samples=[108480, 106560, 115200, 103680]`
- `audio_seconds_total=18.08`
- `audio_seconds_per_second=1.8018`
- `saved_wavs=['benchmark_wavs/scheduled_c4_r0.wav', 'benchmark_wavs/scheduled_c4_r1.wav', 'benchmark_wavs/scheduled_c4_r2.wav', 'benchmark_wavs/scheduled_c4_r3.wav']`
- `errors=[]`

### Trace Benchmark

Command shape:

- `benchmark_multilingual_concurrency.py --impl scheduled --concurrency-levels 1 2 --trace-shapes --output-dir benchmark_wavs`

#### Concurrency = 1

Result:

- `load_s=23.9379`
- `wall_s=4.3153`
- `request_latencies_s=[4.3145]`
- `num_samples=[114240]`
- `audio_seconds_total=4.76`
- `audio_seconds_per_second=1.1031`
- `saved_wavs=['benchmark_wavs/scheduled_c1_r0.wav']`
- `errors=[]`

#### Concurrency = 2

Result:

- `wall_s=4.2557`
- `request_latencies_s=[4.239, 4.2546]`
- `mean_latency_s=4.2468`
- `p95_latency_s=4.2538`
- `num_samples=[102720, 78720]`
- `audio_seconds_total=7.56`
- `audio_seconds_per_second=1.7764`
- `saved_wavs=['benchmark_wavs/scheduled_c2_r0.wav', 'benchmark_wavs/scheduled_c2_r1.wav']`
- `errors=[]`

Trace highlights:

- `[runtime/t3_scheduler.py] run_cohort`
  - `requests 2`
  - `batch_key (36, 150)`
- `[models/t3/inference/scheduled_decode.py] prefill.batch`
  - `requests 2`
  - `inputs_embeds (4, 72, 1024)`

Interpretation:

- the scheduler grouped two separate requests into one `T3` cohort
- `inputs_embeds (4, 72, 1024)` is exactly:
  - `2 requests x 2 CFG rows = 4`
- the two requests still produced different outputs:
  - `predicted_tokens (1, 108)` for one request
  - `predicted_tokens (1, 83)` for the other
- so the requests are batched together for `T3`, but their mutable decode state remains separate

### Scheduled vs Coarse-Lock Concurrent

Using the previously validated `concurrent` path as the comparison point:

- `c1` throughput improved from `0.8549` to `1.0309`
  - about `+20.6%`
- `c1` wall time improved from `5.2871s` to `3.8411s`
  - about `27.3%` lower
- `c2` traced throughput improved from `1.1257` to `1.7764`
  - about `+57.8%`
- `c2` traced wall time improved from `6.8933s` to `4.2557s`
  - about `38.3%` lower
- `c2` traced `p95` latency improved from `6.7747s` to `4.2538s`
  - about `37.2%` lower
- `c4` throughput improved from `1.2339` to `1.8018`
  - about `+46.0%`
- `c4` wall time improved from `12.7722s` to `10.0345s`
  - about `21.4%` lower

### What This Means

- The `scheduled` runtime is the first path that improves both correctness and scaling.
- The scheduler is doing real batched `T3` work, not just renaming the old full-decode lock.
- This is still an inference/serving change, not a retraining change.
- The current scheduler is still limited:
  - it batches a same-shape cohort to completion
  - it does not yet admit new requests dynamically mid-cohort
- That means the design is better, but not yet a full production scheduler.
- `S3` now becomes a more plausible next bottleneck because `T3` is no longer fully serialized.
- VRAM likely increased somewhat because each active request keeps its own mutable decode state and cache.
- VRAM increase was observed qualitatively during testing, but has not been measured formally yet.

## Timing-Enabled Scheduled Runtime Benchmark

This is the latest authoritative scheduled run after adding per-stage timing output.

Command shape:

- `benchmark_multilingual_concurrency.py --impl scheduled --concurrency-levels 1 2 4 --output-dir benchmark_wavs`

Snapshot during run:

- `nvidia-smi` showed about `75%` GPU utilization
- power draw reached about `107W`
- memory snapshot was about `4786 MiB`

Important caution:

- that `nvidia-smi` line is a point-in-time snapshot, not a full utilization trace
- it is still useful evidence that the hardened scheduler is driving the GPU harder than before

### Concurrency = 1

Result:

- `load_s=20.5869`
- `wall_s=4.1369`
- `request_latencies_s=[4.1362]`
- `mean_latency_s=4.1362`
- `p95_latency_s=4.1362`
- `num_samples=[102720]`
- `audio_seconds_total=4.28`
- `audio_seconds_per_second=1.0346`
- `vram_allocated_start_mb=3074.8`
- `vram_reserved_start_mb=3094.0`
- `vram_allocated_end_mb=3302.7`
- `vram_reserved_end_mb=3708.0`
- `vram_peak_allocated_mb=3514.1`
- `vram_peak_reserved_mb=3708.0`
- `vram_peak_allocated_delta_mb=439.3`
- `vram_peak_reserved_delta_mb=614.0`
- `stage_s3_s_mean=0.6424`
- `stage_t3_active_s_mean=3.304`
- `stage_t3_s_mean=3.4081`
- `stage_t3_wait_s_mean=0.1041`
- `stage_text_prep_s_mean=0.0027`
- `stage_watermark_s_mean=0.0685`
- `saved_wavs=['benchmark_wavs/scheduled_c1_r0.wav']`
- `errors=[]`

### Concurrency = 2

Result:

- `wall_s=3.6349`
- `request_latencies_s=[3.6324, 3.5381]`
- `mean_latency_s=3.5852`
- `p95_latency_s=3.6277`
- `num_samples=[81600, 77760]`
- `audio_seconds_total=6.64`
- `audio_seconds_per_second=1.8267`
- `vram_allocated_start_mb=3139.5`
- `vram_reserved_start_mb=3708.0`
- `vram_allocated_end_mb=3474.1`
- `vram_reserved_end_mb=4028.0`
- `vram_peak_allocated_mb=3917.5`
- `vram_peak_reserved_mb=4028.0`
- `vram_peak_allocated_delta_mb=778.0`
- `vram_peak_reserved_delta_mb=320.0`
- `stage_s3_s_mean=0.9802`
- `stage_t3_active_s_mean=2.5256`
- `stage_t3_s_mean=2.5362`
- `stage_t3_wait_s_mean=0.0106`
- `stage_text_prep_s_mean=0.0027`
- `stage_watermark_s_mean=0.061`
- `saved_wavs=['benchmark_wavs/scheduled_c2_r0.wav', 'benchmark_wavs/scheduled_c2_r1.wav']`
- `errors=[]`

### Concurrency = 4

Result:

- `wall_s=5.8816`
- `request_latencies_s=[5.2273, 4.637, 5.739, 5.8696]`
- `mean_latency_s=5.3682`
- `p95_latency_s=5.85`
- `num_samples=[96000, 90240, 102720, 104640]`
- `audio_seconds_total=16.4`
- `audio_seconds_per_second=2.7884`
- `vram_allocated_start_mb=3147.6`
- `vram_reserved_start_mb=4028.0`
- `vram_allocated_end_mb=3815.0`
- `vram_reserved_end_mb=5040.0`
- `vram_peak_allocated_mb=4735.6`
- `vram_peak_reserved_mb=5040.0`
- `vram_peak_allocated_delta_mb=1588.0`
- `vram_peak_reserved_delta_mb=1012.0`
- `stage_s3_s_mean=1.3699`
- `stage_t3_active_s_mean=3.9136`
- `stage_t3_s_mean=3.9262`
- `stage_t3_wait_s_mean=0.0127`
- `stage_text_prep_s_mean=0.0063`
- `stage_watermark_s_mean=0.0629`
- `saved_wavs=['benchmark_wavs/scheduled_c4_r0.wav', 'benchmark_wavs/scheduled_c4_r1.wav', 'benchmark_wavs/scheduled_c4_r2.wav', 'benchmark_wavs/scheduled_c4_r3.wav']`
- `errors=[]`

### Updated Interpretation

- correctness still holds at `1`, `2`, and `4`
- the scheduler hardening plus timing work gives a clearer read than before
- GPU usage is clearly higher than before, though the `nvidia-smi` evidence is still just a snapshot
- VRAM growth with concurrency is now measured instead of guessed
- peak allocated VRAM stayed well below the `16 GB` limit on this card

Most important throughput result:

- `c1`: `1.0346 audio_seconds_per_second`
- `c2`: `1.8267 audio_seconds_per_second`
- `c4`: `2.7884 audio_seconds_per_second`

That means:

- `c1 -> c2` gained about `+76.6%` throughput
- `c2 -> c4` gained about `+52.6%` throughput

Relative to the older coarse-lock `concurrent` path:

- `c1` throughput improved from `0.8549` to `1.0346`
  - about `+21.0%`
- `c4` throughput improved from `1.2339` to `2.7884`
  - about `+126.0%`
- `c4` wall time improved from `12.7722s` to `5.8816s`
  - about `53.9%` lower

Most important stage-timing result:

- `T3` wait time is tiny:
  - `c2 mean = 0.0106s`
  - `c4 mean = 0.0127s`
- active `T3` compute is still larger than `S3`:
  - `c2 T3 total mean = 2.5362s`, `S3 mean = 0.9802s`
  - `c4 T3 total mean = 3.9262s`, `S3 mean = 1.3699s`

Current read:

- the remaining limit is not simple scheduler queueing under simultaneous arrivals
- active `T3` compute is still the larger measured bottleneck
- `S3` remains a real cost, but it is not the first measured limiter in this latest run
- staggered-arrival validation is still useful, but it is no longer blocking the main interpretation of this benchmark

## Latency-KPI Extension With Concurrency = 8

This run extended the scheduled benchmark to include:

- `concurrency=8`
- `stage_t3_first_token_s`
- `stage_audio_ready_s`

Command shape:

- `benchmark_multilingual_concurrency.py --impl scheduled --concurrency-levels 1 2 4 8 --output-dir benchmark_wavs`

### Key Results

- throughput:
  - `c1 = 1.0369`
  - `c2 = 1.767`
  - `c4 = 2.8324`
  - `c8 = 3.2907`
- peak allocated VRAM:
  - `c1 = 3514.9 MB`
  - `c2 = 3951.3 MB`
  - `c4 = 4713.0 MB`
  - `c8 = 6272.6 MB`
- `T3` first token mean:
  - `c1 = 195.6 ms`
  - `c2 = 56.5 ms`
  - `c4 = 105.0 ms`
  - `c8 = 368.0 ms`
- audio ready mean:
  - `c1 = 4.1994s`
  - `c2 = 4.5553s`
  - `c4 = 5.2462s`
  - `c8 = 8.6152s`

### Concurrency = 8

Result:

- `wall_s=10.8185`
- `request_latencies_s=[9.3455, 10.815, 4.8036, 6.6242, 7.7711, 10.0224, 10.1109, 10.0148]`
- `mean_latency_s=8.6884`
- `p95_latency_s=10.5686`
- `audio_seconds_per_second=3.2907`
- `vram_peak_allocated_mb=6272.6`
- `vram_peak_reserved_mb=6360.0`
- `stage_audio_ready_s_mean=8.6152`
- `stage_s3_s_mean=2.2454`
- `stage_t3_active_s_mean=6.3296`
- `stage_t3_first_token_s_mean=0.368`
- `stage_t3_s_mean=6.3571`
- `stage_t3_wait_s_mean=0.0276`
- `saved_wavs`: `8` files
- `errors=[]`

### Updated Interpretation

- `c8` still improves throughput over `c4`, but only modestly:
  - about `+16.2%`
- the latency cost is much steeper:
  - `p95` rises from `5.85s` to `10.5686s`
  - `T3` first token rises from `105.0 ms` to `368.0 ms`
- scheduler wait is still tiny at `c8`
- so the new limiting behavior is still active compute, not queueing

Most important latency read:

- `T3` first-token latency is already fairly good at `c2`
- it is still near target at `c4`
- but audio is only ready seconds later because the current path still waits for full downstream decode

Current practical operating-point read:

- `c2` is the best latency-first operating point
- `c4` is the best throughput-first operating point
- `c8` is not a good latency-sensitive operating point

## Alignment Guardrail Experiments

These were temporary scheduled-path experiments to answer one specific question:

- can the attention-based `T3` alignment guard be weakened or removed without hurting output quality?

Practical result:

- no, not safely with the tested variants

Most important observations from the sweep and follow-up listening:

- `alignment off` caused long rambling clips, trailing silence/noise, and garbled late speech
- `inspect every 2` also produced bad clips
- disabling the `long_tail` force-EOS rule was clearly bad on the tested prompt
- removing the guard can make raw throughput look better while actually making output quality and total request latency worse, because runaway decode continues for much longer

Current conclusion:

- the attention-based alignment guard is not optional in the current runtime
- the safe current assumption is:
  - analyzer on
  - inspect every decode step
  - keep the existing EOS guard policies enabled

Repo note:

- the temporary alignment sweep controls and helper script were removed after these experiments
- the project is back on the simpler validated scheduled runtime path, while keeping the lesson from the sweep recorded here

## GPU-Local Scheduled Alignment State Rewrite

This was the next scheduled-path optimization after the alignment sweep conclusion.

Goal:

- keep the same guard behavior
- remove the obvious scheduled-path implementation waste

Code change summary:

- removed the scheduled hook's per-step `.cpu()` attention copy
- removed the growing CPU-side full alignment matrix
- replaced the scheduled request state with rolling GPU-local summaries:
  - recent alignment rows
  - early-text activation max
  - post-completion tail mass
  - post-completion repetition mass

Important constraint:

- this change did **not** remove the deeper `output_attentions=True` cost
- it only removed the CPU-copy and full-history-growth part of the scheduled guard overhead

Latest benchmark result:

- `errors=[]` through `concurrency=8`
- manual listening stayed clean

Most useful directional comparison was at `c8` against the last clean pre-change run:

- `wall_s`: `11.0954 -> 9.5139`
- `audio_seconds_per_second`: `3.1941 -> 3.4518`
- `stage_t3_s_mean`: `6.9425 -> 5.6515`
- `stage_t3_first_token_s_mean`: `0.2016 -> 0.1561`

Current interpretation:

- the scheduled analyzer was paying a real CPU-side overhead
- the GPU-local rewrite removed a meaningful part of that overhead
- output quality still looked healthy on manual listening
- the next likely remaining guard-path cost is still the attention fallback caused by `output_attentions=True`

## Isolated T3 `output_attentions` Microbenchmark

This was added to separate one question from the rest of the runtime:

- how much does `output_attentions=True` cost by itself on the same `T3` decode shapes?

Command shape:

- `benchmark_t3_output_attentions.py --concurrency 8 --decode-steps 64 --warmup-runs 1 --runs 5`

Important note:

- this benchmark isolates the `T3` backend forward path
- it does **not** include the full scheduled analyzer hook logic
- it is meant to measure the flag-level tax, not the whole guard implementation

Result:

- `prefill_overhead_pct = 1.16%`
- `decode_overhead_pct = 14.83%`
- `decode_per_step_overhead_pct = 14.83%`
- `total_t3_overhead_pct = 13.71%`

Interpretation:

- `output_attentions=True` is a real decode-time cost
- the cost is concentrated in token-by-token decode, not in prefill
- but this is still only part of the remaining utilization problem
- updated read:
  - returned attention maps matter
  - but the deeper structural limit is still the shape of autoregressive decode itself:
    - tiny per-step query length
    - CFG doubling the effective rows
    - many small decode steps instead of one large GPU-friendly workload
