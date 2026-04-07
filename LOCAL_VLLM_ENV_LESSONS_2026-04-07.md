# Local vLLM Env Lessons (2026-04-07)

## Scope

This note documents what happened while bringing up the non-Docker `chatterbox-llm` environment and what fixed it.

It is focused on the local conda flow (`python 3.11`, `vllm==0.17.1`, `vllm_turbo_s3` serving path).

## Outcome

Final state is healthy:

- `export_vllm_t3_model.py` succeeded
- `vllm_t3_preflight.py` succeeded with:
  - `model_registry=ok`
  - `engine_init=ok`

## What Failed

Preflight failed with:

- `ImportError: libcudart.so.12: cannot open shared object file: No such file or directory`

Important context from the same environment:

- `torch==2.10.0+cu130`
- `torchaudio==2.10.0+cu130`
- `torchvision==0.25.0+cu130`
- `transformers==4.57.6`
- `vllm==0.17.1`

`vllm._C` still required `libcudart.so.12` and could not find it at runtime.

## Root Cause

Two separate issues combined:

1. The common export used in docs:
   - `export LD_LIBRARY_PATH=/usr/local/cuda/lib64...`
   did not help on this machine because `/usr/local/cuda/lib64` was not present.

2. The environment had CUDA 13 user-space libs, but not the required CUDA 12 runtime `.so` that `vllm._C` looked up (`libcudart.so.12`).

## Fix That Worked

Install CUDA 12 runtime package inside the env, then export a loader path that includes torch libs and the CUDA runtime site-package directory.

```bash
python -m pip install --no-cache-dir nvidia-cuda-runtime-cu12==12.4.127

export TORCH_LIB="$CONDA_PREFIX/lib/python3.11/site-packages/torch/lib"
export CUDART12_DIR="$CONDA_PREFIX/lib/python3.11/site-packages/nvidia/cuda_runtime/lib"
export LD_LIBRARY_PATH="$TORCH_LIB:$CUDART12_DIR:${LD_LIBRARY_PATH:-}"
export VLLM_WORKER_MULTIPROC_METHOD=spawn
export PYTHONPATH=$PWD/external/chatterbox/src
```

Validation:

```bash
python -c "import vllm._C; print('vllm._C import ok')"
python external/chatterbox/vllm_t3_preflight.py --model-dir "$MODEL_ROOT/t3_vllm_export" --gpu-memory-utilization 0.5
```

## Golden Install Order (Local Conda)

Use this order and keep it stable:

1. Create env (`python=3.11`).
2. Install `uv`.
3. Install `vllm` first:
   - `uv pip install vllm==0.17.1 --torch-backend=auto`
4. Install additive runtime deps (do not pin older torch-family packages).
5. Install local chatterbox with no deps:
   - `python -m pip install -e external/chatterbox --no-deps`
6. Set runtime env vars (`LD_LIBRARY_PATH`, `VLLM_WORKER_MULTIPROC_METHOD`, `PYTHONPATH`).
7. Export model package, then run preflight.

## Lessons / Rules

- Keep the torch-family stack owned by `vllm` in this env.
- Do not overfit the fix to a guessed wheel suffix like `cu124`.
  - the healthy local env ended up on `torch==2.10.0+cu130` / `torchvision==0.25.0+cu130`
  - what actually mattered was preserving the `vllm`-resolved stack and then making `libcudart.so.12` available at runtime
- Do not use plain editable install:
  - avoid `pip install -e external/chatterbox`
  - use `python -m pip install -e external/chatterbox --no-deps`
- Do not assume `/usr/local/cuda/lib64` exists on every machine.
- Always validate with:
  - `python -c "import vllm._C"`
  - `python external/chatterbox/vllm_t3_preflight.py ...`
- If `vllm._C` import fails, inspect missing shared libs first before changing model code.

## Docker Follow-Through

Docker should mirror the same successful sequence:

1. install `vllm` first
2. install only additive runtime deps after that
3. install `chatterbox` with `--no-deps`
4. include `nvidia-cuda-runtime-cu12==12.4.127`
5. fail fast on `import vllm._C`

The portable contract is therefore:

- keep the package-resolution order from the working local env
- keep a CUDA 12 runtime available for `vllm._C`
- do not hard-pin an older torch-family stack after `vllm`

## Known Benign Warnings Seen In Healthy Run

- Duplicate custom model registration warning:
  - `Model architecture ChatterboxT3ForCausalLM is already registered ...`
- NCCL process-group warning on process exit from preflight:
  - preflight still completed with `engine_init=ok`

## Security Note

An HF token appeared in terminal history during setup. Rotate/revoke that token and issue a new one.
