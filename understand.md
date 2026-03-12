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

### Project State

- HM understands the repo is still pre-implementation.
- HM understands the current repo mostly contains design docs, diagrams, and reference repos.

### Major Risks

- HM understands data is a major risk.
- HM understands front-end design is a major risk.
- HM understands alignment quality is a major risk.

## Likely Understood But Still Worth Validating

- Why the phoneme inventory must be fixed early
- Why MFA alignment quality depends on dictionary coverage
- Why DDP is not the first blocker

## Open Understanding Goals

- Confirm HM's preferred transcript representation
- Confirm HM's preferred phoneme representation
- Confirm HM's view on single-speaker v1 scope
- Confirm whether HM wants the first trainer to prioritize simplicity or DDP

## Update Rule

When HM explains a concept correctly in discussion, add it here in one short line.
