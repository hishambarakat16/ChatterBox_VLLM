# S3 Shape Contract

_Last updated: 2026-03-19_

This file is the `S3` equivalent of `architecture/t3_shape_contract.md`.

The goal is to pin down the current input/output tensor contract for the `S3` path, the runtime boundaries around it, and the measured concurrency behavior so later debugging is about concrete shapes and costs instead of guesswork.

## Current Focus

We are tracing only the `S3` side for now.

That means:

- keep `T3` shape traces off
- keep the scheduled/Hydra runtime path active
- log the reference-conditioning tensors entering `S3`
- log the token-to-mel contract
- log the HiFT vocoder input/output contract
- keep the end-to-end benchmark summary so `stage_s3_s` can still be compared against `stage_t3_s`

## Canonical Trace Command

```bash
unset CHATTERBOX_TRACE_SHAPES
PYTHONPATH=external/chatterbox/src python external/chatterbox/benchmark_multilingual_concurrency.py \
  --impl scheduled \
  --device cuda \
  --language-id ar \
  --audio-prompt-path "$PROMPT_AUDIO" \
  --text "مرحبا، هذا اختبار للبنية الحالية." \
  --hydra-checkpoint-dir runs/t3_hydra_ar_short_40k_h2_run1/checkpoint_step_022910 \
  --hydra-speculate-k 3 \
  --temperature 0 \
  --max-new-tokens 128 \
  --concurrency-levels 1 2 4 8 \
  --trace-s3-shapes
```

## Logged S3 Stages

From the current runtime/code path, the selective `S3` trace now covers:

1. Reference embedding build
- `[runtime/worker.py] build_conditionals_from_wav`
- `speaker_emb`
- `cond_prompt_speech_tokens` when present
- `s3_ref.prompt_token`
- `s3_ref.prompt_feat`
- `s3_ref.embedding`

2. `S3` reference dictionary inside `S3Token2Mel`
- `[models/s3gen/s3gen.py] embed_ref`
- `prompt_token`
- `prompt_token_len`
- `prompt_feat`
- `prompt_feat_len` when present
- `embedding`

3. Token-to-mel input contract
- `[models/s3gen/s3gen.py] token2mel.input`
- `speech_tokens`
- `speech_token_lens`
- `finalize`
- `n_cfm_timesteps`
- `ref.prompt_token`
- `ref.prompt_feat`
- `ref.embedding`

4. Token-to-mel output contract
- `[models/s3gen/s3gen.py] token2mel.output`
- `output_mels`

5. HiFT vocoder input/output contract
- `[models/s3gen/s3gen.py] hift.input`
- `speech_feat`
- `cache_source`
- `[models/s3gen/s3gen.py] hift.output`
- `output_wavs`
- `output_sources` when returned

6. Final `S3` inference output
- `[models/s3gen/s3gen.py] inference.output`
- `output_mels`
- `output_wavs`

## Measured Shape Contract

Observed on the current scheduled+Hydra path:

| Stage | Tensor | Shape | Dtype | Device | Meaning |
|---|---|---|---|---|---|
| token2mel input | `speech_tokens` | `(1, 85)` | `torch.int64` | `cuda:0` | filtered `T3` speech tokens handed into `S3` |
| token2mel input | `speech_token_lens` | `(1,)` | `torch.int64` | `cuda:0` | one length value for batch size `1` |
| token2mel input | `ref.prompt_token` | `(1, 157)` | `torch.float32` | `cuda:0` | prompt-token conditioning |
| token2mel input | `ref.prompt_feat` | `(1, 314, 80)` | `torch.float32` | `cuda:0` | prompt mel conditioning |
| token2mel input | `ref.embedding` | `(1, 192)` | `torch.float32` | `cuda:0` | speaker/reference embedding |
| token2mel output | `output_mels` | `(1, 80, 170)` | `torch.float32` | `cuda:0` | token-to-mel output |
| HiFT input | `speech_feat` | `(1, 80, 170)` | `torch.float32` | `cuda:0` | mel input to vocoder |
| HiFT input | `cache_source` | `(1, 1, 0)` | `torch.float32` | `cuda:0` | empty cache in the current sync path |
| HiFT output | `output_wavs` | `(1, 81600)` | `torch.float32` | `cuda:0` | final waveform |
| HiFT output | `output_sources` | `(1, 1, 81600)` | `torch.float32` | `cuda:0` | vocoder source output |
| inference output | `output_mels` | `(1, 80, 170)` | `torch.float32` | `cuda:0` | returned mel output |
| inference output | `output_wavs` | `(1, 81600)` | `torch.float32` | `cuda:0` | returned waveform |

