# Cloud GPU Quickstart

This guide covers two independent paths:

- **Path A (sections 1–18)**: baseline, streaming, scheduled, speculative, Medusa, Hydra benchmarks using the `chatterbox-s3` conda environment
- **Path B (sections 19–22)**: the production FastAPI TTS service using vLLM + turbo S3, using the `chatterbox-vllm` conda environment

For the full vLLM serving reference (all env vars, endpoints, troubleshooting), see:

- [GPU_MIGRATION_SERVING_PLAN.md](GPU_MIGRATION_SERVING_PLAN.md)

Reference for the current tensor/state flow:

- [CHATTERBOX_STATE_FLOW.md](/home/ubuntu/ChatterBox_S3_Concurrency/CHATTERBOX_STATE_FLOW.md)

## 1. If You Already Have An Old Cloud Checkout

Clean the existing `external/chatterbox` checkout first so it does not keep stale local patch state or the old upstream submodule URL.

```bash
git submodule deinit -f external/chatterbox
rm -rf .git/modules/external/chatterbox
rm -rf external/chatterbox
git pull
git submodule sync -- external/chatterbox
git submodule update --init external/chatterbox
```

## 2. Clone The Repo

If this is a fresh cloud box, use this instead:

```bash
export GITHUB_TOKEN=YOUR_GITHUB_TOKEN
git clone https://$GITHUB_TOKEN@github.com/hishambarakat16/ChatterBox_S3_Concurrency.git
cd ChatterBox_S3_Concurrency
git submodule sync -- external/chatterbox
git submodule update --init external/chatterbox
```

### If You Copied The Workspace From An Old Instance

Run this first:

```bash
rm -rf /workspace/.hf_home/hub/models--ResembleAI--chatterbox
find /workspace/.hf_home -name '*.incomplete' -delete
export HF_HOME=/workspace/.hf_home_fresh
mkdir -p "$HF_HOME"
```

## 3. Create The Python Environment

Use Python `3.11`.

If `conda` is not installed on the box yet, run this once first:

```bash
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh -b -p "$HOME/miniconda3"
eval "$("$HOME/miniconda3/bin/conda" shell.bash hook)"
conda init bash
```

```bash
conda create -y -n chatterbox-s3 python=3.11
conda activate chatterbox-s3
python -m pip install --upgrade pip wheel
python -m pip install "setuptools<81"
```

## 4. Install Chatterbox And Perth From Source

```bash
pip install -e external/chatterbox
pip uninstall -y resemble-perth
pip install --no-cache-dir git+https://github.com/resemble-ai/Perth.git
```

## 5. Sanity Check The Environment

```bash
python -c "import torch; print('torch', torch.__version__); print('cuda', torch.version.cuda); print('cuda_available', torch.cuda.is_available()); print('device_count', torch.cuda.device_count()); print('gpu', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'none')"
python -c "import perth; print(perth.PerthImplicitWatermarker)"
python -c "from chatterbox import ChatterboxMultilingualTTS, ChatterboxMultilingualStreamingTTS, ChatterboxMultilingualConcurrentTTS, ChatterboxMultilingualScheduledTTS; print('imports_ok')"
```

## 6. Pick A Prompt File

```bash
export PROMPT_AUDIO=$PWD/SPK_17_000003.wav
```

## 7. Show Original Out-Of-The-Box Chatterbox Single Request

This uses the original `ChatterboxMultilingualTTS` path through `mtl_tts.py`.
The harness here is only for timing and saving the output WAV.

```bash
PYTHONPATH=external/chatterbox/src python external/chatterbox/compare_multilingual_runtime.py \
  --impl baseline \
  --device cuda \
  --language-id ar \
  --audio-prompt-path "$PROMPT_AUDIO" \
  --text "مرحبا، هذا اختبار للبنية الحالية." \
  --warmup-runs 0 \
  --runs 1 \
  --output-wav original_baseline.wav
```

## 8. Show Original Out-Of-The-Box Chatterbox Shared-Instance Concurrency Failure

This still uses the original `baseline` path. On the tested `4060 Ti` setup, `concurrency=2`
historically failed or produced logically broken results here. This is the reference demo
for why the new scheduler work was needed.

```bash
PYTHONPATH=external/chatterbox/src python external/chatterbox/benchmark_multilingual_concurrency.py \
  --impl baseline \
  --device cuda \
  --language-id ar \
  --audio-prompt-path "$PROMPT_AUDIO" \
  --text "مرحبا، هذا اختبار للبنية الحالية." \
  --concurrency-levels 1 2
```

