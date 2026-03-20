# vLLM Environment Incident

_Last updated: 2026-03-20_

## Why This Exists

This incident blocked the `vLLM` `T3` migration path on the cloud GPU box even though `vllm` looked installed and the exported model package looked valid.

This needs to stay documented in the parent repo because the failure was easy to misdiagnose, easy to reintroduce, and came from multiple stacked causes rather than one missing package.

## Observed Failure Chain

Canonical failing command:

```bash
PYTHONPATH=external/chatterbox/src python external/chatterbox/vllm_t3_preflight.py \
  --model-dir runs/t3_hydra_ar_short_40k_h2_run1/vllm_t3_export \
  --gpu-memory-utilization 0.85
```

Observed failure sequence on the Thunder GPU box:

1. `ImportError: libcudart.so.12: cannot open shared object file`
2. after fixing that, Thunder worker startup complained about unsupported `fork()`
3. after fixing that, `vLLM` still failed with:
   `Model architectures ['ChatterboxT3ForCausalLM'] are not supported for now`

The important lesson is that the first visible error was not the full problem.

## Root Cause

There were three separate causes:

1. CUDA runtime loader path was missing.
   - `vllm._C` needed `libcudart.so.12`
   - the library existed under `/usr/local/cuda/lib64`
   - it was not on `LD_LIBRARY_PATH`

2. Thunder runtime needed spawned workers.
   - the default multiprocessing path hit the known Thunder `fork()` limitation
   - `VLLM_WORKER_MULTIPROC_METHOD=spawn` was required

3. The custom Chatterbox `T3` model registration only happened in the parent process.
   - parent-side `register_vllm_t3_model()` was not enough once `vLLM` spawned worker processes
   - the worker process did not inherit the custom architecture registration
   - that is why the later error became `Model architectures ['ChatterboxT3ForCausalLM'] are not supported for now`

There was also one operational footgun:

- plain `pip install -e external/chatterbox` in the `chatterbox-vllm` env is wrong
- that tries to pull Chatterbox's pinned dependency stack into the `vLLM` env and can downgrade `torch`, `torchaudio`, `transformers`, `tokenizers`, and related packages
- the safe install here is:

```bash
python -m pip install -e external/chatterbox --no-deps
```

That exposes the local `chatterbox` package and the `vLLM` plugin entry point without breaking the `vLLM` environment.

## Permanent Repo Fix

The repo-side fix was to register the custom `T3` architecture through a `vLLM` plugin that loads in spawned worker processes.

Relevant code:

- [`external/chatterbox/pyproject.toml`](/home/ubuntu/ChatterBox_S3_Concurrency/external/chatterbox/pyproject.toml)
- [`external/chatterbox/src/chatterbox/vllm_plugin.py`](/home/ubuntu/ChatterBox_S3_Concurrency/external/chatterbox/src/chatterbox/vllm_plugin.py)
- [`patches/chatterbox_vllm_plugin_fix.patch`](/home/ubuntu/ChatterBox_S3_Concurrency/patches/chatterbox_vllm_plugin_fix.patch) mirrors the exact submodule fix in the parent repo

The runbook was also updated:

- [`GPU_MIGRATION_SERVING_PLAN.md`](/home/ubuntu/ChatterBox_S3_Concurrency/GPU_MIGRATION_SERVING_PLAN.md)

## Canonical Recovery Steps

Use this exact setup in the `chatterbox-vllm` env:

```bash
conda activate chatterbox-vllm
python -m pip install -e external/chatterbox --no-deps
export LD_LIBRARY_PATH=/usr/local/cuda/lib64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
export VLLM_WORKER_MULTIPROC_METHOD=spawn
export PYTHONPATH=$PWD/external/chatterbox/src
```

Then rerun:

```bash
PYTHONPATH=external/chatterbox/src python external/chatterbox/vllm_t3_preflight.py \
  --model-dir runs/t3_hydra_ar_short_40k_h2_run1/vllm_t3_export \
  --gpu-memory-utilization 0.85
```

Expected result:

- `model_registry=ok`
- `engine_init=ok`

## Verified Resolution

This path was revalidated on `2026-03-19` on the cloud GPU box:

- env: `chatterbox-vllm`
- GPU: `RTX A6000`
- model dir:
  `runs/t3_hydra_ar_short_40k_h2_run1/vllm_t3_export`
- result:
  `engine_init=ok`

## Prevention Rules

- Do not use plain `pip install -e external/chatterbox` in `chatterbox-vllm`.
- Always set `LD_LIBRARY_PATH` before blaming the `vLLM` wheel.
- Always set `VLLM_WORKER_MULTIPROC_METHOD=spawn` on this Thunder box.
- If `vLLM` says the custom architecture is unsupported, check the `--no-deps` editable install and the plugin registration path before touching the model export.
- Keep this incident note in the parent repo so later agents debug from the real failure chain instead of only the first error message.

