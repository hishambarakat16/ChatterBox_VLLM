# Serving Handoff - 2026-04-03

## Scope

This memo captures the current runnable `vllm_turbo_s3` serving state in this repo, the canonical setup/start commands, the new S3 geometry instrumentation, and the main operational failure modes discovered on the cloud GPU boxes.

Read this together with:

- [CLOUD_GPU_QUICKSTART.md](/home/ubuntu/ChatterBox_S3_Concurrency/CLOUD_GPU_QUICKSTART.md)
- [GPU_MIGRATION_SERVING_PLAN.md](/home/ubuntu/ChatterBox_S3_Concurrency/GPU_MIGRATION_SERVING_PLAN.md)
- [VLLM_ENV_INCIDENT.md](/home/ubuntu/ChatterBox_S3_Concurrency/VLLM_ENV_INCIDENT.md)

## Current Read

- The production path is `external/chatterbox/fastapi_vllm_tts_service.py` using `vllm_turbo_s3`.
- `T3` decode is batched through one shared `vllm.generate()` call.
- `S3` finalize runs in parallel across up to 4 CUDA streams after the batched `T3` stage.
- Prefix caching must remain disabled for the embed-only prompt path.
- `repetition_penalty` is intentionally hardcoded to `1.0` in the vLLM path to avoid the old device-side assert.
- The chunked endpoint `/v1/tts/stream_chunks` is the primary production endpoint.

## Canonical Fresh Setup

Clone and sync the repo and submodule:

```bash
cd /home/ubuntu
export GITHUB_TOKEN=YOUR_GITHUB_TOKEN
git clone https://$GITHUB_TOKEN@github.com/hishambarakat16/ChatterBox_S3_Concurrency.git
cd ChatterBox_S3_Concurrency
git submodule sync -- external/chatterbox
git submodule update --init external/chatterbox
```

Create the serving environment:

```bash
conda create -n chatterbox-vllm python=3.11 -y
conda activate chatterbox-vllm
python -m pip install -U pip uv
export UV_TORCH_BACKEND=cu128
uv pip install vllm --torch-backend=auto
python -m pip install huggingface_hub safetensors librosa soundfile sentencepiece
python -m pip install -e external/chatterbox --no-deps
python -m pip install conformer==0.3.2 diffusers==0.29.0 omegaconf s3tokenizer
python -m pip install fastapi uvicorn psutil
```

Important rule:

- Do not use plain `pip install -e external/chatterbox` in `chatterbox-vllm`. Use `--no-deps`.

If the submodule changes later, rerun:

```bash
conda activate chatterbox-vllm
cd /home/ubuntu/ChatterBox_S3_Concurrency
python -m pip install -e external/chatterbox --no-deps
```

## Export And Preflight

Export the vLLM `T3` package:

```bash
conda activate chatterbox-vllm
cd /home/ubuntu/ChatterBox_S3_Concurrency
export PYTHONPATH=$PWD/external/chatterbox/src
export LD_LIBRARY_PATH=/usr/local/cuda/lib64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}

python external/chatterbox/export_vllm_t3_model.py \
  --base-checkpoint-dir ~/.cache/huggingface/hub/models--ResembleAI--chatterbox/snapshots/05e904af2b5c7f8e482687a9d7336c5c824467d9 \
  --output-dir runs/t3_vllm_export
```

Fallback if the cache path is missing:

```bash
python external/chatterbox/export_vllm_t3_model.py \
  --from-pretrained \
  --output-dir runs/t3_vllm_export
```

Preflight the export:

```bash
python external/chatterbox/vllm_t3_preflight.py \
  --model-dir runs/t3_vllm_export \
  --gpu-memory-utilization 0.5
```

Expected result:

- `model_registry=ok`
- `engine_init=ok`

## Start The API

