# Cloud GPU Quickstart

This is the shortest path to run the current Chatterbox baseline and the new streaming-safe runtime on a GPU box.

Reference for the current tensor/state flow:

- [CHATTERBOX_STATE_FLOW.md](/Users/hisham/Code/Bahraini_TTS/CHATTERBOX_STATE_FLOW.md)

## 1. Clone The Repo

```bash
export GITHUB_TOKEN=YOUR_GITHUB_TOKEN
git clone https://$GITHUB_TOKEN@github.com/hishambarakat16/ChatterBox_S3_Concurrency.git
cd ChatterBox_S3_Concurrency
git submodule update --init external/chatterbox
```

## 2. Create The Python Environment

Use Python `3.11`.

```bash
conda create -y -n chatterbox-s3 python=3.11
conda activate chatterbox-s3
python -m pip install --upgrade pip wheel
python -m pip install "setuptools<81"
```

## 3. Apply The Local Chatterbox Runtime Patch

The new runtime files live as a patch because `external/chatterbox` is still tracked as a submodule.

Run this from the repo root:

```bash
git -C external/chatterbox apply ../../patches/chatterbox_streaming_runtime.patch
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
python -c "from chatterbox import ChatterboxMultilingualTTS, ChatterboxMultilingualStreamingTTS; print('imports_ok')"
```

## 6. Pick A Prompt File

```bash
export PROMPT_AUDIO=$PWD/SPK_17_000003.wav
```

## 7. Run Baseline Concurrency Benchmark

```bash
PYTHONPATH=external/chatterbox/src python external/chatterbox/benchmark_multilingual_concurrency.py \
  --impl baseline \
  --device cuda \
  --language-id ar \
  --audio-prompt-path "$PROMPT_AUDIO" \
  --text "مرحبا، هذا اختبار للبنية الحالية." \
  --concurrency-levels 1 2 \
  --trace-shapes
```

## 8. Run Streaming Concurrency Benchmark

```bash
PYTHONPATH=external/chatterbox/src python external/chatterbox/benchmark_multilingual_concurrency.py \
  --impl streaming \
  --device cuda \
  --language-id ar \
  --audio-prompt-path "$PROMPT_AUDIO" \
  --text "مرحبا، هذا اختبار للبنية الحالية." \
  --concurrency-levels 1 2 \
  --trace-shapes
```

## 9. Send Back These Results

Send back:

- GPU model
- CUDA available output from step 5
- full terminal output from the baseline run
- full terminal output from the streaming run
- whether either run crashed or OOMed
- whether `concurrency=2` failed
- whether any output was obviously truncated
