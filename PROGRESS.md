# Progress

_Last updated: 2026-03-14_

## Done

- cloned and registered reference repos as submodules under `external/`
- inspected local `Chatterbox` runtime
- traced `T3 -> S3 -> vocoder`
- confirmed `S3` lineage from the `CosyVoice` family
- checked `CosyVoice 3` as a later family evolution
- reduced the project docs to a streaming-concurrency focus
- defined the local Chatterbox fork strategy and minimal-file-duplication plan
- added Layer 1 streaming-runtime scaffolding inside `external/chatterbox`
- created [chatterbox_serving_shape_current_vs_target.html](/Users/hisham/Code/Bahraini_TTS/architecture/chatterbox_serving_shape_current_vs_target.html) to show current vs target serving architecture with code anchors

## Current Focus

Only this:

- streaming concurrency per GPU

Main KPI:

- `max concurrent streaming sessions per GPU at target latency`

## Current Baseline Judgment

Current `Chatterbox` is not concurrency-friendly as written because:

- request state is stored and mutated on the model object
- that either risks unsafe sharing or pushes us toward wasteful one-model-per-request fallback
- S3 contains batch-size-1 assumptions
- T3 and S3 are both serial hot paths

## Current Plan

1. keep current Chatterbox as baseline
2. make runtime request-safe
3. introduce explicit session state
4. compare baseline vs new runtime path
5. optimize `S3` next

## Not Current Work

- Bahraini front end
- Arabic-only student
- tokenizer redesign
- broad architecture brainstorming outside streaming concurrency
