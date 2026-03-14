# Cloud GPU Quickstart

This is the shortest path to run the current Chatterbox baseline, the streaming runtime, the first-pass `concurrent` runtime, and the newer `scheduled` runtime on a GPU box.

Reference for the current tensor/state flow:

- [CHATTERBOX_STATE_FLOW.md](/Users/hisham/Code/Bahraini_TTS/CHATTERBOX_STATE_FLOW.md)

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

## 14. Send Back These Results

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
