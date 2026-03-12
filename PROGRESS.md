# Bahraini TTS — Progress & Current Thinking

_Last updated: 2026-03-12_

---

## What We Have Done So Far

### Repository Setup
- [x] GitHub repo created
- [x] Python environment set up (`env-f5-tts/` — contains F5-TTS reference)
- [x] F5-TTS reference code cloned (`F5-TTS/`) for reference/comparison
- [x] `.gitignore` configured to exclude `env-f5-tts/` and `F5-TTS/`

### Architecture Design
- [x] Defined the full system architecture (see `CONTEXT.md`)
- [x] Created paper-quality architecture diagrams:
  - `bahraini_tts_inference.drawio` — inference pipeline with semantic shapes
  - `bahraini_tts_training.drawio` — training supervision flow
  - `bahraini_tts_architecture.drawio` — original combined overview
- [x] Diagram shape conventions established:
  - Parallelogram → data/tensor nodes
  - Rounded rectangle → processing modules
  - Cylinder → database/lexicon
  - Ellipse → embeddings/vectors
  - Trapezoid → predictor blocks
  - Hexagon → vocoder (specialized synthesis)
  - Diamond (rhombus) → loss functions
  - Stacked rectangles → N repeated layers

---

## Current State

**Phase: Pre-implementation — architecture and planning complete**

No code has been written yet. The repo contains:
- Reference code (F5-TTS) for study
- Architecture diagrams
- This context/progress documentation

---

## Decisions Made

| Decision | Choice | Reasoning |
|----------|--------|-----------|
| Acoustic model type | FastSpeech 2 style (non-autoregressive) | Low latency, parallel decoding |
| Vocoder | HiFi-GAN (primary), BigVGAN Lite (upgrade path) | Speed vs quality tradeoff |
| Front end | Rule-based G2P + custom Bahraini lexicon | Deterministic, debuggable dialect control |
| Speaker setup | Single speaker for v1 | Reduce complexity, prove quality first |
| Training target | Bahraini dialect only | Quality focus, data efficiency |
| GPU strategy | PyTorch DDP from day 1 | Scalability built in from start |
| Deployment export | ONNX → TensorRT | Low latency production serving |

---

## Open Questions / Things To Decide Next

### Data
- [ ] Do we have Bahraini Arabic speech recordings? If yes, how many hours? What quality?
- [ ] Do we need to collect/purchase data, or is there an existing dataset?
- [ ] What is the speaker profile for v1? (male/female, age, register)
- [ ] What transcription format will we use? (raw Arabic, diacritized, romanized?)

### Front End
- [ ] Which phoneme set will we use? (Buckwalter-based IPA? Custom Bahraini IPA subset?)
- [ ] How large is the initial Bahraini lexicon? Does one already exist?
- [ ] How do we handle code-switching (English words in Bahraini speech)?
- [ ] Which text normalization rules are most critical for Bahraini (numbers, dates, abbreviations)?

### Model Architecture
- [ ] How many FFT layers in encoder/decoder? (FastSpeech 2 default: 4)
- [ ] Hidden dimension size? (FastSpeech 2 default: 256)
- [ ] Attention heads? (FastSpeech 2 default: 2)
- [ ] Mel spectrogram config: n_mels (80?), sample rate (22050 or 24000?), hop length?
- [ ] Which pitch extraction tool? (RAPT / REAPER / WORLD)

### Training
- [ ] Which MFA (Montreal Forced Aligner) acoustic model for Bahraini Arabic alignment?
- [ ] Training hardware? (How many GPUs, what type?)
- [ ] Batch size, learning rate schedule?
- [ ] How do we validate/evaluate? (MOS, WER, naturalness benchmarks?)

### Deployment
- [ ] What is the serving infrastructure? (cloud, on-prem, edge?)
- [ ] Latency target? (< 100ms? < 50ms first-chunk?)
- [ ] Expected concurrent request load?

---

## Immediate Next Steps (Priority Order)

1. **Assess data situation** — determine what Bahraini speech data is available
2. **Define phoneme set** — create the Bahraini Arabic phoneme inventory
3. **Start building the front end** — text normalization rules and initial G2P
4. **Set up training pipeline skeleton** — data loading, mel extraction, MFA alignment
5. **Implement acoustic model** — FastSpeech 2 with DDP support
6. **Train vocoder** — HiFi-GAN on Bahraini speech data
7. **End-to-end integration** — connect all three stages
8. **Evaluation** — MOS testing, latency benchmarking

---

## Reference Materials

- `F5-TTS/` — F5-TTS codebase (for architecture reference, not for use directly)
- `References/images/` — Paper figures used for diagram style reference:
  - `fastspeech2.png` — FastSpeech 2 architecture figure
  - `compact-neural-tts-voices-Vocoder.png` — Compact TTS vocoder
  - `qwem-tts-overview.png` — Qwen3-TTS overview
  - `qwen-tts-tokenizer.png` — Qwen-TTS tokenizer details
- `CONTEXT.md` — Full architecture and design context

---

## Current Thinking / Notes

**On the front end:** The Bahraini dialect has specific phonological features that MSA-based G2P systems miss entirely. Key ones:
- /q/ → /g/ or /j/ in many words (dialectal)
- Specific vowel lengthening patterns
- Many Persian/English loanwords with non-Arabic phonology
- Code-switching mid-sentence is very common

**On data:** This is likely the biggest bottleneck. Getting clean, transcribed, single-speaker Bahraini speech data is the critical path item. Without this, everything else is academic.

**On architecture size:** For a single-speaker, single-dialect system, we can go smaller than FastSpeech 2 defaults. A 256-dim model with 4 FFT layers is already fast. We could try 128-dim for edge deployment.

**On the vocoder:** HiFi-GAN V1 is the safe choice. BigVGAN Lite might be worth trying if quality is the priority. Both train well on 10-50 hours of data.
