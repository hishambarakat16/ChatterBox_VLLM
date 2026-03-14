# HM Understanding

## Purpose

This file tracks what HM already understands well enough that the agent does not need to re-explain it from scratch.

Only log items that are clearly confirmed in discussion.

## Confirmed Understanding

### Architecture

- HM understands the planned high-level stack:
  deterministic front end -> FastSpeech 2 style acoustic model -> HiFi-GAN vocoder
- HM understands this is a Bahraini-only TTS system, not a general multilingual TTS system.
- HM understands the reference repos are for study and structure, not for blindly merging into the project.
- HM understands `G2P` as grapheme-to-phoneme conversion.
- HM understands the lexicon as the exact pronunciation override layer.
- HM understands rules as the fallback layer for words not covered by the lexicon.
- HM understands `MTL` as multilingual tokenizer in the Chatterbox path.
- HM understands `T3` predicts speech tokens from text plus conditioning.
- HM understands `S3Gen` converts speech tokens into mel/audio.
- HM understands Arabic in Chatterbox is selected by a language tag and shared tokenizer/weights, not by a detachable Arabic-only submodel.
- HM understands the likely scalability bottleneck is the `S3 token -> mel` path, not necessarily the whole model.
- HM understands Turbo-style step reduction is an optimization, not a full scalability solution if the architecture remains sequential.
- HM understands the direct `S3` lineage is `CosyVoice -> Chatterbox`, with the flow-decoder core inherited from the `Matcha-TTS` line.
- HM understands the CosyVoice contribution is not just flow matching itself, but the combination of supervised semantic speech tokens, prompt conditioning, speaker conditioning, and mel-space flow decoding.
- HM understands the current Chatterbox serving issue is `runtime architecture + serial model architecture`, not one slow line.
- HM understands the current fix is `runtime/session isolation first`, then `S3` redesign only if concurrency is still poor.
- HM understands the target runtime shape is `shared worker + explicit session state`, not immediate model replacement.

### Project State

- HM understands the repo is still architecture-first and pre-implementation.
- HM understands the current repo mostly contains design docs, diagrams, and reference repos.
- HM understands the current project direction has pivoted from Stage 1 pronunciation review toward Chatterbox scalability analysis.
- HM understands the active KPI is `max concurrent streaming sessions per GPU at target latency`.

### Working Process

- HM wants multiple agents to coordinate through shared repo docs rather than assume they are working alone.
- HM wants agents to pick up from each other's latest notes when possible instead of restarting from stale context.
- HM wants agents to leave short identity-based handoff notes such as `Agent 1`, `Agent 2`, and `Agent 3` when that identity is assigned.

### Major Risks

- HM understands data is a major risk.
- HM understands front-end design is a major risk.
- HM understands alignment quality is a major risk.

## Likely Understood But Still Worth Validating

- Why the phoneme inventory must be fixed early
- Why MFA alignment quality depends on dictionary coverage
- Why DDP is not the first blocker

## Open Understanding Goals

- Confirm HM's preferred success metric for scalability work
- Confirm whether HM wants Arabic-only fine-tuning before Arabic-only student distillation
- Confirm whether HM wants synchronous low-latency only or true streaming as a target
- Confirm whether HM wants to preserve current Chatterbox speech-token interface or eventually redesign it

## Update Rule

When HM explains a concept correctly in discussion, add it here in one short line.