## 2026-03-20 Internal-Prompt `vLLM` Bring-Up Chain

This was a second incident after the original environment/plugin incident was already fixed.
The env was healthy enough to initialize `vLLM`, but the new internal-prompt `vllm_turbo_s3` path still failed in several layers before reaching the first real request.

Canonical command used during this debugging pass:

```bash
conda activate chatterbox-vllm
export HF_TOKEN=...
export LD_LIBRARY_PATH=/usr/local/cuda/lib64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
export VLLM_WORKER_MULTIPROC_METHOD=spawn
export PYTHONPATH=$PWD/external/chatterbox/src

python external/chatterbox/compare_multilingual_runtime.py \
  --impl vllm_turbo_s3 \
  --device cuda \
  --language-id ar \
  --audio-prompt-path "$PROMPT_AUDIO" \
  --text "مرحبا، هذا اختبار لمسار vllm الجديد." \
  --vllm-model-dir runs/t3_vllm_export \
  --vllm-gpu-memory-utilization 0.45 \
  --vllm-max-model-len 2048 \
  --no-vllm-prefix-caching \
  --vllm-enforce-eager \
  --cfg-weight 0 \
  --temperature 0 \
  --repetition-penalty 1.0 \
  --max-new-tokens 128
```

### Failure 1: Hugging Face processor type crash

Observed error:

```text
TypeError: Invalid type of HuggingFace processor. Expected type: ProcessorMixin, but found type: PreTrainedTokenizerFast
```

Why it happened:

- the new `vLLM` path registers `ChatterboxT3ForCausalLM` as a multimodal model
- `vLLM` then asks the model's processing info object for a Hugging Face processor
- the exported `runs/t3_vllm_export` package only contained tokenizer assets, not a real HF `ProcessorMixin`
- `vLLM` rejected the raw tokenizer object

Fix:

- added a local tokenizer-only processor path inside [`external/chatterbox/src/chatterbox/vllm_t3_model.py`](/home/ubuntu/ChatterBox_S3_Concurrency/external/chatterbox/src/chatterbox/vllm_t3_model.py)
- `ChatterboxT3ProcessingInfo.get_hf_processor()` now returns a local tokenizer-backed processor object instead of relying on export-time HF processor files

Verification:

- this removed the original `ProcessorMixin` crash entirely
- engine startup proceeded to later weight loading

### Failure 2: missing Hugging Face token for downstream turbo `S3`

Observed error during validation runs:

```text
LocalTokenNotFoundError: Token is required (`token=True`), but no token found
```

Why it happened:

- `vllm_turbo_s3` still resolves the downstream turbo `S3` snapshot from Hugging Face when the local files are not present
- the runtime uses `os.getenv("HF_TOKEN")` for that access
- the env was otherwise fine, but the request path could not fetch the downstream artifact without the token

Fix:

- export `HF_TOKEN` before running the compare command

Status:

- this was an operational prerequisite, not a code bug in the `vLLM` bridge itself
- do not hardcode the token in repo docs; keep the command as `export HF_TOKEN=...`

### Failure 3: exported text-position embedding shape mismatch

Observed error:

```text
AssertionError: Attempted to load weight torch.Size([2050, 1024]) into parameter torch.Size([2052, 1024])
```

Why it happened:

- the `vLLM` export config claimed `chatterbox_text_pos_embeddings = hp.max_text_tokens + 4`
- the actual multilingual `T3` checkpoint only has `hp.max_text_tokens + 2` text-position rows
- that made the exported config inconsistent with the real checkpoint weights

Fix:

- updated [`external/chatterbox/src/chatterbox/vllm_t3_bridge.py`](/home/ubuntu/ChatterBox_S3_Concurrency/external/chatterbox/src/chatterbox/vllm_t3_bridge.py)
- changed exported `chatterbox_text_pos_embeddings` from `hp.max_text_tokens + 4` to `hp.max_text_tokens + 2`
- regenerated [`runs/t3_vllm_export/config.json`](/home/ubuntu/ChatterBox_S3_Concurrency/runs/t3_vllm_export/config.json)

Regeneration command:

```bash
conda activate chatterbox-vllm
export HF_TOKEN=...
export PYTHONPATH=$PWD/external/chatterbox/src
python external/chatterbox/export_vllm_t3_model.py \
  --from-pretrained \
  --output-dir runs/t3_vllm_export
```

Verification:

- exported config now reports `chatterbox_text_pos_embeddings = 2050`
- this removed the `2050` vs `2052` load failure

### Failure 4: `vLLM` thought two weights were uninitialized

Observed error:

```text
ValueError: Following weights were not initialized from checkpoint: {'lm_head.weight', 'model.embed_tokens.weight'}
```

Why it happened:

- `load_weights()` already had special Chatterbox logic that manually copies `speech_emb.weight` into `model.embed_tokens.weight`
- it also manually copies `speech_head.weight` into `lm_head.weight`
- but the loader did not mark those destination names as loaded in the returned bookkeeping set
- `vLLM` therefore treated them as missing even though the tensors had already been copied correctly