## 9. Run Streaming Concurrency Benchmark

```bash
PYTHONPATH=external/chatterbox/src python external/chatterbox/benchmark_multilingual_concurrency.py \
  --impl streaming \
  --device cuda \
  --language-id ar \
  --audio-prompt-path "$PROMPT_AUDIO" \
  --text "مرحبا، هذا اختبار للبنية الحالية." \
  --concurrency-levels 1 2
```

## 10. Run Concurrent T3 Benchmark

```bash
PYTHONPATH=external/chatterbox/src python external/chatterbox/benchmark_multilingual_concurrency.py \
  --impl concurrent \
  --device cuda \
  --language-id ar \
  --audio-prompt-path "$PROMPT_AUDIO" \
  --text "مرحبا، هذا اختبار للبنية الحالية." \
  --concurrency-levels 1 4 \
  --output-dir benchmark_wavs

```

Use `--trace-shapes` only when you are debugging a regression. It is not needed for normal benchmark runs anymore.

## 11. Run Scheduled T3 Benchmark

```bash
PYTHONPATH=external/chatterbox/src python external/chatterbox/benchmark_multilingual_concurrency.py \
  --impl scheduled \
  --device cuda \
  --language-id ar \
  --audio-prompt-path "$PROMPT_AUDIO" \
  --text "مرحبا، هذا اختبار للبنية الحالية." \
  --concurrency-levels 1 4 \
  --output-dir benchmark_wavs
```

The scheduled runtime now disables the alignment controller by default. Add
`--enable-alignment-controller` only if you explicitly want the old guarded behavior back.

## 12. Run Scheduled Trace Debug Benchmark

Use this only when you want to inspect scheduler batching behavior or debug a regression.

```bash
PYTHONPATH=external/chatterbox/src python external/chatterbox/benchmark_multilingual_concurrency.py \
  --impl scheduled \
  --device cuda \
  --language-id ar \
  --audio-prompt-path "$PROMPT_AUDIO" \
  --text "مرحبا، هذا اختبار للبنية الحالية." \
  --concurrency-levels 1 2 \
  --trace-shapes \
  --output-dir benchmark_wavs
```

Use `--trace-shapes` only when you are debugging a regression or verifying scheduler cohort behavior.
The default scheduled benchmark path also runs without the alignment controller unless you add
`--enable-alignment-controller`.

## 13. Run Speculative Draft Benchmark

This runs the first real separate-draft speculative prototype using a layer-subset multilingual `T3` draft.

```bash
PYTHONPATH=external/chatterbox/src python external/chatterbox/benchmark_t3_speculative_prototype.py \
  --device cuda \
  --language-id ar \
  --audio-prompt-path "$PROMPT_AUDIO" \
  --text "مرحبا، هذا اختبار للبنية الحالية." \
  --max-new-tokens 128 \
  --speculate-k 4 \
  --draft-mode layer_subset \
  --draft-layers 12 \
  --draft-layer-selection even \
  --warmup-runs 2 \
  --runs 6
```

If you also want rendered WAVs for listening:

```bash
PYTHONPATH=external/chatterbox/src python external/chatterbox/benchmark_t3_speculative_prototype.py \
  --device cuda \
  --language-id ar \
  --audio-prompt-path "$PROMPT_AUDIO" \
  --text "مرحبا، هذا اختبار للبنية الحالية." \
  --max-new-tokens 128 \
  --speculate-k 4 \
  --draft-mode layer_subset \
  --draft-layers 12 \
  --draft-layer-selection even \
  --warmup-runs 2 \
  --runs 6 \
  --output-dir benchmark_speculative
```

## 14. Build T3 Medusa Distill Datasets In Chunks

Use the chunked launcher when you want the builder process to restart every `N` manifest rows.
This is the safer path for long overnight runs because it works for both the original greedy teacher
and the newer scheduled builder path without keeping one giant process alive for the whole dataset.
The scheduled dataset builder disables the alignment controller by default so it stays closer to the
original greedy teacher policy; add `--enable-alignment-controller` only if you explicitly want the
scheduled runtime guard behavior in the teacher outputs.

Original greedy-teacher style build:

