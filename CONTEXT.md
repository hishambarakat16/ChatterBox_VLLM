# Bahraini TTS — Project Context

## Goal

Build a compact, high-quality, low-latency Text-to-Speech system specialized exclusively for **Bahraini Arabic dialect**. This is NOT a general-purpose multilingual TTS. It is a single-task, single-dialect system optimized for:

- Natural Bahraini Arabic speech output
- Low inference latency (real-time or faster)
- High concurrency under load
- Multi-GPU scalability (training and serving)
- Small model footprint (deployable to edge and API)

---

## What We Are NOT Building

- Not a multilingual model
- Not a zero-shot voice cloning system (initially)
- Not a large autoregressive model (no GPT-style token generation)
- Not a general Arabic TTS (MSA, Egyptian, Gulf mixed, etc.)
- Not something like Qwen3-TTS or VALL-E in scope

---

## Architecture

### Design Philosophy

> **Deterministic front end + fast non-autoregressive acoustic model + neural vocoder**

The system is split into three independently trainable/replaceable stages:

```
Bahraini Arabic Text
        │
        ▼
┌─────────────────────────────┐
│   Stage 1: Dialect Front End│  (deterministic, no ML needed)
│   - Text Normalization       │
│   - Bahraini G2P             │
│   - Bahraini Lexicon         │
└─────────────┬───────────────┘
              │  phoneme sequence
              ▼
┌─────────────────────────────┐
│   Stage 2: Acoustic Model   │  (FastSpeech 2 style, non-autoregressive)
│   - Phoneme Embedding       │
│   - Positional Encoding     │
│   - Encoder (N × FFT Block) │
│   - Variance Adaptor        │
│     · Duration Predictor    │
│     · Pitch Predictor       │
│     · Energy Predictor      │
│   - Length Regulator        │
│   - Mel Decoder (N × FFT)   │
│   [optional: Speaker Emb.]  │
│   [optional: Style Emb.]    │
└─────────────┬───────────────┘
              │  mel spectrogram
              ▼
┌─────────────────────────────┐
│   Stage 3: Vocoder          │  (neural, GAN-based)
│   - HiFi-GAN or BigVGAN Lite│
└─────────────┬───────────────┘
              │
              ▼
      Bahraini Speech (waveform)
```

---

## Stage Details

### Stage 1 — Dialect Front End

**Purpose:** Convert raw Bahraini Arabic text into a deterministic phoneme sequence. No ML. Fully rule-based and lookup-based.

- **Text Normalization:** Handle numerals (Arabic and Western), diacritics, punctuation, abbreviations, code-switching (Arabic + English words common in Bahraini dialect)
- **Bahraini G2P (Grapheme-to-Phoneme):** Rule-based system encoding Bahraini-specific pronunciation rules (e.g., qaf → gaf, specific vowel coloring, loan word pronunciation)
- **Bahraini Lexicon:** Custom pronunciation dictionary with word-level overrides for dialect-specific words, proper nouns, common phrases
- **Output:** IPA or X-SAMPA phoneme sequence with optional stress/boundary markers

### Stage 2 — Acoustic Model (FastSpeech 2 style)

**Architecture:** Non-autoregressive feed-forward transformer. Predicts all mel spectrogram frames in parallel (not sequentially). This is what gives low latency.

**Key components:**
- **Encoder:** Feed-Forward Transformer (FFT) blocks. Processes phoneme embeddings into contextual representations
- **Variance Adaptor:** Three parallel predictors that add prosodic control:
  - *Duration Predictor* → how many mel frames per phoneme (Length Regulator)
  - *Pitch Predictor* → fundamental frequency (F0) contour at frame level
  - *Energy Predictor* → amplitude/loudness at frame level
- **Mel Decoder:** FFT blocks that take length-regulated + pitch/energy-conditioned sequence and output mel spectrogram frames

**Optional conditioning (not in v1):**
- Speaker embedding (for multi-speaker extension)
- Style/prosody embedding (for emotional TTS)

### Stage 3 — Vocoder

**Purpose:** Convert mel spectrogram to waveform audio. Must be fast.

- **Primary choice:** HiFi-GAN (V1 or V2) — well-proven, fast, high quality
- **Alternative:** BigVGAN Lite — better generalization, slightly slower
- Trained jointly or fine-tuned separately from the acoustic model

---

## Training Setup

### Data Requirements
- Bahraini dialect speech recordings with transcriptions
- Ideally: 10–50 hours, single speaker for v1, multi-speaker later
- MFA (Montreal Forced Aligner) for duration alignment

### Training Supervision Signals
- **Duration Loss:** MSE between predicted durations and MFA-extracted durations
- **Pitch Loss:** MSE between predicted F0 and RAPT/REAPER-extracted F0
- **Energy Loss:** MSE between predicted energy and frame-level L2 norm of mel frames
- **Mel Loss:** L1 + L2 between predicted mel and extracted mel spectrogram
- **Adversarial Loss (vocoder):** GAN discriminator on real vs. generated mel/waveform

### Infrastructure
- Multi-GPU training via PyTorch DDP (DistributedDataParallel)
- High-concurrency serving: batched inference, async API
- Export path: ONNX → TensorRT for production deployment

---

## Deployment Profile

| Target | Approach |
|--------|----------|
| Low-latency API | FastAPI + async batching |
| Edge device | ONNX export, quantization (INT8) |
| Batch synthesis | GPU cluster, large batch |
| Streaming | Chunk-based inference on vocoder |
| Multi-GPU serving | Tensor parallelism or replicated serving |

---

## Files in This Repo

| File | Purpose |
|------|---------|
| `bahraini_tts_inference.drawio` | Architecture diagram — inference pipeline (paper figure style) |
| `bahraini_tts_training.drawio` | Architecture diagram — training supervision flow |
| `bahraini_tts_architecture.drawio` | Original combined overview diagram |
| `CONTEXT.md` | This file — full project context |
| `PROGRESS.md` | Current progress, decisions made, next steps |

---

## Key Design Decisions

1. **Non-autoregressive acoustic model** — chosen for latency, not for quality ceiling
2. **Deterministic front end** — dialect control through rules/lexicon, not ML; easier to debug and maintain
3. **Single dialect focus** — allows smaller model, higher data efficiency, better quality per parameter
4. **HiFi-GAN over WaveNet/autoregressive vocoder** — 100× faster inference, near-indistinguishable quality
5. **Start single speaker** — reduce complexity, prove quality, add multi-speaker later
6. **DDP from day one** — design training loop for multi-GPU from the start even if running single-GPU initially
