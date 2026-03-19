# GPU MIGRATION SERVING PLAN

_Last updated: 2026-03-19_

## Rules

- this `vLLM` spike is Hydra-free
- use the base multilingual `T3` weights, not Hydra heads
- do not use `--hydra-checkpoint-dir`
- keep `--cfg-weight 0`
- run these commands on the GPU server, not on the local edit machine
- if preflight fails, read [VLLM_ENV_INCIDENT.md](/home/ubuntu/ChatterBox_S3_Concurrency/VLLM_ENV_INCIDENT.md) before changing packages or rebuilding the env
- the most likely base checkpoint dir on Thunder is:
  `~/.cache/huggingface/hub/models--ResembleAI--chatterbox/snapshots/05e904af2b5c7f8e482687a9d7336c5c824467d9`

## 1. Create The `vLLM` Environment

Recommended clean env:

```bash
conda create -n chatterbox-vllm python=3.11 -y
conda activate chatterbox-vllm
python -m pip install -U pip uv
export UV_TORCH_BACKEND=cu128
uv pip install vllm --torch-backend=auto
python -m pip install huggingface_hub safetensors librosa soundfile sentencepiece
python -m pip install -e external/chatterbox --no-deps
python -m pip install conformer==0.3.2 diffusers==0.29.0 omegaconf s3tokenizer
export LD_LIBRARY_PATH=/usr/local/cuda/lib64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
export VLLM_WORKER_MULTIPROC_METHOD=spawn
export PYTHONPATH=$PWD/external/chatterbox/src
```

Do not do this in the `chatterbox-vllm` env:

```bash
pip install -e external/chatterbox
```

Use this instead:

```bash
python -m pip install -e external/chatterbox --no-deps
```

Plain editable install downgrades `torch`, `torchaudio`, `transformers`, `tokenizers`, and `pydantic` and breaks `vLLM`.
The `--no-deps` editable install is the safe path here because it exposes the local `chatterbox` package and
its `vLLM` plugin entry point without pulling the pinned Chatterbox dependency stack into the env.
If you pull new code that changes the plugin entry point, rerun:

```bash
python -m pip install -e external/chatterbox --no-deps
```

Required additive runtime deps for `vllm_turbo_s3`:

- `conformer==0.3.2`
- `diffusers==0.29.0`
- `omegaconf`
- `s3tokenizer`

Usually not required for Arabic:

- `pykakasi` only matters for Japanese text normalization
- `spacy-pkuseg` only matters for Chinese segmentation
- `perth` is now optional and falls back to a passthrough watermarker if missing
- `torchcodec` is not required for the benchmark/save flow on current code because WAV outputs are written through `soundfile`
  - do not add `torchcodec` unless you intentionally move the workflow back to `torchaudio.save()`

## 2. Pull Latest Code

```bash
git pull
git submodule sync -- external/chatterbox
git submodule update --init external/chatterbox
```

## 3. Export The `vLLM` Model Package

Recommended if the base multilingual checkpoint is already cached on the server:

```bash
PYTHONPATH=external/chatterbox/src python external/chatterbox/export_vllm_t3_model.py \
  --base-checkpoint-dir ~/.cache/huggingface/hub/models--ResembleAI--chatterbox/snapshots/05e904af2b5c7f8e482687a9d7336c5c824467d9 \
  --output-dir runs/t3_vllm_export
```

Fallback if that cache path does not exist:

```bash
PYTHONPATH=external/chatterbox/src python external/chatterbox/export_vllm_t3_model.py \
  --from-pretrained \
  --output-dir runs/t3_vllm_export
```

Important:

- a Hydra run dir that only contains `t3_hydra_heads.safetensors` is not a valid base `T3` checkpoint for `vLLM`
- `vLLM` needs the base multilingual `T3` weights file `t3_mtl23ls_v2.safetensors`
- older examples used `runs/t3_hydra_*` only as folder names; that was historical naming, not Hydra runtime usage

## 4. Preflight

```bash
PYTHONPATH=external/chatterbox/src python external/chatterbox/vllm_t3_preflight.py \
  --model-dir runs/t3_vllm_export \
  --gpu-memory-utilization 0.85
```

Expected direction:

- if this says `No module named 'vllm'`, your active env is wrong or `vllm` is not installed yet
- if this says `libcudart.so.12`, first export `LD_LIBRARY_PATH=/usr/local/cuda/lib64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}` and retry
- if this says Thunder does not support `fork()`, export `VLLM_WORKER_MULTIPROC_METHOD=spawn` and retry
- if this says `Model architectures ['ChatterboxT3ForCausalLM'] are not supported for now`, the local `chatterbox` package is not installed into the env with `--no-deps`, so the spawned vLLM worker did not load the custom model plugin

## 5. Single-Request Check

```bash
PYTHONPATH=external/chatterbox/src python external/chatterbox/compare_multilingual_runtime.py \
  --impl vllm_turbo_s3 \
  --device cuda \
  --language-id ar \
  --audio-prompt-path "$PROMPT_AUDIO" \
  --text "مرحبا، هذا اختبار لمسار vllm الجديد." \
  --vllm-model-dir runs/t3_vllm_export \
  --vllm-gpu-memory-utilization 0.5 \
  --vllm-max-model-len 2048 \
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
  --vllm-model-dir runs/t3_vllm_export \
  --vllm-gpu-memory-utilization 0.5 \
  --vllm-max-model-len 2048 \
  --cfg-weight 0 \
  --temperature 0 \
  --max-new-tokens 128 \
  --concurrency-levels 1 2 4 8
```

Important:

- for `vllm_turbo_s3`, this benchmark should use one batched offline `generate(...)` call per concurrency level, not multiple Python threads each calling `generate()` on the same `LLM`
- that is the correct shape for the offline `vLLM` API
- a staggered real-service simulation is a different problem and likely needs `AsyncLLMEngine` or an explicit admission queue around a shared engine
- inspect the stop diagnostics in the benchmark output:
  - `stage_t3_finish_reason_length_mean > 0` means some rows hit the token cap instead of stopping cleanly
  - `stage_t3_tail_trimmed_mean > 0` means the fallback repetitive-tail trim activated on length-capped rows
- current quality caveat:
  - the present `vLLM` spike does not yet replicate the original multilingual alignment-based EOS controller
  - that means throughput can look excellent while some saved WAVs still show lingering noisy tails
  - the current code only adds diagnostics plus a conservative repetitive-tail trim for length-capped rows; this is mitigation, not full parity
  - confirmed current constraint:
    - `vllm_turbo_s3` should run with prefix caching disabled by default
    - with prefix caching enabled, the strongest bad-case pattern was batch-position-specific:
      - row `0` emitted a real stop token and sounded correct
      - rows `1..N` often hit `max_new_tokens` exactly and produced the lingering tail
    - with prefix caching disabled, the same `c16` batch produced:
      - `stage_t3_finish_reason_stop_mean=1.0`
      - `stage_t3_finish_reason_length_mean=0.0`
      - `stage_t3_output_has_stop_token_mean=1.0`
  - because the bad tails disappear, `audio_seconds_total` also drops
    - that is expected and is a quality win, not a regression

Prefix-caching A/B for the batch-stop issue:

```bash
PYTHONPATH=external/chatterbox/src python external/chatterbox/benchmark_multilingual_concurrency.py \
  --impl vllm_turbo_s3 \
  --device cuda \
  --language-id ar \
  --audio-prompt-path "$PROMPT_AUDIO" \
  --text "مرحبا، هذا اختبار لمسار vllm الجديد." \
  --vllm-model-dir runs/t3_vllm_export \
  --vllm-gpu-memory-utilization 0.5 \
  --vllm-max-model-len 2048 \
  --no-vllm-prefix-caching \
  --cfg-weight 0 \
  --temperature 0 \
  --max-new-tokens 128 \
  --concurrency-levels 16 \
  --output-dir benchmark_vllm_c16_no_prefix_cache
```

Interpretation:

- this experiment is now effectively resolved for the current spike:
  - the custom prompt-embed `T3` path is not safe with prefix caching enabled
  - keep prefix caching disabled unless you are explicitly re-testing this interaction
- the remaining quality gap after that is deeper stop-control parity with the original alignment-based EOS controller

## 7. Mixed-Traffic Simulator

Important:

- for `vllm_turbo_s3`, the mixed-traffic simulator must also use admission-batched `generate_many_with_sessions(...)`
- older threaded simulator behavior called `generate_with_session(...)` concurrently on the same offline `vLLM` engine and could crash with a CUDA device-side assert
- current code batches queued arrivals into cohorts using the simulator's batching window and text-bucket settings
- keep prefix caching disabled for this path as well
- current mixed-shape prompt-embed traffic is not yet stable on the compiled / CUDA-graph `vLLM` path
- for the simulator, use eager mode unless you are explicitly re-testing the compiled path