```bash
PYTHONPATH=external/chatterbox/src python external/chatterbox/run_t3_medusa_distill_in_chunks.py \
  --manifest-csv data/arabic_medusa_manifest_short_40000.csv \
  --audio-prompt-path "$PROMPT_AUDIO" \
  --language-id ar \
  --device cuda \
  --output-dir data/t3_medusa_distill_ar_short_40000_384_v5_greedy \
  --max-new-tokens 384 \
  --decode-impl greedy \
  --chunk-size 10000 \
  --mp-workers 3 \
  --resume-existing
```

Chunked scheduled build:

```bash
PYTHONPATH=external/chatterbox/src python external/chatterbox/run_t3_medusa_distill_in_chunks.py \
  --manifest-csv data/arabic_medusa_manifest_short_40000.csv \
  --audio-prompt-path "$PROMPT_AUDIO" \
  --language-id ar \
  --device cuda \
  --output-dir data/t3_medusa_distill_ar_short_40000_384_v6_scheduled \
  --max-new-tokens 384 \
  --decode-impl scheduled \
  --chunk-size 10000 \
  --mp-workers 3 \
  --scheduler-inflight 10 \
  --scheduler-batching-window-ms 10 \
  --resume-existing
```

## 15. Train T3 Medusa Heads

This trains a head-only Medusa adapter on top of the frozen multilingual `T3`.
The current best dataset family is the greedy-teacher `v5` build, and the current best
training shape is still `h2` training (`--medusa-heads 2`, `--medusa-layers 1`).

```bash
PYTHONPATH=external/chatterbox/src python external/chatterbox/train_t3_medusa.py \
  --dataset-dir data/t3_medusa_distill_ar_short_40000_384_v5_greedy \
  --output-dir runs/t3_medusa_ar_short_40k_v5_greedy_h2_run1 \
  --device cuda \
  --batch-size 8 \
  --epochs 5 \
  --lr 3e-4 \
  --medusa-heads 2 \
  --medusa-layers 1 \
  --save-every 200
```

Current best completed checkpoint:

- `runs/t3_medusa_ar_short_40k_v5_greedy_h2_run1/checkpoint_step_022910`
- `eval_loss = 3.0694`
- `eval_base_top1 = 0.6721`
- `eval_medusa_head_0_top1 = 0.4155`
- `eval_medusa_head_1_top1 = 0.2962`

## 16. Download The Published Medusa Checkpoint

The private Hugging Face model repo currently hosting this exact checkpoint is:

- `Hishambarakat/TTS_Optimization`

Use the same `HF_TOKEN` you use for private repo access, then download the checkpoint to a
local folder that can be passed directly as `--medusa-checkpoint-dir`:

```bash
export HF_TOKEN=YOUR_HF_TOKEN
export MEDUSA_CHECKPOINT_DIR=$PWD/models/t3_medusa_ar_short_40k_v5_greedy_h2_checkpoint_step_022910
mkdir -p "$MEDUSA_CHECKPOINT_DIR"
/home/ubuntu/miniconda3/envs/chatterbox-s3/bin/python - <<'PY'
import os
from huggingface_hub import snapshot_download
snapshot_download(
    repo_id='Hishambarakat/TTS_Optimization',
    repo_type='model',
    local_dir=os.environ['MEDUSA_CHECKPOINT_DIR'],
    local_dir_use_symlinks=False,
    token=os.environ['HF_TOKEN'],
    allow_patterns=['README.md', 't3_medusa_config.json', 't3_medusa_heads.safetensors'],
)
print(os.environ['MEDUSA_CHECKPOINT_DIR'])
PY
```

## 17. Run Medusa Speculative Benchmark

The current best serving tradeoff is to train with `h2` and infer with `--speculate-k 2`.
You can point `--medusa-checkpoint-dir` either at the local training checkpoint directory or at
`$MEDUSA_CHECKPOINT_DIR` from the download step above.

```bash
PYTHONPATH=external/chatterbox/src python external/chatterbox/benchmark_t3_speculative_prototype.py \
  --device cuda \
  --language-id ar \
  --audio-prompt-path "$PROMPT_AUDIO" \
  --text "مرحبا، هذا اختبار للبنية الحالية." \
  --max-new-tokens 128 \
  --speculate-k 2 \
  --draft-mode medusa \
  --medusa-checkpoint-dir "$MEDUSA_CHECKPOINT_DIR" \
  --warmup-runs 2 \
  --runs 6 \
  --output-dir benchmark_speculative_medusa_40k_v5_greedy_h2_k2
```

