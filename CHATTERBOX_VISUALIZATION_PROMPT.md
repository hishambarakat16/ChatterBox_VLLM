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

- current scheduler is still same-shape cohort-to-completion
- it does not yet admit new requests dynamically mid-cohort

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

Use these exact scheduled numbers:

- `scheduled c1`
  - `wall_s=3.8411`
  - `audio_seconds_per_second=1.0309`
- `scheduled c2 traced`
  - `wall_s=4.2557`
  - `p95_latency_s=4.2538`
  - `audio_seconds_per_second=1.7764`
- `scheduled c4`
  - `wall_s=10.0345`
  - `audio_seconds_per_second=1.8018`

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

- `c1` throughput: about `+20.6%`
- `c1` wall time: about `27.3%` lower
- `c2` traced throughput: about `+57.8%`
- `c2` traced wall time: about `38.3%` lower
- `c2` traced `p95`: about `37.2%` lower
- `c4` throughput: about `+46.0%`
- `c4` wall time: about `21.4%` lower

## What The Updated Diagram Should Say

Add a new validated checkpoint section:

- `concurrent`: correctness restored
- `scheduled`: correctness plus meaningful throughput improvement

Add a new "current bottleneck" note:

- the shared-state corruption bug is no longer the main problem
- the next problems are:
  - dynamic scheduler admission
  - `S3` throughput / concurrency cost
  - peak `VRAM` measurement

Add a small warning/note box:

- `VRAM` appeared to increase somewhat with the scheduled path
- that has not been measured formally yet

Add a milestone box:

- immediate concurrency correctness milestone: done
- current serving milestone: first batched `T3` scheduler works
- next milestone: dynamic `T3` scheduler + explicit `VRAM` and `S3` measurement

## Output Preference

- one updated HTML file
- compact sections
- checkmarks for completed milestones
- one small comparison panel for `concurrent` vs `scheduled`
- preserve the existing current-vs-target narrative, but add the new scheduled checkpoint clearly
