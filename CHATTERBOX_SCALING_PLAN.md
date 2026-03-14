# Chatterbox Streaming Plan

## Objective

Optimize for:

- `max concurrent streaming sessions per GPU at target latency`

Not for:

- Bahraini quality
- Arabic specialization
- tokenizer redesign

## Baseline

Use the current `Chatterbox` implementation as the baseline.

We do not need a long research phase before acting.

We need one baseline measurement set, then we fix the runtime and compare against it.

Repo strategy:

- use `external/chatterbox/` as the working fork
- keep original upstream file paths as the baseline path
- add new streaming-specific files beside the originals

See:

- [CHATTERBOX_FORK_IMPLEMENTATION_PLAN.md](/Users/hisham/Code/Bahraini_TTS/CHATTERBOX_FORK_IMPLEMENTATION_PLAN.md)

## What Must Be Fixed First

### 1. Request isolation

Current problem:

- `self.conds` is stored on the model instance and mutated per request

Target:

- no request-specific mutable state on the shared model object
- all conditionals passed explicitly through a session/request object

### 2. Streaming session model

Target:

- one explicit streaming session object per active request
- session owns its prompt state, caches, and decode progress
- shared model weights stay read-only

### 3. Concurrency safety

Target:

- multiple active sessions can share one model worker safely
- no hidden cross-request mutation
- no global prompt state

### 4. S3 serving cost

After the runtime is safe:

- profile `S3` as the first hot path
- reduce per-stream decoder cost there first

## Current Architecture Judgment

### What is probably okay for now

- multilingual tokenizer
- T3 as the initial baseline text-to-speech-token stage
- existing speech-token interface

### What is probably not okay for streaming density

- shared mutable runtime state
- batch-size-1 assumptions on the S3 side
- iterative mel-space S3 cost under many active streams

## Decision Rule

If request isolation + runtime cleanup gives acceptable concurrency:

- keep the architecture longer

If request isolation is fixed and concurrency is still poor:

- replace or redesign `S3`

If S3 is improved and concurrency is still poor:

- revisit `T3` autoregression

## Immediate Work Order

1. capture baseline numbers from current Chatterbox
2. refactor runtime around explicit session state
3. remove request-unsafe shared state
4. rerun baseline
5. then attack `S3`

## Reference Scope

Only keep these mental references active:

- `Chatterbox` = current baseline
- `CosyVoice` = origin of the S3 family
- `CosyVoice 3` = later family evolution, useful reference but not the answer by itself