### Derived Ratios

- `85` speech tokens -> `170` mel frames
- current token-to-mel expansion is `2x`
- `170` mel frames -> `81600` waveform samples
- `81600` samples at `24 kHz` = `3.4s` of audio

So the current sync `S3` contract is:

```text
speech_tokens (1, 85)
  -> token2mel
  -> output_mels (1, 80, 170)
  -> HiFT vocoder
  -> output_wavs (1, 81600)
```

## Runtime Boundaries

The benchmark now exposes both the coarse `S3` stage and the internal request-time `S3` substages:

- `stage_s3_s`
  - total time spent in the `S3` stack for a request
- `stage_s3_ref_prepare_s`
  - per-request reference dictionary preparation and dtype/device casting
- `stage_s3_token2mel_s`
  - token-to-mel generation time
- `stage_s3_hift_s`
  - HiFT vocoder time
- `stage_s3_trim_s`
  - waveform trim/fade time
- `stage_s3_inference_internal_s`
  - internal `S3` inference path total

Session-time prompt conditioning also has dedicated keys, but those are not part of request latency in this benchmark:

- `stage_session_conditioning_s`
- `stage_s3_ref_mel_s`
- `stage_s3_ref_speaker_s`
- `stage_s3_ref_tokenize_s`
- `stage_s3_ref_align_s`
- `stage_s3_ref_embed_s`

## Measured Performance

Current scheduled+Hydra `S3` timings on the latest traced run:

| Concurrency | `stage_s3_s_mean` | `stage_audio_ready_s_mean` | Throughput (`audio_seconds_per_second`) | Read |
|---|---:|---:|---:|---|
| `c1` | `4.7602s` | `9.3834s` | `0.3494` | cold single-request baseline on this run |
| `c2` | `2.1098s` | `4.9376s` | `1.3356` | best per-request `S3` efficiency in this run |
| `c4` | `3.3746s` | `9.4711s` | `1.4042` | `S3` starts degrading materially |
| `c8` | `6.8995s` | `14.0846s` | `1.8687` | `S3` is the dominant downstream bottleneck |

### Relative Increase

Using `c2` as the clean baseline:

| Metric | `c2` | `c4` | `c8` | `c2 -> c4` | `c2 -> c8` |
|---|---:|---:|---:|---:|---:|
| `stage_s3_s_mean` | `2.1098s` | `3.3746s` | `6.8995s` | `+59.9%` | `+227.0%` |
| `stage_audio_ready_s_mean` | `4.9376s` | `9.4711s` | `14.0846s` | `+91.8%` | `+185.3%` |

## Internal S3 Breakdown

Per-request `S3` substages on the same run:

| Stage | `c1` mean (s) | `c2` mean (s) | `c4` mean (s) | `c8` mean (s) | `c2 -> c4` | `c2 -> c8` | Read |
|---|---:|---:|---:|---:|---:|---:|---|
| `s3_ref_prepare_s` | `0.0004` | `0.0009` | `0.0008` | `0.0018` | `-11.1%` | `+100.0%` | negligible |
| `s3_token2mel_s` | `3.5140` | `1.8980` | `3.1110` | `6.5268` | `+63.9%` | `+243.9%` | main `S3` bottleneck |
| `s3_hift_s` | `1.2437` | `0.2093` | `0.2581` | `0.3661` | `+23.3%` | `+74.9%` | secondary bottleneck |
| `s3_trim_s` | `0.0001` | `0.0001` | `0.0003` | `0.0003` | about flat | about flat | irrelevant |
| `s3_inference_internal_s` | `4.7600` | `2.1097` | `3.3745` | `6.8993` | `+59.9%` | `+227.0%` | total internal `S3` time |
| `s3_s` | `4.7602` | `2.1098` | `3.3746` | `6.8995` | `+59.9%` | `+227.0%` | total measured `S3` time |

## Contribution Split

How much each request-time component contributes to total `S3` time:

| Concurrency | `token2mel` share of `s3_s` | `HiFT` share of `s3_s` | Read |
|---|---:|---:|---|
| `c1` | `73.8%` | `26.3%` | token-to-mel dominates |
| `c2` | `89.9%` | `9.9%` | token-to-mel overwhelmingly dominates |
| `c4` | `92.2%` | `7.6%` | almost entirely token-to-mel |
| `c8` | `94.6%` | `5.3%` | bottleneck is clearly token-to-mel |

### What This Suggests