Fix:

- updated [`external/chatterbox/src/chatterbox/vllm_t3_model.py`](/home/ubuntu/ChatterBox_S3_Concurrency/external/chatterbox/src/chatterbox/vllm_t3_model.py)
- after the manual copies, explicitly add:
  - `model.embed_tokens.weight`
  - `lm_head.weight`
  to the loaded-name set returned to `vLLM`

Verification:

- this removed the uninitialized-weight error
- engine startup advanced into runtime request processing

### Failure 5: multimodal embedding inputs were rejected

Observed error:

```text
ValueError: You must set --enable-mm-embeds to input conditioning_embeds
```

Why it happened:

- the internal prompt path sends conditioning tensors through `vLLM`'s multimodal embedding route
- the bridge was constructing `LLM(...)` without enabling multimodal embedding inputs
- request parsing therefore rejected the `conditioning` payload before generation began

Fix:

- updated [`external/chatterbox/src/chatterbox/vllm_t3_bridge.py`](/home/ubuntu/ChatterBox_S3_Concurrency/external/chatterbox/src/chatterbox/vllm_t3_bridge.py)
- pass `enable_mm_embeds=True` into the `LLM(...)` constructor

Verification:

- later engine logs showed `enable_mm_embeds=True`
- request submission got past the conditioning-input validation step

### Current state after those fixes

What now works:

- `vLLM` imports correctly in the `chatterbox-vllm` env
- custom `ChatterboxT3ForCausalLM` registration works in spawned workers
- the internal-prompt model package loads
- the exported config shape now matches the checkpoint
- `vLLM` no longer complains about missing HF processor files
- the request path accepts multimodal conditioning inputs
- the compare path now completes end-to-end when `vLLM` penalties are disabled for this model shape
- the streaming simulator also completes a smoke run with the same setting

Root cause of the remaining generation crash with the old default:

```text
torch.AcceleratorError: CUDA error: unknown error
```

The crash happens inside `vllm/.../sample/ops/penalties.py` when the `vLLM` penalty path is active.

Current best read on why that happens:

- Chatterbox prompt token ids are not one clean language-model vocab
- prompt assembly includes:
  - speech tokens in the speech vocab range
  - offset text tokens
  - a special conditioning token
- the custom model intentionally trims output logits back down to the speech-token vocab only
- the `vLLM` penalty kernels assume prompt/output token ids live inside the same vocab range as the logits they modify
- that assumption is false for this internal-prompt Chatterbox path, so the penalty path is not currently safe here

Verified workaround and current repo behavior:

- `repetition_penalty=1.0` avoids the penalty path and allows end-to-end generation to complete
- the `vllm_turbo_s3` code path now defaults to `repetition_penalty=1.0`
- the CLI entrypoints now also default to `1.0` for `vllm_turbo_s3` while keeping the older defaults for the non-vLLM runtimes

Validated on `2026-03-20`:

- compare path: `compare_multilingual_runtime.py --impl vllm_turbo_s3`
  - completed successfully with `repetition_penalty=1.0`
  - observed `latency_s=[7.2745]`
  - observed `num_samples=20160`
- streaming simulator smoke path: `simulate_streaming_service.py --impl vllm_turbo_s3`
  - completed successfully at `concurrency=1`, `rounds_per_level=1`
  - observed `mean_audio_ready_s=5.2762`
  - observed `audio_seconds_per_second=0.1592`

## Current canonical rerun command

Use this exact command shape in the `chatterbox-vllm` env:

```bash
conda activate chatterbox-vllm
export HF_TOKEN=...
export LD_LIBRARY_PATH=/usr/local/cuda/lib64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
export VLLM_WORKER_MULTIPROC_METHOD=spawn
cd /home/ubuntu/ChatterBox_S3_Concurrency

PYTHONPATH=external/chatterbox/src python external/chatterbox/compare_multilingual_runtime.py \
  --impl vllm_turbo_s3 \
  --device cuda \
  --language-id ar \
  --audio-prompt-path "$PROMPT_AUDIO" \
  --text "مرحبا، هذا اختبار لمسار vllm الجديد." \
  --vllm-model-dir runs/t3_vllm_export \
  --vllm-gpu-memory-utilization 0.45 \
  --vllm-max-model-len 2048 \
  --no-vllm-prefix-caching \
  --vllm-enforce-eager \
  --cfg-weight 0 \
  --temperature 0 \
  --repetition-penalty 1.0 \
  --max-new-tokens 128
```

If you need to regenerate the export first, run:

```bash
conda activate chatterbox-vllm
export HF_TOKEN=...
cd /home/ubuntu/ChatterBox_S3_Concurrency

PYTHONPATH=external/chatterbox/src \
python external/chatterbox/export_vllm_t3_model.py \
  --from-pretrained \
  --output-dir runs/t3_vllm_export
```
