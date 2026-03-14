# Cloud GPU Quickstart

This is the shortest path to run the current Chatterbox baseline and the new streaming-safe runtime on a GPU box.

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
python -m pip install --upgrade pip setuptools wheel
```

## 3. Apply The Local Chatterbox Runtime Patch

The new runtime files live as a patch because `external/chatterbox` is still tracked as a submodule.

Run this from the repo root:

```bash
git -C external/chatterbox apply ../../patches/chatterbox_streaming_runtime.patch
```

## 4. Install Chatterbox From Source

```bash
pip install -e external/chatterbox
```

## 5. Sanity Check The Environment

```bash
python -c "import torch; print('torch', torch.__version__); print('cuda', torch.cuda.is_available()); print('device_count', torch.cuda.device_count())"
python -c "from chatterbox import ChatterboxMultilingualTTS, ChatterboxMultilingualStreamingTTS; print('imports_ok')"
```

## 6. Pick A Prompt File

```bash
export PROMPT_AUDIO=/absolute/path/to/reference.wav
```

## 7. Run Baseline

```bash
PYTHONPATH=external/chatterbox/src python external/chatterbox/compare_multilingual_runtime.py \
  --impl baseline \
  --device cuda \
  --language-id ar \
  --audio-prompt-path "$PROMPT_AUDIO" \
  --text "مرحبا، هذا اختبار للبنية الحالية." \
  --warmup-runs 1 \
  --runs 3
```

## 8. Run Streaming Runtime

```bash
PYTHONPATH=external/chatterbox/src python external/chatterbox/compare_multilingual_runtime.py \
  --impl streaming \
  --device cuda \
  --language-id ar \
  --audio-prompt-path "$PROMPT_AUDIO" \
  --text "مرحبا، هذا اختبار للبنية الحالية." \
  --warmup-runs 1 \
  --runs 3
```

## 9. Send Back These Results

Send back:

- GPU model
- CUDA available output from step 5
- full terminal output from the baseline run
- full terminal output from the streaming run
- whether either run crashed or OOMed
- whether both runs produced the same rough audio length
