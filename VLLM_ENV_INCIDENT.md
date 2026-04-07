# vLLM Environment Incident

_Last updated: 2026-03-19_

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
export TORCH_LIB="$CONDA_PREFIX/lib/python3.11/site-packages/torch/lib"
if [ -d /usr/local/cuda/lib64 ]; then
  export LD_LIBRARY_PATH="/usr/local/cuda/lib64:$TORCH_LIB${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
else
  python -m pip install --no-cache-dir nvidia-cuda-runtime-cu12==12.4.127
  export CUDART12_DIR="$CONDA_PREFIX/lib/python3.11/site-packages/nvidia/cuda_runtime/lib"
  export LD_LIBRARY_PATH="$TORCH_LIB:$CUDART12_DIR${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
fi
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
