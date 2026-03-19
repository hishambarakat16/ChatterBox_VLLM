# GPU MIGRATION SERVING PLAN

_Last updated: 2026-03-19_

## Goal

Add a first serious `vLLM` migration spike for `T3` without disturbing the working `scheduled_turbo_s3` path.

This plan is intentionally narrow:

- keep the current Chatterbox scheduled stack working
- add a separate experimental `vllm_turbo_s3` path
- keep `turbo S3` downstream
- defer `Hydra` and `CFG` for the first `vLLM` spike
- isolate package risk with a separate Python environment first

Decision for this spike:

- the `vLLM` path is explicitly Hydra-free
- keep Hydra only on the existing scheduled runtime while the `vLLM` migration is validated

Primary local references:

- [t3_engine_migration_memo.md](/Users/hisham/Code/Bahraini_TTS/architecture/t3_engine_migration_memo.md)
- [t3_serving_stack_layering_memo.md](/Users/hisham/Code/Bahraini_TTS/architecture/t3_serving_stack_layering_memo.md)
- [mtl_tts_vllm_turbo_s3.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/mtl_tts_vllm_turbo_s3.py)
- [worker_vllm.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/runtime/worker_vllm.py)
- [vllm_t3_bridge.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/vllm_t3_bridge.py)
- [vllm_t3_model.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/vllm_t3_model.py)
- [export_vllm_t3_model.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/export_vllm_t3_model.py)
- [vllm_t3_preflight.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/vllm_t3_preflight.py)

## Recommended Environment Strategy

Do not mutate the current `chatterbox-s3` environment first.

Important scope note:

- this repo can be edited locally without any `conda` setup
- the environment commands below are for the GPU server where `vLLM` will actually run
- do not add local-machine module checks just to edit the code or read the memos

Recommended order:

1. Keep `chatterbox-s3` unchanged as the known-good production and benchmark environment.
2. Create a new `chatterbox-vllm` environment for the first `vLLM` spike.
3. Only consider a unified environment after the `vLLM` path is proven useful.

Reason:

- the current stack already has known-good package behavior
- `vLLM` officially recommends a fresh environment on CUDA
- `vLLM` and the current stack may want different PyTorch / CUDA wheel combinations
- separating environments avoids breaking the working T3 scheduler while we experiment

## Environment Options

### Option A: Fresh `vLLM` Environment On The GPU Server

This is the recommended first path.

```bash
conda create -n chatterbox-vllm python=3.11 -y
conda activate chatterbox-vllm
python -m pip install -U pip uv
uv pip install vllm --torch-backend=auto
uv pip install torchaudio librosa safetensors huggingface_hub transformers sentencepiece soundfile
```

Then run Chatterbox from source on the server:

```bash
export PYTHONPATH=$PWD/external/chatterbox/src
```

Notes:

- if `uv pip install vllm --torch-backend=auto` picks the wrong backend, set `UV_TORCH_BACKEND=cu128` or the backend matching your server
- keep this environment focused on the `vLLM` spike, not on preserving every historical package from the scheduled stack

### Option B: Clone The Working Server Environment

Use this only if Option A runs into a missing dependency gap for Chatterbox helpers.

```bash
conda create -n chatterbox-vllm --clone chatterbox-s3 -y
conda activate chatterbox-vllm
python -m pip install -U pip uv
uv pip install vllm --torch-backend=auto
```

Pros:

- fastest way to preserve Chatterbox-side dependencies

Cons:

- higher risk of PyTorch / CUDA / NCCL incompatibility
- less clean than a fresh environment

### Option C: Unified Final Server Environment

Do not start here.

Use this only after:

- `vllm_turbo_s3` has been benchmarked
- the exported model package loads cleanly
- package versions are known to coexist

## What The First `vLLM` Spike Does

The new experimental path is:

```text
app/session layer
  -> custom Chatterbox adapter
  -> vLLM T3 speech-token decoder
  -> turbo S3
```

What stays custom:

- session creation
- prompt audio conditioning
- multilingual text tokenization
- prompt embedding construction
- speech-token filtering
- `turbo S3`

What changes:

- the custom scheduled `T3` decode loop is replaced by `vLLM`
- `Hydra` is deferred
- `CFG` is deferred

## Important First-Spike Limitations

The current `vLLM` spike is experimental and intentionally limited:

1. `Hydra` is disabled
2. `CFG` is disabled
3. prompt embeddings are computed outside `vLLM`
4. speech decode uses an approximate learned speech-position strategy on the `vLLM` side

The approximate position point matters:

- current local `T3` decode uses speech-segment-relative learned positions
- `vLLM` does not naturally expose per-request prompt-length offsets back into the model step loop
- the spike therefore uses an approximate absolute-position mapping for generated speech tokens

This is good enough for a first feasibility spike, but not yet a production-correct port.

## New Files

The migration spike adds:

- [GPU_MIGRATION_SERVING_PLAN.md](/Users/hisham/Code/Bahraini_TTS/GPU_MIGRATION_SERVING_PLAN.md)
- [vllm_t3_model.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/vllm_t3_model.py)
- [vllm_t3_bridge.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/vllm_t3_bridge.py)
- [worker_vllm.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/runtime/worker_vllm.py)
- [mtl_tts_vllm_turbo_s3.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/mtl_tts_vllm_turbo_s3.py)
- [export_vllm_t3_model.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/export_vllm_t3_model.py)
- [vllm_t3_preflight.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/vllm_t3_preflight.py)

## Export The `vLLM` Model Package

Run this on the GPU server, not on the local edit machine.

Before using `vLLM`, export a `vLLM`-friendly model directory from the current T3 checkpoint:

