# GPU MIGRATION SERVING PLAN

_Last updated: 2026-03-26_

## Rules

- this `vLLM` spike is Hydra-free
- use the base multilingual `T3` weights, not Hydra heads
- do not use `--hydra-checkpoint-dir`
- **CFG is now implemented natively inside vLLM** — `--cfg-weight 0.5` (or any positive value) is now safe to use; the old "keep `--cfg-weight 0`" rule no longer applies
- run these commands on the GPU server, not on the local edit machine
- current branch no longer feeds full external `prompt_embeds` into `vLLM`
- current branch sends token ids plus conditioning tensors and lets the served custom model rebuild the `T3` prompt internally
- `vllm_turbo_s3` now applies CFG, EOS suppression, and token-repetition detection inside vLLM via `T3CFGLogitsProcessor` — the old HF replay pass is no longer needed and is not called
- if preflight fails, read [VLLM_ENV_INCIDENT.md](/home/ubuntu/ChatterBox_S3_Concurrency/VLLM_ENV_INCIDENT.md) before changing packages or rebuilding the env
- the most likely base checkpoint dir on Thunder is:
  `~/.cache/huggingface/hub/models--ResembleAI--chatterbox/snapshots/05e904af2b5c7f8e482687a9d7336c5c824467d9`

## 0. Per-Shell Bootstrap (Do This Every New Terminal)

```bash
conda activate chatterbox-vllm
export LD_LIBRARY_PATH=/usr/local/cuda/lib64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
export VLLM_WORKER_MULTIPROC_METHOD=spawn
export PYTHONPATH=$PWD/external/chatterbox/src
```

Why this is mandatory:

- new shells do not keep prior exports
- if `LD_LIBRARY_PATH` is missing, `vLLM` fails with `ImportError: libcudart.so.12: cannot open shared object file`
- if `VLLM_WORKER_MULTIPROC_METHOD` is missing on Thunder, worker startup can fail on `fork()`

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
- current export also writes a lightweight tokenizer package because the served model now enters through token ids plus multimodal conditioning, not external `prompt_embeds`

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
- if this says `Error in inspecting model architecture 'ChatterboxT3ForCausalLM'` right after the internal-prompt migration:
  - check the traceback for `MultiModalEmbeddings`
  - on the deployed `vLLM 0.17.1` line, `MultiModalEmbeddings` must be imported from `vllm.model_executor.models.interfaces`, not `vllm.multimodal.inputs`
  - current code has already been updated for that mismatch; pull latest code before debugging deeper runtime issues

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
  --repetition-penalty 1.0 \
  --max-new-tokens 128
```

Current safest rerun shape after the internal-prompt debugging pass:

```bash
conda activate chatterbox-vllm
export HF_TOKEN=...
export LD_LIBRARY_PATH=/usr/local/cuda/lib64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
export VLLM_WORKER_MULTIPROC_METHOD=spawn
cd /home/ubuntu/ChatterBox_S3_Concurrency

PYTHONPATH=external/chatterbox/src \
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

Why this exact shape:

