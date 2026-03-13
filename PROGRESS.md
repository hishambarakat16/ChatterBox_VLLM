# Bahraini TTS — Progress & Current Thinking

_Last updated: 2026-03-14_

---

## What We Have Done So Far

### Repository Setup
- [x] GitHub repo created
- [x] Python environment set up (`env-f5-tts/` — contains F5-TTS reference)
- [x] F5-TTS reference code cloned (`F5-TTS/`) for reference/comparison
- [x] `.gitignore` configured to exclude `env-f5-tts/` and `F5-TTS/`
- [x] Reference repos cloned under `external/` for acoustic model, vocoder, alignment, and Arabic utilities

### Architecture Study
- [x] Local Chatterbox multilingual code inspected
- [x] Local CosyVoice repo added for upstream architectural reference
- [x] Local CosyVoice v1 inference path traced from frontend -> speech-token LM -> flow token-to-mel -> HiFT vocoder
- [x] Matcha-TTS repo and lineage papers downloaded under `References/`
- [x] CozyVoice linear vs parallel breakdown note created
- [x] Chatterbox Arabic specialization diagram created
- [x] Focused `S3 token -> mel` diagram created
- [x] Current bottleneck hypothesis narrowed to the `S3 token -> mel` decoder path
- [x] Current architectural risk clarified: Turbo-style step reduction is an optimization, not a full scalability solution
- [x] Current architectural understanding clarified: the decoder first expands tokens to mel-rate conditioning and then runs a heavy iterative flow model over the whole mel timeline
- [x] Existing practical parallelism clarified: prompt preprocessing branches are parallelizable and CosyVoice 1/2 already use chunk-level pipeline overlap, but single-utterance generation remains serial at the LLM token loop and flow solver loop
- [x] Historical lineage clarified: `Glow-TTS -> Grad-TTS -> Matcha-TTS -> CosyVoice -> Chatterbox S3`

### Architecture Design
- [x] Defined the full system architecture (see `CONTEXT.md`)
- [x] Created paper-quality architecture diagrams:
  - `architecture/bahraini_tts_architecture.drawio` — Bahraini TTS combined overview
  - `architecture/chatterbox_arabic_specialization.drawio` — Chatterbox multilingual teacher and Arabic-only student path
  - `architecture/chatterbox_s3_token_to_mel.drawio` — focused S3 speech-token-to-mel subgraph
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

**Phase: Architecture pivot — Chatterbox-based specialization and scalability analysis**

The repo now contains:
- Reference repos for study under `external/`
- Architecture diagrams and planning docs
- Chatterbox architecture notes and Arabic specialization diagram
- Focused CozyVoice linear/parallel architecture note
- Training/debug notes for future reruns

---

## Decisions Made

| Decision | Choice | Reasoning |
|----------|--------|-----------|
| Main architecture under study | Chatterbox multilingual | Strongest current base to study for scalability and Arabic specialization |
| Immediate focus | `S3 token -> mel` scalability | Current code and README both point to this as the likely bottleneck |
| Scalability interpretation | Turbo is a patch, not the final answer | Fewer S3 steps do not remove the sequential structure of the stack |
| Upstream mental model | `CosyVoice` token-to-mel flow decoder | Chatterbox S3 follows the same basic pattern: token expansion -> `mu` -> conditional flow matching over mel |
| Historical origin | `CosyVoice` is the direct origin, `Matcha-TTS` is the direct flow-decoder ancestor | Chatterbox inherits the CosyVoice token-to-mel stack, and CosyVoice explicitly builds on Matcha-TTS |
| Arabic path | Arabic-only student, not checkpoint surgery | Cleaner than trying to cut Arabic out of shared multilingual weights |
| Speech-token interface | Keep it fixed for now | Changing it forces coordinated retraining of T3 and S3 |
| First methodology | Benchmark before redesign | Avoid solving the wrong bottleneck |
| Bahraini work | Postponed until architecture path is clearer | Do not mix dialect-quality work with runtime scaling too early |

---

## Open Questions / Things To Decide Next

### Data
- [ ] Is the clean single-speaker subset enough to support adaptation experiments reliably?
- [ ] How much clean Arabic-only data can we reserve for eval prompts and checkpoint comparison?

### Chatterbox Path
- [ ] Is the current bottleneck actually in `S3 token -> mel`, or is `T3` already too expensive for the target deployment?
- [ ] Do we want Arabic-only fine-tuning first, or Arabic-only student distillation directly?
- [ ] Do we keep the current `25 Hz` speech-token interface, or redesign the whole speech-token stack later?
- [ ] Which weights should be frozen, transferred, or rebuilt for an Arabic-only student?

### Scalability
- [ ] What is the actual latency split between tokenizer, T3, S3 token-to-mel, and vocoder?
- [ ] Is reducing CFM steps enough, or do we need a new distilled/meanflow-style S3 decoder?
- [ ] How much of the cost comes from sequence expansion from `25 Hz` speech tokens to mel-rate decoding?
- [ ] How much of the cost comes from the per-step `ConditionalDecoder` itself?
- [ ] Even after S3 optimization, is the autoregressive T3 path still too sequential for the target?
- [ ] Is memory usage or wall-clock latency the real deployment problem?
- [ ] How badly does the current S3 path scale with utterance length and concurrent batch size?
- [ ] Do we need streaming, or only faster synchronous generation?

