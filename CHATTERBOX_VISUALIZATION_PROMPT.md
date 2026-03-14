# Chatterbox Visualization Update Prompt

Update the existing Chatterbox serving visualization so it reflects the new `scheduled` runtime findings.

Repo root:

- `/Users/hisham/Code/Bahraini_TTS`

Primary source files:

- [CONTEXT.md](/Users/hisham/Code/Bahraini_TTS/CONTEXT.md)
- [TRACE_RUN_RESULTS.md](/Users/hisham/Code/Bahraini_TTS/TRACE_RUN_RESULTS.md)
- [IMPLEMENTATION_CHECKLIST.md](/Users/hisham/Code/Bahraini_TTS/IMPLEMENTATION_CHECKLIST.md)
- [PROGRESS.md](/Users/hisham/Code/Bahraini_TTS/PROGRESS.md)
- [chatterbox_serving_shape_current_vs_target.html](/Users/hisham/Code/Bahraini_TTS/architecture/chatterbox_serving_shape_current_vs_target.html)

Target output:

- update the existing HTML
- do not create a second competing diagram unless absolutely necessary
- keep the style scientific, grayscale, compact, engineering-focused

## What Changed

The old story was:

- original `baseline` and `streaming` paths were not concurrency-safe
- first fix was the `concurrent` path:
  - request-local `T3` backend
  - request-local alignment analyzer
  - coarse full-decode `T3` lock
- that restored correctness but scaling stayed weak

The new story is:

- a new `scheduled` path exists
- it keeps one shared `T3` weight copy on GPU
- it keeps per-request mutable decode state separate
- it uses one scheduler per shared `T3` worker
- it batches multiple separate requests together for `T3`
- it improved throughput materially without retraining
- it was then hardened further to keep active cohorts and rotate them step-by-step

## Important Clarification To Visualize

Do not depict this as "one request with four internal lanes."

Depict it as:

- separate requests arrive
- compatible requests are grouped into one `T3` cohort
- the cohort runs batched `T3` prefill + decode steps
- each request still keeps separate:
  - KV cache
  - generated tokens
  - stop/alignment state
  - waveform output

Current limitation to show:

- the hardened scheduler now admits new work while older cohorts are still active
- but the current benchmark evidence is still strongest for same-time arrivals
- staggered-arrival validation is the next clean test

## Concrete Evidence To Include

Trace proof that the scheduler is real:

- `[runtime/t3_scheduler.py] run_cohort`
  - `requests 2`
  - `batch_key (36, 150)`
- `[models/t3/inference/scheduled_decode.py] prefill.batch`
  - `requests 2`
  - `inputs_embeds (4, 72, 1024)`

Interpretation:

- `2 requests x 2 CFG rows = 4`
- this proves two separate requests were actually batched together for `T3`

## Benchmark Results To Include

Use these latest scheduled numbers:

- `scheduled c1`
  - `wall_s=4.1369`
  - `audio_seconds_per_second=1.0346`
- `scheduled c2`
  - `wall_s=3.6349`
  - `p95_latency_s=3.6277`
  - `audio_seconds_per_second=1.8267`
- `scheduled c4`
  - `wall_s=5.8816`
  - `p95_latency_s=5.85`
  - `audio_seconds_per_second=2.7884`

Compare against coarse-lock `concurrent`:

- `concurrent c1`
  - `wall_s=5.2871`
  - `audio_seconds_per_second=0.8549`
- `concurrent c2 traced`
  - `wall_s=6.8933`
  - `p95_latency_s=6.7747`
  - `audio_seconds_per_second=1.1257`
- `concurrent c4`
  - `wall_s=12.7722`
  - `audio_seconds_per_second=1.2339`

Show these deltas explicitly:

- `c1` throughput vs coarse-lock concurrent: about `+21.0%`
- `c4` throughput vs coarse-lock concurrent: about `+126.0%`
- `c1 -> c2` on the hardened scheduler: about `+76.6%`
- `c2 -> c4` on the hardened scheduler: about `+52.6%`

Also include:

- `c2` is the first strong scaling step
- `c4` also adds real throughput in the latest timing-enabled run

## What The Updated Diagram Should Say

Add a new validated checkpoint section:

- `concurrent`: correctness restored
- `scheduled`: correctness plus meaningful throughput improvement

Add a new "current bottleneck" note:

- the shared-state corruption bug is no longer the main problem
- the next problems are:
  - deeper `T3` profiling
  - staggered-arrival / dynamic-admission validation
  - then `S3` throughput / concurrency cost

Add a small timing box:

- scheduler wait is tiny in the latest run:
  - `c2 T3 wait mean = 0.0106s`
  - `c4 T3 wait mean = 0.0127s`
- active `T3` is still larger than `S3`:
  - `c2 T3 total mean = 2.5362s`, `S3 mean = 0.9802s`
  - `c4 T3 total mean = 3.9262s`, `S3 mean = 1.3699s`
- interpretation:
  - the current remaining limit is not simple scheduler queueing
  - active `T3` compute is still the larger measured bottleneck

Add a small warning/note box:

- `VRAM` now has measured numbers:
  - `c1 peak allocated = 3514.1 MB`
  - `c2 peak allocated = 3917.5 MB`
  - `c4 peak allocated = 4735.6 MB`
- a live `nvidia-smi` snapshot also showed about `75%` utilization and about `107W` power draw

Add a milestone box:

- immediate concurrency correctness milestone: done
- current serving milestone: hardened batched `T3` scheduler works
- next milestone: staggered-arrival validation + deeper `T3` profiling

## Output Preference

- one updated HTML file
- compact sections
- checkmarks for completed milestones
- one small comparison panel for `concurrent` vs `scheduled`
- preserve the existing current-vs-target narrative, but add the new scheduled checkpoint clearly
