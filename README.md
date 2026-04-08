# ChatterBox Concurrency

**High-throughput concurrent TTS on a single GPU using vLLM batching + parallel S3 finalization.**

---

## The Problem

[Chatterbox](https://github.com/resemble-ai/chatterbox) is an open-source multilingual TTS system built on a two-stage architecture:

- **T3** — a transformer that converts text tokens into discrete speech tokens
- **S3** — a flow-matching vocoder that converts speech tokens into mel spectrograms and then waveforms via HiFiGAN

Out of the box, Chatterbox can only handle **one request at a time**. Each request occupies the GPU from start to finish before the next one begins. Under any real concurrent load, requests queue up and per-request latency degrades linearly with queue depth.

The root causes:

1. **T3 has no batching** — each request runs its own autoregressive decode loop, one token at a time, on the full GPU
2. **S3 finalization is sequential** — even if T3 could batch, the mel synthesis step ran one request after another in a Python for-loop
3. **No admission scheduler** — requests were not grouped or co-scheduled; the runtime had no concept of concurrent sessions

---

## The Solution

This repo replaces the original Chatterbox runtime with a serving stack that handles many concurrent requests at GPU-native speed:

### 1. vLLM for T3 Batching

The T3 transformer is exported as a vLLM-compatible causal LM and served through vLLM's `AsyncLLMEngine`. This enables:

- **True cross-request batching** — N concurrent T3 decodes run as a single `(N, seq_len)` forward pass, not N separate passes
- **Continuous batching** — requests arriving at different times are grouped into shared decode steps automatically
- **CUDA graphs** — with `VLLM_ENFORCE_EAGER=false`, the decode kernel is fused via CUDA graphs giving ~47% latency reduction at c=4

The T3 model uses an embed-only prompt path (`prompt_embeds` tensor, no token IDs) to carry voice conditioning through the vLLM engine.

**Stack note:** this uses the **standard multilingual T3** weights (not a turbo T3), paired with the **turbo S3 meanflow** checkpoint (`ResembleAI/chatterbox-turbo`, `s3gen_meanflow.safetensors`). Turbo S3 runs a 2-step ODE solver instead of the default 10-step, making S3 ~5× faster while keeping quality.

### 2. Parallel S3 Finalization

After the batched T3 decode, each request still needs its own S3 inference (speech tokens → mel → wav). These are independent and embarrassingly parallel. We run them concurrently using a `ThreadPoolExecutor` with one `torch.cuda.Stream` per worker:

```
T3 decode (vLLM batched): [req0, req1, req2, req3] → one GPU pass
                                       ↓
S3 finalize (parallel):   req0 ──┐
                          req1 ──┤→ all run concurrently on separate CUDA streams
                          req2 ──┤
                          req3 ──┘
```

This eliminated `s3_finalize_wait_s` from **0.719s → 0.001s** at c=4.

### 3. Chunked Streaming

Text is split at natural boundaries (sentence punctuation → clause punctuation → word cap) before inference. Each chunk is synthesized independently and streamed back as an NDJSON event immediately on completion. The first audio arrives after ~1.5s regardless of total text length.

---

## Performance

Historical optimization measurements were run on **NVIDIA RTX A6000 (48 GB)**.
Latest validation also includes **NVIDIA RTX 4060 Ti (16 GB)** to show how the
same stack behaves on a smaller-memory card.

### Before vs After (c=4 concurrent requests)

| Metric | Baseline (original Chatterbox) | This repo |
|--------|-------------------------------|-----------|
| First chunk latency | ~4.5s (full text) | **~1.6s** (first chunk) |
| T3 decode (c=4) | 4 × ~2.0s serial | **~1.0s** batched |
| S3 finalize wait | ~0.72s (sequential queue) | **~0.001s** (parallel) |
| Throughput (c=16) | ~1.0× audio real-time | **~9.9× audio real-time** |
| Requests at once | 1 | 16+ |

### Key Measurements (c=2, n=4, CUDA graphs enabled)

```
first_chunk_s (mean):        1.71 s
s3_finalize_wait_s (mean):   0.0009 s
s3_token2mel_s (mean):       0.383 s
s3_hift_s (mean):            0.177 s
```

### Throughput Scaling (same text, CUDA graphs enabled)

| Concurrency | T3 batch size | T3 decode time | Total wall time | Audio RT factor |
|-------------|--------------|----------------|-----------------|-----------------|
| 1           | 1            | ~0.6s          | ~2.0s           | ~3.3×           |
| 4           | 4            | ~1.0s          | ~3.5s           | ~5.4×           |
| 16          | 16           | ~1.1s          | ~7.4s           | **~9.9×**       |

T3 decode time barely increases from c=1 to c=16 — that's the vLLM batching effect.

### Cross-GPU Validation (Arabic stream_chunks, April 2026)

Workload used for the table below:

- endpoint: `/v1/tts/stream_chunks`
- texts:
  - `صباح الخير. هذا اختبار قصير للصوت.`
  - `هل يبدو الصوت طبيعيًا عندما ينتقل من سؤال إلى جواب؟ هذا ما نريد التأكد منه.`

| GPU | Concurrency | Requests | first_chunk_s (mean) | total_s (mean) | RTF (mean) | wall_s |
|-----|-------------|----------|----------------------|----------------|------------|--------|
| RTX A6000 (historical baseline) | 4 | n/a | ~1.6s | ~3.5s | ~5.4x | n/a |
| RTX A6000 (historical baseline) | 16 | n/a | n/a | ~7.4s | ~9.9x | n/a |
| RTX 4060 Ti (16 GB) | 4 | 8 | 2.08s | 5.02s | 0.51x | 11.89s |
| RTX 4060 Ti (16 GB) | 8 | 16 | 4.15s | 7.04s | 0.37x | 15.28s |
| RTX 4060 Ti (16 GB) | 16 | 32 | 5.59s | 10.15s | 0.26x | 22.79s |

Interpretation:

- The system still scales correctly on 4060 Ti (all requests completed at c=16).
- On 16 GB VRAM, higher concurrency pushes queueing and S3 finalize wait up, so
  first-chunk latency rises faster than on A6000.
- This is capacity-limited scaling, not a scheduler correctness issue.

### Baseline vs vLLM (Same GPU, April 2026)

Direct comparison on the same **RTX 4060 Ti (16 GB)** using `/v1/tts`:

- Baseline endpoint: `http://127.0.0.1:8001/v1/tts` (basic local FastAPI).
- Optimized endpoint: `http://127.0.0.1:8000/v1/tts` (vLLM + scheduler path).
- Workload: same two Arabic prompts used above.
- Request volume per run: `num_requests = 4 * concurrency`.
- vLLM run policy: one single-request warmup sent before each measured run.

| C | Baseline mean total (s) | Ours mean total (s) | Mean speedup | Baseline req/s | Ours req/s |
|---|--------------------------|---------------------|--------------|----------------|------------|
| 1 | 4.642 | 1.318 | 3.52x | 0.215 | 0.759 |
| 2 | 9.072 | 1.301 | 6.97x | 0.205 | 1.536 |
| 4 | 18.038 | 1.834 | 9.84x | 0.200 | 2.180 |
| 8 | 38.065 | 3.135 | 12.14x | 0.186 | 2.371 |
| 16 | 81.092 | 5.400 | 15.02x | 0.173 | 2.817 |

Key read:

- vLLM is faster at every tested concurrency level, and the advantage grows with load.
- At `c=16`, baseline queue wait dominates (`~75.31s` mean server queue wait), while vLLM remains much lower (`~2.28s`).
- This validates that the optimized path is not just lower-latency at `c=1`; it preserves throughput as concurrency increases.

### Performance Chart

![ChatterBox Concurrency Optimization](docs/performance.png)

**Left** — throughput (audio-seconds synthesized per wall-second) as concurrency grows, traced across all four optimization phases.  
**Right** — throughput at c=4 for each phase showing the step-by-step improvement.

Each phase built on the previous:

| Phase | What changed | Throughput at c=4 |
|-------|-------------|-------------------|
| Original | Single-request only, no concurrency | ~0.45× |
| Coarse-lock fix | Requests run concurrently; T3 still locked per-request | 1.23× |
| Scheduled T3 batching | T3 cohorts batched together; GPU-local alignment state | 2.60× |
| + Turbo S3 | S3 synthesis ~5× faster via 2-step meanflow ODE | 3.22× |
| + vLLM + Parallel S3 | True T3 cross-request batching via vLLM; S3 on parallel CUDA streams | **4.9×** (4 reqs) / **9.9×** (16 reqs) |

The "scheduled T3 batching" phase is what first enabled multiple requests to share T3 compute — the scheduler groups concurrent requests into cohorts and runs their T3 decodes in a single batched forward pass. Adding turbo S3 on top then unlocked the full throughput potential of that batching by removing the S3 bottleneck. vLLM replaced the custom T3 scheduler with a production inference engine that handles continuous batching automatically.

---

## Installation

### Current status for recreation

If you are recreating the vLLM API on a fresh machine today, the most recently
validated `external/chatterbox` branch is `pre-vllm-api` (commit `d1e3d32`).
The `external/chatterbox` `master` branch was later rebuilt so it replays the
full `pre-vllm-api` file set (`8e7fb90`), but that replay was not revalidated
on this host because the GPU runtime went unhealthy (`cudaGetDeviceCount()`
error `804`) before the final smoke test.

Practical recommendation:

- use `pre-vllm-api` first when you need the last known-good vLLM API setup
- treat `master` as the branch we are aligning to that setup, but re-smoke-test
  it on the new machine before assuming parity

### 0. Sync the repo and set the Chatterbox branch

```bash
cd /path/to/ChatterBox_S3_Concurrency
git submodule update --init --recursive

cd external/chatterbox
git fetch origin
git switch pre-vllm-api
cd ../..
```

If you specifically want to test the replayed `master` branch instead, replace
the `git switch pre-vllm-api` line with `git switch master`.

### Prerequisites

- NVIDIA GPU (tested on RTX A6000 48GB)
- CUDA 12.x-class host driver / runtime
- Python 3.11
- `conda`

### 1. Create the environment

```bash
cd /path/to/ChatterBox_S3_Concurrency

# If `conda activate` is unavailable, initialize conda for your own installation first.

conda create -n chatterbox-vllm python=3.11 -y
conda activate chatterbox-vllm
python -m pip install -U pip uv
```

### 2. Install the runtime stack

```bash
export UV_TORCH_BACKEND=cu128
uv pip install vllm==0.17.1 --torch-backend=auto

python -m pip install \
  huggingface_hub safetensors librosa soundfile sentencepiece \
  conformer==0.3.2 diffusers==0.29.0 omegaconf s3tokenizer \
  fastapi uvicorn psutil

python -m pip install -e external/chatterbox --no-deps
```

### 3. Set runtime environment variables

```bash
export HF_TOKEN=your_huggingface_token
export PYTHONPATH=$PWD/external/chatterbox/src
export VLLM_WORKER_MULTIPROC_METHOD=spawn

export TORCH_LIB="$CONDA_PREFIX/lib/python3.11/site-packages/torch/lib"
if [ -d /usr/local/cuda/lib64 ]; then
  export LD_LIBRARY_PATH="/usr/local/cuda/lib64:$TORCH_LIB${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
else
  python -m pip install --no-cache-dir nvidia-cuda-runtime-cu12==12.4.127
  export CUDART12_DIR="$CONDA_PREFIX/lib/python3.11/site-packages/nvidia/cuda_runtime/lib"
  export LD_LIBRARY_PATH="$TORCH_LIB:$CUDART12_DIR${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
fi
```

### 4. Prepare local model artifacts

Use the local helper script instead of manually downloading files and exporting the model package:

```bash
python prepare_local_vllm_models.py --copy
```

By default this creates:

- `runs/models/chatterbox_base`
- `runs/models/chatterbox_turbo`
- `runs/models/t3_vllm_export`

The helper depends on `HF_TOKEN` and is the expected way to reproduce the local
artifact layout from scratch.

### 5. Optional preflight

```bash
python external/chatterbox/vllm_t3_preflight.py \
  --model-dir "$PWD/runs/models/t3_vllm_export" \
  --gpu-memory-utilization 0.5
```

### 6. Start the API

```bash
export MODEL_ROOT="$PWD/runs/models"

export CHECKPOINT_DIR="$MODEL_ROOT/chatterbox_base"
export BASE_CHECKPOINT_DIR="$MODEL_ROOT/chatterbox_base"
export TURBO_S3_CHECKPOINT_DIR="$MODEL_ROOT/chatterbox_turbo"
export VLLM_MODEL_DIR="$MODEL_ROOT/t3_vllm_export"
export VLLM_EXPORT_DIR="$MODEL_ROOT/t3_vllm_export"

export DEFAULT_AUDIO_PROMPT_PATH="$PWD/SPK_17_000003.wav"
export API_DEVICE=cuda
export API_PORT=8000

export VLLM_TP_SIZE=1
export VLLM_GPU_MEMORY_UTILIZATION=0.8
export VLLM_MAX_MODEL_LEN=2048
export VLLM_ENABLE_PREFIX_CACHING=false
export VLLM_ENFORCE_EAGER=false

python external/chatterbox/fastapi_vllm_tts_service.py
```

The service is ready when Uvicorn reports startup complete.

---

## Testing the API

In a new terminal:

```bash
cd /path/to/ChatterBox_S3_Concurrency
conda activate chatterbox-vllm
export PYTHONPATH=$PWD/external/chatterbox/src
```

### Health check

```bash
curl http://127.0.0.1:8000/health
```

### Single warmup request

```bash
curl -sS -o /tmp/vllm_warmup.wav \
  -X POST http://127.0.0.1:8000/v1/tts \
  -H "Content-Type: application/json" \
  -d '{
    "text":"صباح الخير. هذا طلب تهيئة أولي.",
    "language_id":"ar",
    "audio_prompt_path":"'"$PWD"'/SPK_17_000003.wav"
  }'
```

### Chunked streaming check

```bash
python external/chatterbox/stream_chunks_client.py \
  --url http://127.0.0.1:8000/v1/tts/stream_chunks \
  --language-id ar \
  --text "صباح الخير. هذا اختبار قصير للصوت." \
  --save-dir /tmp/chunks
```

### Concurrent load test

```bash
python external/chatterbox/stream_chunks_client.py \
  --url http://127.0.0.1:8000/v1/tts/stream_chunks \
  --language-id ar \
  --concurrency 8 \
  --num-requests 16 \
  --text "صباح الخير. هذا اختبار قصير للصوت." \
  --text "هل يبدو الصوت طبيعيًا عندما ينتقل من سؤال إلى جواب؟ هذا ما نريد التأكد منه." \
  --summary-json /tmp/tts_chunks_summary.json
```

### Preview chunk boundaries

```bash
curl -X POST http://127.0.0.1:8000/v1/tts/split_preview \
  -H "Content-Type: application/json" \
  -d '{"text":"صباح الخير. هذا اختبار قصير للصوت. هل يبدو الصوت طبيعيًا؟","language_id":"ar"}'
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Service health check |
| POST | `/v1/tts` | Synthesize full text, return WAV |
| POST | `/v1/tts/stream` | Synthesize full text, stream audio bytes |
| POST | `/v1/tts/meta` | Synthesize full text and return timing metadata |
| POST | `/v1/tts/stream_chunks` | Split + synthesize per chunk, stream NDJSON events |
| POST | `/v1/tts/split_preview` | Preview chunk boundaries without synthesis |
| GET | `/v1/tts/trace/recent` | Last N batch scheduler traces |

### Chunked streaming event format

Each line from `/v1/tts/stream_chunks` is a JSON object:

```json
{
  "event": "chunk",
  "request_id": "abc123",
  "chunk_index": 0,
  "text": "Hello, this is a test.",
  "audio_wav_b64": "<base64 WAV>",
  "sample_rate": 22050,
  "queue_wait_s": 0.002,
  "t3_s": 0.95,
  "s3_s": 0.56,
  "chunk_total_s": 1.52,
  "is_final": false
}
```

---

## Architecture

```
HTTP request
     │
     ▼
FastAPI service
     │
     ▼
Admission scheduler  ←── batches concurrent requests into cohorts
     │
     ▼
Text chunker  ←── splits text at sentence/clause/word boundaries
     │
     ▼
┌────────────────────────────────────┐
│  T3 (vLLM, batched across N reqs)  │  ← shared GPU decode step
│  text tokens → speech tokens       │
└────────────────────────────────────┘
     │  N independent token sequences
     ▼
┌────────────────────────────────────┐
│  S3 finalize (parallel, N streams) │  ← N CUDA streams simultaneously
│  speech tokens → mel → wav         │    token2mel (meanflow, 2-step ODE)
└────────────────────────────────────┘    HiFiGAN mel → waveform
     │  N waveforms
     ▼
NDJSON stream (one event per chunk per request)
```

---

## Configuration Reference

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `CHECKPOINT_DIR` | — | Base multilingual Chatterbox checkpoint directory |
| `BASE_CHECKPOINT_DIR` | — | Same as `CHECKPOINT_DIR`; keep both set for this service |
| `TURBO_S3_CHECKPOINT_DIR` | — | Turbo S3 checkpoint directory containing `s3gen_meanflow.safetensors` |
| `VLLM_MODEL_DIR` | — | Exported vLLM T3 package directory |
| `VLLM_EXPORT_DIR` | — | Export destination used if the service needs to export locally |
| `DEFAULT_AUDIO_PROMPT_PATH` | `SPK_17_000003.wav` | Default reference voice clip used when requests omit `audio_prompt_path` |
| `API_DEVICE` | `cuda` | Device used for the runtime |
| `API_PORT` | `8000` | FastAPI port |
| `VLLM_ENFORCE_EAGER` | `false` | Set `true` to disable CUDA graphs (slower but safer for debugging) |
| `VLLM_ENABLE_PREFIX_CACHING` | `false` | Must remain `false` — prefix caching is incompatible with embed-only prompts |
| `VLLM_GPU_MEMORY_UTILIZATION` | `0.5` | Fraction of VRAM reserved for the vLLM KV cache |
| `VLLM_MAX_MODEL_LEN` | `2048` | Maximum T3 sequence length |
| `VLLM_TP_SIZE` | `1` | Tensor parallel shards (multi-GPU) |
| `VLLM_PROMPT_BUILDER_DEVICE` | `cpu` | Device used for the non-vLLM prompt builder T3 pieces |
| `API_BATCH_WINDOW_MS` | `5.0` | Admission batching window for request grouping |
| `API_MAX_BATCH_SIZE` | `8` | Maximum requests per scheduler batch |
| `HF_TOKEN` | — | HuggingFace token for checkpoint download |

---

## Repository Layout

```
prepare_local_vllm_models.py      ← local helper: download base/turbo artifacts + export vLLM package

external/chatterbox/
  src/chatterbox/
    runtime/
      worker_vllm.py          ← vLLM worker: batched T3 decode + parallel S3 finalize
    models/
      t3/                     ← T3 transformer
      s3gen/                  ← S3 flow-matching vocoder (turbo meanflow)
    mtl_tts_vllm_turbo_s3.py  ← top-level TTS class
    vllm_t3_bridge.py         ← vLLM engine setup + T3 export
  fastapi_vllm_tts_service.py ← FastAPI service with scheduler + streaming
  stream_chunks_client.py     ← load test + streaming client

GPU_MIGRATION_SERVING_PLAN.md ← full serving runbook
CLOUD_GPU_QUICKSTART.md       ← cloud GPU quickstart
SERVING_HANDOFF_2026-04-03.md ← checkpoint paths, env vars, audit findings
```