```bash
conda activate chatterbox-vllm
cd /home/ubuntu/ChatterBox_S3_Concurrency

export HF_TOKEN=hf_your_token_here
export LD_LIBRARY_PATH=/usr/local/cuda/lib64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
export VLLM_WORKER_MULTIPROC_METHOD=spawn
export PYTHONPATH=$PWD/external/chatterbox/src

export VLLM_MODEL_DIR=$PWD/runs/t3_vllm_export
export TURBO_S3_CHECKPOINT_DIR=~/.cache/huggingface/hub/models--ResembleAI--chatterbox-turbo/snapshots/749d1c1a46eb10492095d68fbcf55691ccf137cd
export DEFAULT_AUDIO_PROMPT_PATH=$PWD/SPK_17_000003.wav

export VLLM_GPU_MEMORY_UTILIZATION=0.5
export VLLM_MAX_MODEL_LEN=2048
export VLLM_ENFORCE_EAGER=false
export VLLM_ENABLE_PREFIX_CACHING=false
export API_BATCH_WINDOW_MS=5
export API_MAX_BATCH_SIZE=8

python external/chatterbox/fastapi_vllm_tts_service.py
```

## Smoke Tests

Health check:

```bash
curl -sS http://127.0.0.1:8000/health
```

Single metadata request:

```bash
curl -sS -H 'Content-Type: application/json' \
  -d '{"text":"صباح الخير. هذا اختبار قصير للصوت.","language_id":"ar","auto_max_new_tokens":true,"auto_max_new_tokens_cap":128}' \
  http://127.0.0.1:8000/v1/tts/meta | jq '.profile._trace.stage_meta'
```

Chunked streaming smoke:

```bash
python external/chatterbox/stream_chunks_client.py \
  --url http://127.0.0.1:8000/v1/tts/stream_chunks \
  --concurrency 2 \
  --num-requests 4 \
  --text "صباح الخير. هذا اختبار قصير للصوت." \
  --text "هل يبدو الصوت طبيعيًا عندما ينتقل من سؤال إلى جواب؟"
```

Recent scheduler traces:

```bash
curl -sS http://127.0.0.1:8000/v1/tts/trace/recent?limit=5 | jq '.batches'
```

## New S3 Geometry Instrumentation

Use these fields for bucket design and TRT planning:

- `s3_token2mel_speech_token_len`: generated speech-token length for the chunk
- `s3_token2mel_prompt_token_len`: prompt/reference speech-token length
- `s3_token2mel_total_token_len`: total token length seen by the S3 flow encoder
- `s3_token2mel_prompt_mel_frames`: prompt mel frames
- `s3_token2mel_generated_mel_frames`: generated mel frames for the chunk
- `s3_token2mel_total_mel_frames`: prompt + generated mel frames
- `s3_hift_input_mel_frames`: mel frames passed into HiFT
- `s3_hift_output_samples`: waveform sample count emitted by HiFT

Do not size buckets from raw frontend text length alone. The real decoder axis is the S3 token/mel geometry above.

## Verified Live Read (2026-04-03)

From a live `/v1/tts/meta` call:

- `t3_text_token_len = 37`
- `t3_generated_tokens = 2`
- `s3_token2mel_speech_token_len = 2`
- `s3_token2mel_prompt_token_len = 150`
- `s3_token2mel_generated_mel_frames = 4`
- `s3_hift_input_mel_frames = 4`
- `s3_hift_output_samples = 1920`

From a live `/v1/tts/stream_chunks` chunk trace:

- `s3_token2mel_batch_size = 1`
- `s3_token2mel_speech_token_len = 47`
- `s3_token2mel_prompt_token_len = 150`
- `s3_token2mel_total_token_len = 197`
- `s3_token2mel_prompt_mel_frames = 300`
- `s3_token2mel_generated_mel_frames = 94`
- `s3_token2mel_total_mel_frames = 394`
- `s3_token2mel_mel_channels = 80`
- `s3_token2mel_embedding_dim = 192`
- `s3_token2mel_ratio = 2`
- `s3_token2mel_finalize = 1`
- `s3_hift_input_batch_size = 1`
- `s3_hift_input_mel_channels = 80`
- `s3_hift_input_mel_frames = 94`
- `s3_hift_output_samples = 45120`

Sanity checks from that same run:

- `generated_mel_frames (94) ~= speech_token_len (47) * ratio (2)`
- `hift_input_mel_frames (94) == generated_mel_frames (94)`

Additional live chunk-trace sample while the API was still up (`2026-04-03`, 8 observed chunks across 3 requests):

