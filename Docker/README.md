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
    ├── special_tokens_map.json
    ├── tokenizer.json
    ├── tokenizer_config.json
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