- `--no-vllm-prefix-caching` stays on because prefix caching previously caused batch-row-specific stop failures on this path
- `--vllm-enforce-eager` stays on because mixed-shape traffic is not yet stable on the compiled / CUDA-graph path
- `--repetition-penalty 1.0` is important on this internal-prompt `vLLM` path because the default penalty kernels are not safe with the mixed prompt-token id space
- the repo now defaults `vllm_turbo_s3` to `repetition_penalty=1.0`, but keeping it explicit in bring-up commands is still the safest choice
- if you intentionally raise repetition penalty above `1.0`, expect the old sampler crash to reappear unless that kernel-level incompatibility is fixed

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
  --repetition-penalty 1.0 \
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
- current quality status:
  - CFG, EOS suppression, and token-repetition detection are now all applied inside vLLM via `T3CFGLogitsProcessor`
  - the old HF replay pass is eliminated — `vllm_turbo_s3` no longer has an O(N) serial post-generation stage
  - still missing vs the original `AlignmentStreamAnalyzer` (requires attention maps not exposed by vLLM's optimized kernels):
    - false-start suppression
    - long-tail / alignment-repetition detection
  - for N concurrent requests, expected behavior: `T_vllm(2N) ≈ T_vllm(N)` because vLLM shares weight loads across all 2N sequences
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
  --repetition-penalty 1.0 \
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
- current code batches queued arrivals into cohorts using the simulator's batching window and a `vLLM`-oriented grouping policy
- keep prefix caching disabled for this path as well
- current mixed-shape prompt-embed traffic is not yet stable on the compiled / CUDA-graph `vLLM` path
- for the simulator, use eager mode unless you are explicitly re-testing the compiled path
- current simulator default for `vllm_turbo_s3`:
  - group by prompt length only
  - prefer the largest ready cohort
  - do not force exact text-length singleton buckets unless you explicitly opt back into that older behavior
- previous bucket/recycle workaround:
  - fixed a narrow singleton repro
  - failed under realistic staggered mixed-text traffic
  - has been removed from the codebase rather than left as stale mitigation
- current architectural direction:
  - worker sends token ids plus conditioning tensors
  - served `ChatterboxT3ForCausalLM` reconstructs the `T3` prompt internally
  - the next job is to revalidate the simulator on this cleaner boundary

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
  --repetition-penalty 1.0 \
  --max-new-tokens 128 \
  --concurrency-levels 1 2 4 8 \
  --rounds-per-level 2 \
  --stagger-ms 250 \
  --save-mode representative \
  --output-dir streaming_service_sim_vllm
```

Benchmark-vs-simulator comparison points for `vllm_turbo_s3`:

- the working benchmark path in [benchmark_multilingual_concurrency.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/benchmark_multilingual_concurrency.py) sends one call shaped like:
  - `generate_many_with_sessions(sessions, [text] * concurrency, ...)`
- the simulator path in [simulate_streaming_service.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/simulate_streaming_service.py) is intentionally different:
  - it can stagger arrivals
  - it can rotate through different sentences
  - it can group ready arrivals into cohorts before calling `generate_many_with_sessions(...)`
- if you want to make the simulator look much closer to the benchmark for diagnosis, run it with a fixed text:

```bash
PYTHONPATH=external/chatterbox/src python external/chatterbox/simulate_streaming_service.py \
  --impl vllm_turbo_s3 \
  --device cuda \
  --language-id ar \
  --audio-prompt-path "$PROMPT_AUDIO" \
  --fixed-text "مرحبا، هذا اختبار لمسار vllm الجديد." \
  --vllm-model-dir runs/t3_vllm_export \
  --vllm-gpu-memory-utilization 0.5 \
  --vllm-max-model-len 2048 \
  --no-vllm-prefix-caching \
  --vllm-enforce-eager \
  --concurrency-levels 8 \
  --rounds-per-level 2 \
  --stagger-ms 250 \
  --save-mode representative \
  --output-dir streaming_service_sim_vllm_fixed_text
```

Input-path diagnosis commands:

Note:

- the diagnostic script name is still `diagnose_vllm_prompt_embeds.py` for continuity, but it now inspects the internal `T3` prompt/input path rather than replaying raw external `prompt_embeds`

- inspect the real `T3` prompt/input contract without calling `vLLM.generate(...)`:

```bash
PYTHONPATH=external/chatterbox/src python external/chatterbox/diagnose_vllm_prompt_embeds.py \
  --mode inspect \
  --device cuda \
  --language-id ar \
  --audio-prompt-path "$PROMPT_AUDIO" \
  --texts-file external/chatterbox/arabic_streaming_sentences.txt \
  --text-limit 8 \
  --vllm-model-dir runs/t3_vllm_export \
  --vllm-gpu-memory-utilization 0.5 \
  --vllm-max-model-len 2048 \
  --no-vllm-prefix-caching \
  --vllm-enforce-eager \
  --output-json prompt_embed_inspect.json
```

- test whether singleton requests with changing prompt sequence shapes kill a reused engine:

```bash
PYTHONPATH=external/chatterbox/src python external/chatterbox/diagnose_vllm_prompt_embeds.py \
  --mode sequential_singletons \
  --device cuda \
  --language-id ar \
  --audio-prompt-path "$PROMPT_AUDIO" \
  --texts-file external/chatterbox/arabic_streaming_sentences.txt \
  --text-limit 8 \
  --vllm-model-dir runs/t3_vllm_export \
  --vllm-gpu-memory-utilization 0.5 \
  --vllm-max-model-len 2048 \
  --no-vllm-prefix-caching \
  --vllm-enforce-eager \
  --output-json prompt_embed_singletons.json
```

- test whether mixed shapes already fail inside one batched `generate_many_with_sessions(...)` call:

```bash
PYTHONPATH=external/chatterbox/src python external/chatterbox/diagnose_vllm_prompt_embeds.py \
  --mode batched \
  --device cuda \
  --language-id ar \
  --audio-prompt-path "$PROMPT_AUDIO" \
  --texts-file external/chatterbox/arabic_streaming_sentences.txt \
  --text-limit 8 \
  --batch-size 2 \
  --vllm-model-dir runs/t3_vllm_export \
  --vllm-gpu-memory-utilization 0.5 \
  --vllm-max-model-len 2048 \
  --no-vllm-prefix-caching \
  --vllm-enforce-eager \
  --output-json prompt_embed_batched.json
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
- and the safe simulator grouping defaults are:
  - prompt-length-only grouping
  - largest-ready-cohort selection
- current local read:
  - prefix caching was one separate incompatibility
  - after that was fixed, the old exact text-length bucketing still produced singleton sequential requests that did not match the working benchmark shape
  - the current safe path is admission-batched cohorts plus eager mode, with grouping shaped around `vLLM` rather than the legacy custom scheduler

## 8. CFG-in-vLLM Test Commands

CFG is now handled natively inside vLLM. Use `--cfg-weight 0.5` (or any positive value) instead of `0`.

### Single-request CFG check

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
  --no-vllm-prefix-caching \
  --vllm-enforce-eager \
  --cfg-weight 0.5 \
  --temperature 0.8 \
  --max-new-tokens 300
```

### Concurrency benchmark with CFG

```bash
PYTHONPATH=external/chatterbox/src python external/chatterbox/simulate_streaming_service.py \
  --impl vllm_turbo_s3 \
  --device cuda \
  --language-id ar \
  --audio-prompt-path "$PROMPT_AUDIO" \
  --fixed-text "مرحباً، يسعدنا خدمتك اليوم. كيف يمكنني مساعدتك؟" \
  --vllm-model-dir runs/t3_vllm_export \
  --vllm-gpu-memory-utilization 0.5 \
  --vllm-max-model-len 2048 \
  --no-vllm-prefix-caching \
  --vllm-enforce-eager \
  --concurrency-levels 1 2 4 \
  --rounds-per-level 3 \
  --stagger-ms 0 \
  --batching-window-ms 10 \
  --save-mode all \
  --warmup-runs 1 \
  --cfg-weight 0.5 \
  --temperature 0.8 \
  --max-new-tokens 300 \
  --allow-vllm-compiled-service-sim \
  --output-dir streaming_sim_vllm_cfg05
```

What to look for:
- `t3_s` should be similar at `c1`, `c2`, and `c4` — no longer multiplying with N
- no `token_repetition` log warnings (handled by `T3CFGLogitsProcessor` now)
- audio quality comparable to baseline `scheduled` path

### How T3CFGLogitsProcessor works

For each request with `cfg_weight > 0` the worker submits two vLLM sequences:
- **cond**: full prompt (speaker + text + speech BOS), tagged with `extra_args={cfg_weight, is_uncond: false, pair_id}`
- **uncond**: same speaker conditioning, but text = SOT + EOT only (empty text), tagged with `extra_args={cfg_weight, is_uncond: true, pair_id}`

At every decode step, `T3CFGLogitsProcessor.apply(logits)` runs over all batch logits:
1. `cfg_logits[cond] = cond_logits + w * (cond_logits - uncond_logits)`
2. EOS suppression: block stop token for first `max(25, text_token_len * 3)` steps
3. 3× token repetition → force EOS
4. `logits[uncond]` = one-hot on argmax of cfg_logits (mirrors cond trajectory)

For N concurrent requests this means 2N sequences run in one vLLM `generate()` call. vLLM's weight-sharing makes `T_vllm(2N) ≈ T_vllm(N)`, so the HF replay O(N) bottleneck is gone.

## Supporting Docs

- [t3_engine_migration_memo.md](/Users/hisham/Code/Bahraini_TTS/architecture/t3_engine_migration_memo.md)
- [t3_serving_stack_layering_memo.md](/Users/hisham/Code/Bahraini_TTS/architecture/t3_serving_stack_layering_memo.md)
- [t3_mixed_traffic_scheduler_research_memo.md](/Users/hisham/Code/Bahraini_TTS/architecture/t3_mixed_traffic_scheduler_research_memo.md)
