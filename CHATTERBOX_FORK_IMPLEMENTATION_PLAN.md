# Chatterbox Fork Implementation Plan

## Terminology

Important correction:

- a local `clone` is not automatically a `fork`

Right now `external/chatterbox/` is:

- a local clone of the upstream repo
- tracked by the parent repo as a submodule

It becomes our real working fork when we do one of these:

- push it to our own remote fork later
- or explicitly treat this checkout as our modified branch of the project

For the current task, that distinction is enough.

## Repo Strategy

Use `external/chatterbox/` as the working fork.

Reason:

- no second duplicate repo
- easiest path to implementation
- parent repo already tracks it as a submodule

Rule:

- keep the current upstream files as baseline references where possible
- duplicate only the files we actually need to change
- do not rewrite the whole repo up front

## Baseline Preservation

Before changing behavior:

1. record the current submodule commit as baseline
2. keep the original file paths as reference implementations
3. compare all new behavior against that baseline

The point is:

- baseline exists
- forked runtime exists beside it
- we can switch and compare

## Fork Shape

### Phase 1: duplicate the runtime wrapper only

Create new files beside the originals:

- `external/chatterbox/src/chatterbox/mtl_tts_streaming.py`
- `external/chatterbox/src/chatterbox/runtime/session.py`
- `external/chatterbox/src/chatterbox/runtime/types.py`

Purpose:

- keep original `mtl_tts.py` untouched
- move request/session state out of the shared model object
- make per-request conditionals explicit

### Phase 2: add a streaming-safe service layer

Create:

- `external/chatterbox/src/chatterbox/runtime/worker.py`

Purpose:

- shared model weights live here
- active sessions are tracked here
- no request-specific mutable state is stored on the model wrapper itself

### Phase 3: only fork deeper model files if required

Do not duplicate these yet:

- `models/t3/t3.py`
- `models/s3gen/s3gen.py`
- `models/tokenizers/tokenizer.py`

Only fork them if runtime cleanup alone is not enough.

If needed later:

- `models/s3gen/s3gen_streaming.py`
- `models/t3/t3_streaming.py`

## First Concrete Refactor

### Current problem

In current `mtl_tts.py`:

- `self.conds` is shared mutable state
- request-specific data lives on the model instance

That is the first thing to remove.

### Target shape

Instead of:

```text
shared model object
  -> mutable self.conds
  -> generate()
```

Move to:

```text
shared model object
  -> stateless weights and helpers

streaming session object
  -> request conditionals
  -> session caches
  -> decode progress
```

### Session-owned state

Per session:

- prompt audio conditionals
- T3 conditioning
- S3 conditioning
- streaming caches
- decode offsets / progress
- request settings

Shared across sessions:

- model weights
- tokenizer object
- vocoder object
- reusable non-request helpers

## Minimal File Duplication Rule

Duplicate a file only when one of these is true:

1. we need to preserve the original as a clean baseline
2. the behavioral change is large enough that patching in place will create confusion
3. the new version is specifically for streaming/session-safe behavior

Otherwise:

- add a new helper file
- wrap the original behavior
- avoid copying deep model code too early

## Immediate Implementation Order

1. keep `external/chatterbox/src/chatterbox/mtl_tts.py` untouched
2. create `mtl_tts_streaming.py`
3. create `runtime/session.py`
4. move `prepare_conditionals` output into explicit session state
5. remove `self.conds` from the streaming path
6. run the old baseline and the new path side by side
7. only then decide whether `S3` itself needs a forked implementation

## Decision Rule

If the runtime fork gives us clean concurrent session handling:

- keep original `T3` and `S3` for the moment

If concurrency is still bad after runtime cleanup:

- fork `S3` next

If concurrency is still bad after that:

- revisit `T3`

## Non-Goals For This Fork

Not now:

- Arabic specialization
- tokenizer redesign
- speech-token redesign
- replacing Chatterbox with CosyVoice 3 directly

Those are separate decisions.