- `S3` scales well enough from `c1 -> c2`
- `S3` degrades materially by `c4`
- `S3` is the dominant downstream bottleneck by `c8`
- the bottleneck is now clearly inside `token2mel`, not inside `HiFT`
- the repeated per-request `token2mel.input` traces still suggest `S3` is effectively running per request, not cohort-batched like scheduled `T3`
- the session-time reference conditioning keys are `0.0` in this benchmark because session creation happens before timed request generation

## Current Structural Expectations

These are the current expectations from the code and measured trace:

- `speech_tokens` enters `S3` as one logical row
- `speech_token_lens` should be one length value for batch size `1`
- reference prompt tokens and prompt mels are paired conditioning inputs
- `output_mels` is expected to be shaped like:
  - `(B=1, mel_bins=80, mel_frames)`
- final waveform output is expected to be shaped like:
  - `(B=1, num_samples)`

## Why This Matters

The current runtime read is:

- Hydra compute itself scales reasonably
- scheduler/orchestration overhead shows up in `t3_wait_s` at high concurrency
- `S3` becomes the larger downstream bottleneck by `c8`

So the next debugging loop is:

1. confirm the exact `S3` tensor contract end to end
2. identify whether the scaling problem is mostly token-to-mel or HiFT
3. only then decide whether the next step is runtime scheduling, model-side `S3` changes, or both

## State Ownership

This section is the `S3` equivalent of the state-ownership reasoning we already had to do for `T3`.

### Current Scheduled Runtime Path

In the current `scheduled` runtime, `S3` is used through one shared module instance:

- [mtl_tts_scheduled.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/mtl_tts_scheduled.py)
- shared worker field:
  - `worker.s3gen`

But the important difference from the old `T3` bug is:

- we do **not** currently see `S3` rebuilding or overwriting shared runtime decode objects on the model instance per request
- there is no `S3` analogue here of:
  - `self.compiled`
  - `self.patched_model`
  - alignment-controller state
  - request-local decode analyzer state stored back onto the shared model

### Shared Immutable / Mostly-Immutable State

These are shared across requests and are expected to remain stable during inference:

- model weights in:
  - `self.flow`
  - `self.mel2wav`
  - `self.speaker_encoder`
  - `self.tokenizer`
- registered buffers such as:
  - `trim_fade`
  - HiFT / STFT buffers inside the vocoder stack
- the cached resampler factory:
  - `get_resampler(...)`
  - this is a global cached utility, not request decode state

These are shared, but they are not currently being re-authored per request in the way `T3` was.

### Request-Local / Per-Call State

These are created fresh per request or per call in the current sync `S3` path:

- `active_conds.gen`
  - the reference dictionary handed from the worker to `S3`
- `speech_tokens`
- `speech_token_lens`
- `ref_dict` inside `S3.forward(...)`
- `output_mels`
- `output_wavs`
- local temporary caches:
  - `hift_cache_source = torch.zeros(1, 1, 0)` in the sync forward path
  - `cache_source` in `hift_inference(...)` when not externally supplied
- local flow cache tensors returned from lower flow-matching code

### Important Mutable Spots We Should Be Aware Of

Even though `S3` does not currently look like the old `T3` shared-state bug, there are still some mutable operations worth knowing about:

1. `ref_dict` values may be converted in place
- in [s3gen.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/s3gen/s3gen.py), `forward(...)` will cast `ref_dict` tensor values onto the target device/dtype
- that mutation is happening on the per-call `ref_dict`
- in the current worker path, `active_conds` is cloned per request first, so this does not currently look like a cross-request overwrite

2. waveform trimming is in-place on the produced output tensor
- `output_wavs[:, :len(self.trim_fade)] *= self.trim_fade`
- this mutates the request-local output tensor, not shared model state

3. one-time / utility caches exist
- the LRU resampler cache is shared
- trace counters for shape logging are shared process globals
- these are not part of the decode contract, but they are shared mutable helpers

### Current Architectural Read

For the current sync `scheduled` path, `S3` looks more like:

- shared immutable weights
- per-request inputs and outputs
- no obvious request-local decode state being written back into the shared model object

That is materially different from the original `T3` issue.

### Current Risk Level

Current risk ranking for `S3` shared-state hazards:

- obvious shared mutable inference-state bug like old `T3`: low from current code reading
- performance bottleneck under concurrency: high
- hidden lower-level contention or kernel inefficiency: still possible

So the next `S3` investigation should focus first on:

1. tensor contract / shape tracing
2. concurrency scaling cost
3. only then deeper hidden-state / cache hazards if the runtime behavior suggests them