```bash
PYTHONPATH=external/chatterbox/src python external/chatterbox/simulate_streaming_service.py \
  --impl vllm_turbo_s3 \
  --device cuda \
  --language-id ar \
  --audio-prompt-path "$PROMPT_AUDIO" \
  --vllm-model-dir runs/t3_vllm_export \
  --vllm-gpu-memory-utilization 0.5 \
  --vllm-max-model-len 2048 \
  --vllm-enforce-eager \
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
python -m pip install -e external/chatterbox --no-deps
python -m pip install conformer==0.3.2 diffusers==0.29.0 omegaconf s3tokenizer
export LD_LIBRARY_PATH=/usr/local/cuda/lib64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
export VLLM_WORKER_MULTIPROC_METHOD=spawn
export PYTHONPATH=$PWD/external/chatterbox/src
```

`No module named 'conformer'`

```bash
conda activate chatterbox-vllm
python -m pip install conformer==0.3.2 diffusers==0.29.0 omegaconf s3tokenizer
export PYTHONPATH=$PWD/external/chatterbox/src
```

`TorchCodec is required for save_with_torchcodec`

- pull latest code first
- current benchmark and simulator save WAVs through `soundfile`, not `torchaudio.save()`
- no extra package should be needed if you are on the latest repo state
- avoid installing `torchcodec` into the working `vLLM` env unless you have a separate reason to depend on the torchaudio codec path

`No module named 'chatterbox.vllm_plugin'`

```bash
git pull
git submodule sync -- external/chatterbox
git submodule update --init external/chatterbox
conda activate chatterbox-vllm
python -m pip install -e external/chatterbox --no-deps
export PYTHONPATH=$PWD/external/chatterbox/src
```

`Received a Hydra-head checkpoint directory`

- you pointed at a Hydra-only run dir
- pass the base multilingual checkpoint dir instead
- on Thunder, that is most likely:
  `~/.cache/huggingface/hub/models--ResembleAI--chatterbox/snapshots/05e904af2b5c7f8e482687a9d7336c5c824467d9`

`GPU memory looks "full" or benchmark appears frozen after concurrency 1`

- `vLLM` reserves KV cache aggressively based on `--vllm-gpu-memory-utilization`
- older commands used `0.9`, which can reserve almost the whole A6000 and look like a leak
- use `--vllm-gpu-memory-utilization 0.5` and `--vllm-max-model-len 2048` for this spike
- the single-request path already works; if this still stalls after lowering both values, the next suspect is the threaded benchmark pattern rather than raw model loading

`Only the first row in a batched run sounds right; later rows linger`

- check the benchmark diagnostics first
- if you see something like:
  - `stage_t3_finish_reason_stop_mean ~= 0.0625`
  - `stage_t3_finish_reason_length_mean ~= 0.9375`
  - `stage_t3_generated_tokens=[89,128,128,...]`
- that means row `0` stopped naturally and later rows length-capped
- for the current spike, treat that as a prefix-caching incompatibility and keep prefix caching disabled
- if the problem persists even with prefix caching disabled, the remaining gap is the missing alignment-based EOS controller in the `vLLM` path

`torch.AcceleratorError: CUDA error: device-side assert triggered` in mixed-traffic simulation

- if this happens after one or a few successful `vllm_turbo_s3` requests, check the printed runtime flags first
- for the current spike, the safe simulator settings are:
  - `vllm_enable_prefix_caching=False`
  - `vllm_enforce_eager=True`
- current local read:
  - prefix caching was one separate incompatibility
  - after that was fixed, the mixed-shape service simulator still showed compiled-path instability
  - the current safe path is admission-batched cohorts plus eager mode

`vLLM` command still using Hydra flags

- remove `--hydra-checkpoint-dir`
- keep `--cfg-weight 0`

## Supporting Docs

- [t3_engine_migration_memo.md](/Users/hisham/Code/Bahraini_TTS/architecture/t3_engine_migration_memo.md)
- [t3_serving_stack_layering_memo.md](/Users/hisham/Code/Bahraini_TTS/architecture/t3_serving_stack_layering_memo.md)
- [t3_mixed_traffic_scheduler_research_memo.md](/Users/hisham/Code/Bahraini_TTS/architecture/t3_mixed_traffic_scheduler_research_memo.md)