Current best benchmark result for that checkpoint:

- `speedup = 14.09%`
- `acceptance_rate = 0.7326`
- `exact_token_match = true`
- `rebuild_count = 0`

`--speculate-k 3` also works and preserves exact output, but it is currently a weaker tradeoff
for this checkpoint (`speedup = 11.92%`, `acceptance_rate = 0.4954`).

## 18. Send Back These Results

Send back:

- GPU model
- CUDA available output from step 5
- full terminal output from the original single-request baseline run
- full terminal output from the original shared-instance baseline concurrency run
- full terminal output from the streaming run
- full terminal output from the concurrent run
- full terminal output from the scheduled run
- full terminal output from the scheduled trace-debug run if you used it
- full terminal output from the speculative draft benchmark
- full terminal output from the Medusa training run if you used it
- full terminal output from the Medusa speculative benchmark if you used it
- full terminal output from the Hydra training run if you used it
- full terminal output from the Hydra speculative benchmark if you used it
- whether either run crashed or OOMed
- whether `concurrency=2` or `concurrency=4` failed
- whether any output was obviously truncated
- whether throughput improved meaningfully or correctness was restored without much scaling gain

## Troubleshooting

### `OSError: [Errno 116] Stale file handle` during `snapshot_download`

If you copied the workspace from an old instance, run:

```bash
rm -rf /workspace/.hf_home/hub/models--ResembleAI--chatterbox
find /workspace/.hf_home -name '*.incomplete' -delete
export HF_HOME=/workspace/.hf_home_fresh
mkdir -p "$HF_HOME"
```

Then rerun the command.

## Appendix A. Build The Hydra Dataset

Hydra dataset build is much faster than the original Medusa dataset build because it reuses the
existing teacher `speech_tokens` and only extracts teacher-forced planner hidden states.

```bash
PYTHONPATH=external/chatterbox/src python external/chatterbox/build_t3_hydra_distill_dataset.py \
  --source-dataset-dir data/t3_medusa_distill_ar_short_40000_384_v5_greedy \
  --output-dir data/t3_hydra_distill_ar_short_40000_v1 \
  --device cuda \
  --resume-existing \
  --save-every 200
```

## Appendix B. Train Hydra Heads

This is the first completed Hydra training run that currently leads Medusa on the single-request
planner benchmark.

```bash
PYTHONPATH=external/chatterbox/src python external/chatterbox/train_t3_hydra.py \
  --dataset-dir data/t3_hydra_distill_ar_short_40000_v1 \
  --output-dir runs/t3_hydra_ar_short_40k_h2_run1 \
  --device cuda \
  --batch-size 8 \
  --epochs 5 \
  --lr 3e-4 \
  --hydra-heads 2 \
  --hydra-layers 1 \
  --save-every 800
```

Current best completed Hydra checkpoint:

- `runs/t3_hydra_ar_short_40k_h2_run1/checkpoint_step_022910`
- `eval_loss = 2.2706`
- `eval_base_top1 = 0.6808`
- `eval_hydra_head_0_top1 = 0.4787`
- `eval_hydra_head_1_top1 = 0.3756`

Published Hydra checkpoint repo:

- `Hishambarakat/hydra-chatterbox-t3-enhancement`

## Appendix C. Run Hydra Speculative Benchmarks

Hydra is now the current best planner path in this repo.

Use the same `HF_TOKEN` you use for private repo access, then download the published checkpoint into a
local folder that can be passed directly as `--hydra-checkpoint-dir`:

```bash
export HF_TOKEN=YOUR_HF_TOKEN
export HYDRA_CHECKPOINT_DIR=$PWD/models/t3_hydra_ar_short_40k_h2_checkpoint_step_022910
mkdir -p "$HYDRA_CHECKPOINT_DIR"
/home/ubuntu/miniconda3/envs/chatterbox-s3/bin/python - <<'PY'
import os
from huggingface_hub import snapshot_download
snapshot_download(
    repo_id='Hishambarakat/hydra-chatterbox-t3-enhancement',
    repo_type='model',
    local_dir=os.environ['HYDRA_CHECKPOINT_DIR'],
    local_dir_use_symlinks=False,
    token=os.environ['HF_TOKEN'],
    allow_patterns=['README.md', 't3_hydra_config.json', 't3_hydra_heads.safetensors'],
)
print(os.environ['HYDRA_CHECKPOINT_DIR'])
PY
```