- shortest observed chunk in the sample: `speech_token_len=2`, `total_token_len=152`, `generated_mel_frames=4`, `total_mel_frames=304`, `hift_output_samples=1920`
- longest observed chunk in the sample: `speech_token_len=54`, `total_token_len=204`, `generated_mel_frames=108`, `total_mel_frames=408`, `hift_output_samples=51840`
- other observed points in the same sample included:
  - `speech_token_len=8`, `total_token_len=158`, `generated_mel_frames=16`, `hift_output_samples=7680`
  - `speech_token_len=12`, `total_token_len=162`, `generated_mel_frames=24`, `hift_output_samples=11520`
  - `speech_token_len=28`, `total_token_len=178`, `generated_mel_frames=56`, `hift_output_samples=26880`
  - `speech_token_len=47`, `total_token_len=197`, `generated_mel_frames=94`, `hift_output_samples=45120`
- across that sample, the prompt-side constants remained stable at `prompt_token_len=150` and `prompt_mel_frames=300`
- the live relationship continued to hold: `generated_mel_frames ~= 2 * speech_token_len` and `hift_input_mel_frames == generated_mel_frames`

Larger live chunk sample (`2026-04-03`, 32 chunks across 12 requests, same chunking config):

- `s3_token2mel_speech_token_len`: `min=2`, `p50=8`, `p90=32.5`, `max=54`
- `s3_token2mel_total_token_len`: `min=152`, `p50=158`, `p90=182.5`, `max=204`
- `s3_token2mel_generated_mel_frames`: `min=4`, `p50=16`, `p90=65`, `max=108`
- `s3_hift_output_samples`: `min=1920`, `p50=7680`, `p90=31200`, `max=51840`
- prompt-side constants were still fixed at `prompt_token_len=150` and `prompt_mel_frames=300`
- most frequent live pair in this sample was `speech_token_len=2 -> generated_mel_frames=4` (`13/32` chunks)
- next most frequent pairs were `8 -> 16` (`5/32`) and `12 -> 24` (`3/32`)
- full sampled JSON snapshot was saved during capture at `/tmp/live_s3_boundary_sample.json`

From a live `stream_chunks_client.py` smoke (`c=2`, `n=4`):

- `first_chunk_s (client mean) = 1.7104s`
- `s3_finalize_wait_s (mean) = 0.0009s`
- `chunk_t3_active_s (mean) = 0.6445s`
- `s3_token2mel_s (mean) = 0.3831s`
- `s3_hift_s (mean) = 0.1766s`
- `requests OK / total = 4 / 4`

This is the latest checked state before the current GPU became unavailable.

## Operational Notes

- `Ctrl+C` should drain requests, close the engine, and force-kill lingering `EngineCore` child processes.
- If a request crashes and an orphan `VLLM::EngineCore` PID is still visible in the container, kill that PID first.
- If the PID is gone but VRAM remains allocated and `nvidia-smi --gpu-reset -i 0` fails with the primary-GPU error, that remaining allocation is provider-side. In that case the practical fix is container restart or provider GPU reset.
- On Thunder/prototyping boxes, always keep `VLLM_WORKER_MULTIPROC_METHOD=spawn`.
- Keep `VLLM_ENABLE_PREFIX_CACHING=false`.
- Keep `VLLM_GPU_MEMORY_UTILIZATION=0.5` on A6000-class boxes unless you deliberately rebalance against S3 VRAM demand.

## If Someone Needs To Reconstruct The Whole Path Fast

Use this order:

1. [CLOUD_GPU_QUICKSTART.md](/home/ubuntu/ChatterBox_S3_Concurrency/CLOUD_GPU_QUICKSTART.md) sections 19-22 for the short operator runbook.
2. [GPU_MIGRATION_SERVING_PLAN.md](/home/ubuntu/ChatterBox_S3_Concurrency/GPU_MIGRATION_SERVING_PLAN.md) section 8 for the full env var, endpoint, instrumentation, and troubleshooting reference.
3. [VLLM_ENV_INCIDENT.md](/home/ubuntu/ChatterBox_S3_Concurrency/VLLM_ENV_INCIDENT.md) if startup fails around `libcudart`, `spawn`, or custom model registration.
