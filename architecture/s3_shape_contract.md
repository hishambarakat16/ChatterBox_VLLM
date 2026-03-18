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

The benchmark currently exposes only one coarse `S3` stage:

- `stage_s3_s`
  - total time spent in the `S3` stack for a request
  - this currently includes both token-to-mel and HiFT/vocoder work

The benchmark does not yet split that into:

- `stage_s3_token2mel_s`
- `stage_s3_hift_s`

So the current doc can pin down the tensor contract and total `S3` cost, but not yet the internal cost split between the two main `S3` components.

## Measured Performance

Current scheduled+Hydra `S3` timings on the traced run:

| Concurrency | `stage_s3_s_mean` | `stage_audio_ready_s_mean` | Throughput (`audio_seconds_per_second`) | Read |
|---|---:|---:|---:|---|
| `c1` | `3.5420s` | `7.3320s` | `0.4426` | single-request baseline on this run |
| `c2` | `1.8349s` | `4.6923s` | `1.4251` | best per-request `S3` efficiency in this run |
| `c4` | `3.2712s` | `6.3983s` | `2.0944` | `S3` starts growing again |
| `c8` | `8.1225s` | `12.4766s` | `2.1536` | `S3` becomes the major bottleneck |

### Relative Increase

Using `c2` as the clean baseline:

| Metric | `c2` | `c4` | `c8` | `c2 -> c4` | `c2 -> c8` |
|---|---:|---:|---:|---:|---:|
| `stage_s3_s_mean` | `1.8349s` | `3.2712s` | `8.1225s` | `+78.3%` | `+342.7%` |
| `stage_audio_ready_s_mean` | `4.6923s` | `6.3983s` | `12.4766s` | `+36.4%` | `+165.9%` |

### What This Suggests

- `S3` scales well enough from `c1 -> c2`
- `S3` degrades materially by `c4`
- `S3` is the dominant downstream bottleneck by `c8`
- the repeated per-request `token2mel.input` traces suggest `S3` is still effectively running per request, not cohort-batched like scheduled `T3`

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