You can point `--hydra-checkpoint-dir` either at the local training checkpoint directory or at
`$HYDRA_CHECKPOINT_DIR` from the download step above.

Best current `k3` command:

```bash
PYTHONPATH=external/chatterbox/src python external/chatterbox/benchmark_t3_hydra_prototype.py \
  --device cuda \
  --language-id ar \
  --audio-prompt-path "$PROMPT_AUDIO" \
  --text "مرحبا، هذا اختبار للبنية الحالية." \
  --max-new-tokens 128 \
  --speculate-k 3 \
  --hydra-checkpoint-dir "$HYDRA_CHECKPOINT_DIR" \
  --warmup-runs 2 \
  --runs 6 \
  --output-dir benchmark_hydra_k3
```

Reference `k2` command:

```bash
PYTHONPATH=external/chatterbox/src python external/chatterbox/benchmark_t3_hydra_prototype.py \
  --device cuda \
  --language-id ar \
  --audio-prompt-path "$PROMPT_AUDIO" \
  --text "مرحبا، هذا اختبار للبنية الحالية." \
  --max-new-tokens 128 \
  --speculate-k 2 \
  --hydra-checkpoint-dir "$HYDRA_CHECKPOINT_DIR" \
  --warmup-runs 2 \
  --runs 6 \
  --output-dir benchmark_hydra_k2
```

Current Hydra benchmark results:

- `k2`:
  - `speedup = 18.88%`
  - `acceptance_rate = 0.7907`
  - `exact_token_match = true`
  - `rebuild_count = 0`
- `k3`:
  - `speedup = 24.34%`
  - `acceptance_rate = 0.6078`
  - `exact_token_match = true`
  - `rebuild_count = 0`

Current read:

- Hydra beats the current best Medusa benchmark on the single-request planner test
- Medusa best so far remains:
  - `speedup = 14.09%`
  - `acceptance_rate = 0.7326`
- Hydra `k3` is the current best overall speculative setting

---

## Path B — vLLM FastAPI Service

This is the production serving path. It replaces the HF T3 decode loop with vLLM batched
generation and uses the turbo S3 checkpoint (2-step meanflow CFM, ~5× faster than default).
S3 finalize runs in parallel across up to 4 CUDA streams after the batched T3 decode.

For the complete reference (all env vars, endpoint list, diagnostics, troubleshooting), see
[GPU_MIGRATION_SERVING_PLAN.md](GPU_MIGRATION_SERVING_PLAN.md).

## 19. Install The `chatterbox-vllm` Conda Environment

This is a separate env from `chatterbox-s3`. Do NOT reuse `chatterbox-s3` — vLLM requires
specific torch/cuda wheel versions that conflict with the chatterbox dependency stack.

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

The `--no-deps` editable install is critical. Plain `pip install -e external/chatterbox`
downgrades `torch`, `torchaudio`, `transformers`, and `pydantic` and breaks vLLM.

If you update the submodule or change any plugin entry point, re-run:

```bash
python -m pip install -e external/chatterbox --no-deps
```

## 20. Export The vLLM T3 Model Package

Run once per checkout (or after pulling new submodule code):

```bash
conda activate chatterbox-vllm
cd /home/ubuntu/ChatterBox_S3_Concurrency
export PYTHONPATH=$PWD/external/chatterbox/src
export LD_LIBRARY_PATH=/usr/local/cuda/lib64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}

python external/chatterbox/export_vllm_t3_model.py \
  --base-checkpoint-dir ~/.cache/huggingface/hub/models--ResembleAI--chatterbox/snapshots/05e904af2b5c7f8e482687a9d7336c5c824467d9 \
  --output-dir runs/t3_vllm_export
```

Fallback if the HF cache path does not exist on this box:

```bash
python external/chatterbox/export_vllm_t3_model.py \
  --from-pretrained \
  --output-dir runs/t3_vllm_export
```

Verify the export worked:

```bash
python external/chatterbox/vllm_t3_preflight.py \
  --model-dir runs/t3_vllm_export \
  --gpu-memory-utilization 0.5
```

## 21. Start The FastAPI Service