```bash
PYTHONPATH=external/chatterbox/src python external/chatterbox/export_vllm_t3_model.py \
  --checkpoint-dir runs/t3_hydra_ar_short_40k_h2_run1/checkpoint_step_022910 \
  --output-dir runs/t3_hydra_ar_short_40k_h2_run1/vllm_t3_export
```

What this writes:

- `config.json`
- `generation_config.json`
- `chatterbox_vllm_export.json`
- `model.safetensors` symlink or copy to the original `t3_mtl23ls_v2.safetensors`

## Run A `vLLM` Preflight

Run this on the GPU server after the `vLLM` environment is ready.

This checks:

- `vLLM` import works
- the custom T3 architecture registers
- the exported model package is structurally valid
- a `vLLM` engine can initialize on the exported package

```bash
PYTHONPATH=external/chatterbox/src python external/chatterbox/vllm_t3_preflight.py \
  --model-dir runs/t3_hydra_ar_short_40k_h2_run1/vllm_t3_export \
  --device cuda \
  --gpu-memory-utilization 0.85
```

## Run The Experimental Runtime

These runtime commands are also server-side commands.

The new runtime implementation name is:

- `vllm_turbo_s3`

Baseline single-request comparison:

```bash
PYTHONPATH=external/chatterbox/src python external/chatterbox/compare_multilingual_runtime.py \
  --impl vllm_turbo_s3 \
  --device cuda \
  --language-id ar \
  --audio-prompt-path "$PROMPT_AUDIO" \
  --text "مرحبا، هذا اختبار لمسار vllm الجديد." \
  --checkpoint-dir runs/t3_hydra_ar_short_40k_h2_run1/checkpoint_step_022910 \
  --vllm-model-dir runs/t3_hydra_ar_short_40k_h2_run1/vllm_t3_export \
  --turbo-s3-checkpoint-dir ~/.cache/huggingface/hub/models--ResembleAI--chatterbox-turbo/snapshots/<snapshot> \
  --cfg-weight 0 \
  --temperature 0 \
  --max-new-tokens 128 \
  --output-wav vllm_turbo_s3.wav
```

Concurrency benchmark:

```bash
PYTHONPATH=external/chatterbox/src python external/chatterbox/benchmark_multilingual_concurrency.py \
  --impl vllm_turbo_s3 \
  --device cuda \
  --language-id ar \
  --audio-prompt-path "$PROMPT_AUDIO" \
  --text "مرحبا، هذا اختبار لمسار vllm الجديد." \
  --checkpoint-dir runs/t3_hydra_ar_short_40k_h2_run1/checkpoint_step_022910 \
  --vllm-model-dir runs/t3_hydra_ar_short_40k_h2_run1/vllm_t3_export \
  --cfg-weight 0 \
  --temperature 0 \
  --max-new-tokens 128 \
  --concurrency-levels 1 2 4 8
```

Mixed-traffic service simulation:

```bash
PYTHONPATH=external/chatterbox/src python external/chatterbox/simulate_streaming_service.py \
  --impl vllm_turbo_s3 \
  --device cuda \
  --language-id ar \
  --audio-prompt-path "$PROMPT_AUDIO" \
  --checkpoint-dir runs/t3_hydra_ar_short_40k_h2_run1/checkpoint_step_022910 \
  --vllm-model-dir runs/t3_hydra_ar_short_40k_h2_run1/vllm_t3_export \
  --cfg-weight 0 \
  --temperature 0 \
  --max-new-tokens 128 \
  --concurrency-levels 1 2 4 8 \
  --rounds-per-level 2 \
  --stagger-ms 250 \
  --save-mode representative \
  --output-dir streaming_service_sim_vllm
```

## Flags Added For The New Path

The new runtime accepts:

- `--vllm-model-dir`
- `--vllm-export-dir`
- `--vllm-prompt-builder-device`
- `--vllm-tensor-parallel-size`
- `--vllm-gpu-memory-utilization`
- `--vllm-enforce-eager`
- `--vllm-dtype`
- `--vllm-export-copy`

Recommended first values:

- `--cfg-weight 0`
- `--temperature 0`
- `--vllm-prompt-builder-device cpu`
- `--vllm-tensor-parallel-size 1`
- `--vllm-gpu-memory-utilization 0.85`

## Why `CFG` And `Hydra` Are Deferred

### `CFG`

Current `CFG` is not a sampler flag. It duplicates cond/uncond rows and recombines logits outside the model.

That is not the right first `vLLM` port boundary.

### `Hydra`

Current `Hydra` is embedded inside the local decode loop.

For the first `vLLM` spike, the goal is:

- prove the serving-engine replacement
- measure realistic latency and throughput shape
- decide later whether `Hydra` is still worth re-adding

## Success Criteria

The first spike is successful if it does all of the following:

1. exported model package initializes in `vLLM`
2. `vllm_turbo_s3` generates speech tokens and reaches `turbo S3`
3. audio is intelligible enough for feasibility testing
4. mixed-traffic latency under concurrency improves relative to the custom scheduled path

## Failure Criteria

Stop and reassess if any of these happen:

1. `vLLM` engine loads, but generated speech tokens are obviously invalid
2. quality collapses because the approximate speech-position strategy is too wrong
3. memory duplication from prompt-building plus `vLLM` is too expensive
4. latency does not improve enough to justify the engine migration

If that happens, the next path is:

- deeper custom `vLLM` model work
- or move directly to a more complete continuous-batching rewrite

## Practical Recommendation

Do these in order:

1. export the model package
2. run preflight
3. run `compare_multilingual_runtime.py` with `vllm_turbo_s3`
4. run concurrency benchmark
5. only then decide whether to invest in `Hydra` re-introduction or a deeper `vLLM` model port
