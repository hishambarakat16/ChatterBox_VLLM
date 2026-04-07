# Dockerized vLLM + Turbo S3 Service

This directory packages the current runnable `vLLM T3 + turbo S3` service into
one GPU container.

The image contains:

- the service code
- the Python runtime and vLLM dependencies
- the default prompt WAV (`SPK_17_000003.wav`)

The image does **not** bake the large model artifacts into the container by
default. Instead, it expects a mounted `/models` directory so the same image can
be reused across machines.

## CUDA Contract

This image is intentionally aligned to a CUDA 12 runtime contract.

- base image: `nvidia/cuda:12.8.1-cudnn-runtime-ubuntu22.04`
- Docker mirrors the local conda recovery flow that passed preflight
- `UV_TORCH_BACKEND=cu128` is set before installing `vllm==0.17.1`
- `vLLM` is installed via `uv pip install vllm==0.17.1 --torch-backend=auto`
- CUDA 12 runtime libs are installed in Python site-packages as a fallback (`nvidia-cuda-runtime-cu12`)

This keeps startup behavior deterministic for `vllm._C` (`libcudart.so.12`) even when `/usr/local/cuda/lib64` is absent, while still letting the torch-family versions come from the `vLLM` install instead of hard-pinning an older stack.

## Files

- `Dockerfile`: GPU runtime image for the FastAPI service
- `entrypoint.sh`: resolves env defaults, validates model paths, optionally prepares models, starts the API
- `prepare_models.py`: validates or auto-downloads the base/turbo checkpoints and can export a self-contained vLLM model package
- `docker-compose.yaml`: example Compose service with GPU, ports, healthcheck, and mounted `/models`
- `.env.example`: sample environment file for Compose

## Recommended Host Model Layout

Mount a host directory to `/models` with this shape:

```text
/models
├── chatterbox_base
│   ├── ve.pt
│   ├── conds.pt
│   ├── grapheme_mtl_merged_expanded_v1.json
│   ├── Cangjie5_TC.json
│   └── t3_mtl23ls_v2.safetensors
├── chatterbox_turbo
│   └── s3gen_meanflow.safetensors
└── t3_vllm_export
    ├── config.json
    ├── generation_config.json
    ├── model.safetensors
    └── chatterbox_vllm_export.json
```

## Important Container Contract

Set both:

- `CHECKPOINT_DIR=/models/chatterbox_base`
- `BASE_CHECKPOINT_DIR=/models/chatterbox_base`

This is intentional. The current service loader only uses `from_local(...)`
when `CHECKPOINT_DIR` is set. If you set only `BASE_CHECKPOINT_DIR`, the code
falls back to `from_pretrained(...)` and redownloads the base checkpoint.

## Important Export Note

For Docker, prefer a **self-contained** vLLM export. The original export helper
defaults to symlinking `model.safetensors` back into the HF cache. That is fine
on one machine, but it is a weak container contract.

Use:

```bash
python external/chatterbox/export_vllm_t3_model.py \
  --base-checkpoint-dir /path/to/chatterbox_base \
  --output-dir /path/to/t3_vllm_export \
  --copy
```

The container helper also defaults to `VLLM_EXPORT_COPY=1` for the same reason.

Tokenizer JSON files are not required for the current vLLM bridge path because
the service uses the multilingual grapheme tokenizer from
`/models/chatterbox_base/grapheme_mtl_merged_expanded_v1.json`.

## Easiest Source For `/models`

The simplest path is to populate `/models` from the backup repo:

- `https://huggingface.co/Hishambarakat/ChatterBox_VLLM`

Map those folders like this:

- `hf_cache/chatterbox_base_snapshot_05e904af2b5c7f8e482687a9d7336c5c824467d9/` -> `/models/chatterbox_base/`
- `hf_cache/chatterbox_turbo_s3_snapshot_749d1c1a46eb10492095d68fbcf55691ccf137cd/` -> `/models/chatterbox_turbo/`
- `runs/t3_vllm_export/` -> `/models/t3_vllm_export/`

## Build

From the repo root:

```bash
docker build -f Docker/Dockerfile -t chatterbox-vllm:latest .
```

## Run With Pre-Staged Models