---

## Immediate Next Steps (Priority Order)

1. **Benchmark Chatterbox locally** — measure where latency actually goes: tokenizer vs T3 vs S3 vs vocoder
2. **Measure S3 more granularly** — separate prompt preprocessing, token upsampling encoder, per-step flow estimator cost, and total step count cost
3. **Isolate S3 scalability path** — test how much of the problem is really in S3 versus the overall sequential structure
4. **Decide whether the student must remove T3 autoregression too** — not just reduce S3 steps
5. **Choose specialization strategy** — Arabic-only fine-tune, Arabic-only student, or both in sequence
6. **Define Arabic-only student boundaries** — what to rebuild on text side, what to transfer on shared/speech side
7. **Only after that: Bahraini adaptation** — use the cleaned architecture choice as the base for dialect work

---

## Reference Materials

- `F5-TTS/` — F5-TTS codebase (for architecture reference, not for use directly)
- `external/chatterbox/` — Chatterbox multilingual / Turbo reference code
- `external/CosyVoice/` — upstream token-to-mel flow architecture reference
- `architecture/cosyvoice_v1_linear_parallel_breakdown.md` — source-grounded linear path and parallelism breakdown for CozyVoice v1, with v2/v3 overlap notes
- `References/images/` — Paper figures used for diagram style reference:
  - `fastspeech2.png` — FastSpeech 2 architecture figure
  - `compact-neural-tts-voices-Vocoder.png` — Compact TTS vocoder
  - `qwem-tts-overview.png` — Qwen3-TTS overview
  - `qwen-tts-tokenizer.png` — Qwen-TTS tokenizer details
- `architecture/conditional flow matching.png` — extracted CosyVoice flow-matching figure for the inner decoder view
- `CONTEXT.md` — Full architecture and design context
- `TRAINING_DEBUG_CHECKLIST.md` — Remote rerun artifact checklist

---

## Current Thinking / Notes

**On Chatterbox multilingual:** Arabic is selected by a language tag and shared multilingual vocab. It is not stored as a clean detachable Arabic-only subnetwork.

**On T3 vs S3:** T3 predicts speech tokens from text plus conditioning. S3Gen then converts speech tokens into mel/audio. The code and README both suggest the S3 token-to-mel path is the main latency bottleneck.

**On how S3 actually works:** The expensive path is not a direct token decoder. Speech tokens are first expanded by an upsampling Conformer encoder into a mel-rate conditioning sequence `mu`, then a conditional flow-matching model repeatedly runs a large causal `ResNet1D + Transformer` estimator over the full mel timeline.

**On the CozyVoice upstream path:** The clean linear path is:
1. text normalization and tokenization
2. prompt preprocessing branches
3. autoregressive speech-token LLM
4. token-to-mel expansion
5. iterative flow decoding over the mel timeline
6. HiFT vocoder

This matches the local source and is now written up in `architecture/cosyvoice_v1_linear_parallel_breakdown.md`.

**On where it came from:** The direct Chatterbox `S3` path comes from `CosyVoice`. The flow-decoder core inside CosyVoice comes from the `Matcha-TTS` conditional-flow-matching acoustic-model line, which itself sits downstream of the earlier `Grad-TTS` and `Glow-TTS` acoustic-model lineage.

**On the real scaling limit:** The issue is not just step count. The issue is:
1. `T3` is still autoregressive
2. `S3` still works on the longer mel timeline, not the shorter token timeline
3. each S3 step is a heavy whole-sequence model pass

So the bottleneck is fundamentally a serial GPU resource problem, not just a missing low-level optimization.

**On what can really be parallelized today:** The safest parallelism is:
1. prompt preprocessing branches
2. batching across requests
3. chunk-level pipeline overlap between upstream token generation and downstream synthesis

That can improve throughput and online latency, but it does not remove the core serial dependencies of the architecture.

**On tokenizer changes:** Replacing the speech tokenizer is not a small swap. A new speech-token rate or new speech-token vocabulary would force coordinated retraining of the T3 speech-token interface and the S3 decoder path.

**On what CosyVoice really added:** The novel CosyVoice part is not "flow matching" by itself. It is the combination of:
1. supervised semantic speech tokens as the intermediate unit
2. prompt speech-token conditioning
3. prompt mel-prefix conditioning
4. speaker conditioning
5. a Matcha-style mel-space flow decoder behind an upsampling encoder

**On current direction:** The most defensible pivot is:
1. profile Chatterbox
2. use the CosyVoice-style flow architecture as the explanatory model for S3
3. treat Turbo-style S3 reduction as an optimization, not the final answer
4. decide whether a real scalable student must also remove or reduce T3 autoregression
5. only then decide how much Arabic-only specialization is worth building
