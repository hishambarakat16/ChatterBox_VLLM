# GPU MIGRATION SERVING PLAN

_Last updated: 2026-03-19_

## Rules

- this `vLLM` spike is Hydra-free
- do not use `--hydra-checkpoint-dir`
- keep `--cfg-weight 0`
- run these commands on the GPU server, not on the local edit machine

## 1. Create The `vLLM` Environment

Recommended clean env:

```bash
conda create -n chatterbox-vllm python=3.11 -y
conda activate chatterbox-vllm
python -m pip install -U pip uv
export UV_TORCH_BACKEND=cu128
uv pip install vllm --torch-backend=auto
python -m pip install huggingface_hub safetensors librosa soundfile sentencepiece
export PYTHONPATH=$PWD/external/chatterbox/src
```

Do not do this in the `chatterbox-vllm` env:

```bash
pip install -e external/chatterbox
```

That downgrades `torch`, `torchaudio`, `transformers`, `tokenizers`, and `pydantic` and breaks `vLLM`.

## 2. Pull Latest Code

```bash
git pull
git submodule sync -- external/chatterbox
git submodule update --init external/chatterbox
```

## 3. Export The `vLLM` Model Package

If you do not have a local base multilingual `T3` checkpoint dir, use pretrained fallback:

```bash
PYTHONPATH=external/chatterbox/src python external/chatterbox/export_vllm_t3_model.py \
  --from-pretrained \
  --output-dir runs/t3_hydra_ar_short_40k_h2_run1/vllm_t3_export
```

If you do have the base multilingual checkpoint locally:

```bash
PYTHONPATH=external/chatterbox/src python external/chatterbox/export_vllm_t3_model.py \
  --base-checkpoint-dir /path/to/base_multilingual_chatterbox_ckpt \
  --output-dir runs/t3_hydra_ar_short_40k_h2_run1/vllm_t3_export
```

Important:

- a Hydra run dir that only contains `t3_hydra_heads.safetensors` is not a valid base `T3` checkpoint for `vLLM`
- `vLLM` needs the base multilingual `T3` weights file `t3_mtl23ls_v2.safetensors`

## 4. Preflight

```bash
PYTHONPATH=external/chatterbox/src python external/chatterbox/vllm_t3_preflight.py \
  --model-dir runs/t3_hydra_ar_short_40k_h2_run1/vllm_t3_export \
  --gpu-memory-utilization 0.85
```

Expected direction:

- if this says `No module named 'vllm'`, your active env is wrong or `vllm` is not installed yet
- if this says `libcudart.so.12`, your env pulled the wrong CUDA stack; recreate it and use `UV_TORCH_BACKEND=cu128`

## 5. Single-Request Check

```bash
PYTHONPATH=external/chatterbox/src python external/chatterbox/compare_multilingual_runtime.py \
  --impl vllm_turbo_s3 \
  --device cuda \
  --language-id ar \
  --audio-prompt-path "$PROMPT_AUDIO" \
  --text "مرحبا، هذا اختبار لمسار vllm الجديد." \
  --vllm-model-dir runs/t3_hydra_ar_short_40k_h2_run1/vllm_t3_export \
  --cfg-weight 0 \
  --temperature 0 \
  --max-new-tokens 128
```

## 6. Concurrency Benchmark

```bash
PYTHONPATH=external/chatterbox/src python external/chatterbox/benchmark_multilingual_concurrency.py \
  --impl vllm_turbo_s3 \
  --device cuda \
  --language-id ar \
  --audio-prompt-path "$PROMPT_AUDIO" \
  --text "مرحبا، هذا اختبار لمسار vllm الجديد." \
  --vllm-model-dir runs/t3_hydra_ar_short_40k_h2_run1/vllm_t3_export \
  --cfg-weight 0 \
  --temperature 0 \
  --max-new-tokens 128 \
  --concurrency-levels 1 2 4 8
```

## 7. Mixed-Traffic Simulator

```bash
PYTHONPATH=external/chatterbox/src python external/chatterbox/simulate_streaming_service.py \
  --impl vllm_turbo_s3 \
  --device cuda \
  --language-id ar \
  --audio-prompt-path "$PROMPT_AUDIO" \
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

## Common Failures

`No module named 'vllm'`

```bash
conda activate chatterbox-vllm
python -m pip install -U pip uv
export UV_TORCH_BACKEND=cu128
uv pip install vllm --torch-backend=auto
export PYTHONPATH=$PWD/external/chatterbox/src
```

`libcudart.so.12: cannot open shared object file`

```bash
conda deactivate
conda remove -n chatterbox-vllm --all -y
conda create -n chatterbox-vllm python=3.11 -y
conda activate chatterbox-vllm
python -m pip install -U pip uv
export UV_TORCH_BACKEND=cu128
uv pip install vllm --torch-backend=auto
python -m pip install huggingface_hub safetensors librosa soundfile sentencepiece
export PYTHONPATH=$PWD/external/chatterbox/src
```

`Received a Hydra-head checkpoint directory`

- you pointed at a Hydra-only run dir
- rerun export with `--from-pretrained`
- or pass `--base-checkpoint-dir /path/to/base_multilingual_chatterbox_ckpt`

`vLLM` command still using Hydra flags

- remove `--hydra-checkpoint-dir`
- keep `--cfg-weight 0`

## Supporting Docs

- [t3_engine_migration_memo.md](/Users/hisham/Code/Bahraini_TTS/architecture/t3_engine_migration_memo.md)
- [t3_serving_stack_layering_memo.md](/Users/hisham/Code/Bahraini_TTS/architecture/t3_serving_stack_layering_memo.md)
- [t3_mixed_traffic_scheduler_research_memo.md](/Users/hisham/Code/Bahraini_TTS/architecture/t3_mixed_traffic_scheduler_research_memo.md)