```bash
conda activate chatterbox-vllm
cd /home/ubuntu/ChatterBox_S3_Concurrency

export HF_TOKEN=hf_your_token_here
export LD_LIBRARY_PATH=/usr/local/cuda/lib64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
export VLLM_WORKER_MULTIPROC_METHOD=spawn
export PYTHONPATH=$PWD/external/chatterbox/src

# Model paths
export VLLM_MODEL_DIR=$PWD/runs/t3_vllm_export
export TURBO_S3_CHECKPOINT_DIR=~/.cache/huggingface/hub/models--ResembleAI--chatterbox-turbo/snapshots/749d1c1a46eb10492095d68fbcf55691ccf137cd
export DEFAULT_AUDIO_PROMPT_PATH=$PWD/SPK_17_000003.wav

# vLLM tuning — safe production defaults
export VLLM_GPU_MEMORY_UTILIZATION=0.5   # 50% VRAM for KV cache; leaves room for S3 activations
export VLLM_MAX_MODEL_LEN=2048
export VLLM_ENFORCE_EAGER=false          # CUDA graphs: ~47% first_chunk_s reduction
export VLLM_ENABLE_PREFIX_CACHING=false  # Must stay false — incompatible with embed-only prompts

# Batching
export API_BATCH_WINDOW_MS=5
export API_MAX_BATCH_SIZE=8

python external/chatterbox/fastapi_vllm_tts_service.py
```

The service binds on `0.0.0.0:8000` by default. Override with `API_HOST` and `API_PORT`.

Ctrl+C triggers graceful drain → engine close (15s) → force-kill any surviving vLLM EngineCore
child processes so VRAM is released cleanly.

Health check after startup:

```bash
curl -sS http://127.0.0.1:8000/health
```

Inspect the current S3 shape metadata after startup:

```bash
curl -sS -H 'Content-Type: application/json' \
  -d '{"text":"صباح الخير. هذا اختبار قصير للصوت.","language_id":"ar","auto_max_new_tokens":true,"auto_max_new_tokens_cap":128}' \
  http://127.0.0.1:8000/v1/tts/meta | jq '.profile._trace.stage_meta'
```

Inspect recent scheduler traces:

```bash
curl -sS http://127.0.0.1:8000/v1/tts/trace/recent?limit=5 | jq '.batches'
```

Use the `s3_token2mel_*` and `s3_hift_*` fields for bucket design. Do not size buckets from raw text length alone; the real token-to-mel axis is what matters for TRT planning.

## 22. Test The Service With `stream_chunks_client.py`

The `stream_chunks` endpoint is the primary production endpoint. It splits text into short
phrases, synthesises each in batches, and streams each WAV chunk as it finishes — giving
the lowest possible first-audio latency.

Single request:

```bash
python external/chatterbox/stream_chunks_client.py \
  --url http://127.0.0.1:8000/v1/tts/stream_chunks \
  --concurrency 1 \
  --text "صباح الخير. هذا اختبار قصير للصوت."
```

Concurrency-4 load test with saved output and JSON summary:

```bash
python external/chatterbox/stream_chunks_client.py \
  --url http://127.0.0.1:8000/v1/tts/stream_chunks \
  --concurrency 4 \
  --num-requests 8 \
  --text "صباح الخير. هذا اختبار قصير للصوت. أريد أن أسمع بداية الجملة ونهايتها بوضوح." \
  --text "هل يبدو الصوت طبيعيًا عندما ينتقل من سؤال إلى جواب؟ هذا ما نريد التأكد منه الآن." \
  --text "إذا كانت الجودة جيدة والزمن معقولًا، فسنكمل على تحسين الأداء تحت الضغط." \
  --save-dir /tmp/tts_audit \
  --summary-json /tmp/tts_audit/summary.json
```

Expected healthy summary numbers (c=4, N=8, on A6000):

| Metric | Target |
|---|---|
| `first_chunk_s (client mean)` | `< 2.5s` |
| `s3_finalize_wait_s (mean)` | `< 0.01s` |
| `chunk_t3_active_s (mean)` | `0.7 – 1.5s` |
| `s3_token2mel_s (mean)` | `0.8 – 1.2s` (2-step meanflow) |
| `s3_hift_s (mean)` | `0.3 – 0.6s` |
| `RTF (mean)` | `< 1.5×` for first wave |

If `s3_finalize_wait_s` is large (> 0.1s), the S3 parallel finalize is not active — check
that you are on the latest submodule commit and that `worker_vllm.py` uses `ThreadPoolExecutor`.

If `first_chunk_s` is > 5s for the first wave, check that `VLLM_ENFORCE_EAGER=false`
(CUDA graphs) and that the service has already completed its first warmup batch.