```bash
docker run --rm --gpus all \
  -p 8000:8000 \
  -v /absolute/path/to/models:/models \
  -e HF_TOKEN=hf_your_token_here \
  chatterbox-vllm:latest
```

The image defaults to:

- `CHECKPOINT_DIR=/models/chatterbox_base`
- `BASE_CHECKPOINT_DIR=/models/chatterbox_base`
- `TURBO_S3_CHECKPOINT_DIR=/models/chatterbox_turbo`
- `VLLM_MODEL_DIR=/models/t3_vllm_export`
- `DEFAULT_AUDIO_PROMPT_PATH=/app/SPK_17_000003.wav`

## First-Boot Auto-Prepare Mode

If you mount an empty `/models` volume and want the container to populate it:

```bash
docker run --rm --gpus all \
  -v /absolute/path/to/models:/models \
  -e HF_TOKEN=hf_your_token_here \
  -e AUTO_DOWNLOAD_BASE_CHECKPOINT=1 \
  -e AUTO_DOWNLOAD_TURBO_S3=1 \
  -e AUTO_EXPORT_VLLM_MODEL=1 \
  chatterbox-vllm:latest prepare-models
```

That will:

- download the base multilingual Chatterbox files into `/models/chatterbox_base`
- download turbo `s3gen_meanflow.safetensors` into `/models/chatterbox_turbo`
- export a self-contained vLLM T3 package into `/models/t3_vllm_export`

After that, start the service normally:

```bash
docker run --rm --gpus all \
  -p 8000:8000 \
  -v /absolute/path/to/models:/models \
  chatterbox-vllm:latest
```

## Compose

```bash
cd Docker
cp .env.example .env
# edit .env
docker compose up --build
```

The compose file assumes:

- NVIDIA Container Toolkit is installed
- the Docker daemon can see a GPU
- `MODEL_ROOT_HOST` points at a persistent host directory

## Smoke Test

```bash
curl -sS http://127.0.0.1:8000/health

curl -sS -H 'Content-Type: application/json' \
  -d '{"text":"صباح الخير. هذا اختبار قصير للصوت.","language_id":"ar","auto_max_new_tokens":true,"auto_max_new_tokens_cap":128}' \
  http://127.0.0.1:8000/v1/tts/meta | jq '.profile._trace.stage_meta'
```

## Notes

- `VLLM_ENABLE_PREFIX_CACHING` must stay `false`.
- `VLLM_WORKER_MULTIPROC_METHOD=spawn` is set by default.
- `prepare_models.py` is run automatically before `serve` and fails fast if the model contract is incomplete.
- The container keeps the same service entrypoint as the manual path: `external/chatterbox/fastapi_vllm_tts_service.py`.
- If startup fails with `RuntimeError: operator torchvision::nms does not exist` or `cannot import name 'Gemma3Config' from 'transformers'`, rebuild from this repo's current Dockerfile. It avoids downgrading the `vLLM` torch/transformers stack and keeps those packages mutually compatible.
- `entrypoint.sh` now fronts `/opt/conda/lib` before system libraries, then builds `LD_LIBRARY_PATH` from multiple CUDA 12 locations (`torch/lib`, pip CUDA runtime dirs, and system CUDA paths), and fails fast if `vllm._C` cannot import.
- If startup fails with `CXXABI_1.3.15 not found` from `libstdc++.so.6`, the process is picking the system C++ runtime instead of the Conda one. Rebuild from this repo's current Dockerfile/entrypoint so `/opt/conda/lib` is preferred.
- The runtime image intentionally includes `build-essential`. `vLLM` can trigger Triton / Torch Inductor compilation during engine startup, and that path fails with `Failed to find C compiler` if the final container has no compiler.
- Temporary workaround if you need to get unstuck before rebuilding: run with `-e VLLM_ENFORCE_EAGER=true`. That avoids the compiled path, but it is a performance fallback rather than the preferred production setting.
- The builder now hard-fails if `vllm`, `torch`, `torchaudio`, `torchvision`, `transformers`, or `chatterbox-tts` are missing, so a “successful” image cannot silently omit the runtime stack.
- Cross-GPU support: this image can run on different NVIDIA GPUs (e.g., RTX 4060 Ti, RTX A6000) as long as the host driver supports the CUDA 12 user-space stack used by the container.
