# Bahraini TTS — Project Context

## Current Goal

The current goal is not to build the full Bahraini front end first.

The current goal is:

- understand whether a `Chatterbox`-style architecture is a strong base
- identify the real scalability bottleneck in that stack
- isolate and improve the `S3 token -> mel` path first if it is the bottleneck
- only after that, decide how to build an `Arabic-only` or `Bahraini-adapted` version

This project is now operating in two phases:

1. `Scalability phase`
2. `Arabic specialization phase`

## Current Working Hypothesis

The strongest current hypothesis is:

- `T3` is probably not the main scalability problem
- `S3Gen`, especially the iterative `speech-token -> mel` decoder, is the main latency bottleneck
- Arabic quality issues and scalability issues should not be mixed into one problem too early

But the deeper architectural concern is:

- the stack is sequential twice
- `T3` is autoregressive over speech tokens
- `S3` is iterative over acoustic decoding

So reducing S3 steps alone may improve latency without making the architecture truly scalable.

So the current question is not:

- "How do we build a full Bahraini TTS stack from scratch?"

It is:

- "Can we keep the Chatterbox-style architecture, improve its scalability, and only then specialize it toward Arabic?"

## Current Architecture Mental Model

The Chatterbox multilingual path is currently understood as:

```text
text
  -> language_id tag
  -> multilingual tokenizer
  -> T3 token-to-token transformer
  -> speech tokens
  -> S3Gen speech-token decoder
  -> waveform
```

More precisely:

- `MTLTokenizer` handles multilingual text tokenization and prepends a language tag like `[ar]`
- `T3` uses text tokens plus conditioning to predict `speech tokens`
- `S3Gen` converts those speech tokens into mel/audio
- the likely expensive part is the `speech-token -> mel` flow decoder inside `S3Gen`

## How `S3 token -> mel` Actually Works

The important architectural point is that `S3Gen` is not a simple token decoder.

It is closer to:

```text
speech tokens
  -> token embedding
  -> upsampling Conformer encoder
  -> mel-rate conditioning sequence `mu`
  -> prompt-conditioned causal flow decoder
  -> generated mel
  -> vocoder
```

More concretely, the path has three major conditioning branches:

### 1. Prompt speech-token branch

- reference audio is resampled to `16 kHz`
- `S3Tokenizer` extracts prompt speech tokens
- these prompt tokens are concatenated in front of generated speech tokens

### 2. Prompt acoustic branch

- the same reference audio is resampled to `24 kHz`
- mel features are extracted from it
- those prompt mel frames are injected as the acoustic prefix condition

### 3. Speaker branch

- a speaker encoder extracts an x-vector style speaker embedding
- that embedding is projected into the flow decoder's conditioning space

### Main decoding path

- prompt tokens + generated tokens are embedded
- an `UpsampleConformerEncoder` expands the token timeline to the mel timeline
- this produces an `80`-channel mel-rate conditioning sequence usually written as `mu`
- a conditional flow-matching decoder starts from noise and iteratively updates the mel tensor
- inside each flow step, a heavy causal estimator predicts `dx/dt`
- after the flow solver finishes, the prompt prefix is cropped off and only the newly generated mel remains

## Where The Chatterbox S3 Design Comes From

The Chatterbox S3 path is strongly aligned with the `CosyVoice` token-to-mel design.

The useful upstream mental model is:

- speech tokens are first converted into a mel-rate conditioning sequence
- generation then happens through conditional flow matching over mel frames
- the flow estimator itself is a U-Net-like stack of `ResNet1D + Transformer` blocks with timestep conditioning

So the extracted `conditional flow matching` figure from the `CosyVoice` paper is not the whole token-to-mel path.

It is only the inner flow estimator view.

## Historical Lineage

The `S3 token -> mel` path did not originate in Chatterbox.

The cleanest lineage is:

1. `Glow-TTS`
   - established the monotonic alignment search (`MAS`) style text-to-mel prior path
   - important because later non-autoregressive acoustic models keep the idea of aligning a shorter linguistic sequence to a longer mel sequence

2. `Grad-TTS`
   - kept the alignment-driven `text -> mu_y` idea
   - replaced direct mel prediction with an iterative diffusion decoder over mel spectrograms
   - this is one major root of the later "predict mel by iterative denoising / ODE-style refinement" branch

3. `Matcha-TTS`
   - kept the same broad text-to-mel structure
   - replaced slower diffusion-style decoding with `conditional flow matching`
   - the important point is that it still performs iterative generation at mel resolution
   - architecturally, this is the most direct ancestor of the CosyVoice flow decoder stack

4. `CosyVoice v1`
   - changed the front side of the problem from plain text conditioning to supervised semantic `speech tokens`
   - added zero-shot prompt conditioning through:
     - prompt speech tokens
     - prompt mel prefix
     - speaker embedding
   - added the token-rate to mel-rate upsampling encoder before the flow decoder
   - this is the first place where the full `speech tokens -> upsampled mu -> prompt-conditioned flow decoder -> mel` pattern appears as a published system

5. `CosyVoice 2`
   - kept the same basic idea
   - pushed it toward streaming with finite-scalar-quantized speech tokens and chunk-aware causal flow matching
   - this improves deployability, but it still keeps the mel-rate flow decoder as a core component

6. `Chatterbox S3`
   - directly inherits this CosyVoice family design
   - in code, Chatterbox `s3gen.py` is explicitly marked as modified from CosyVoice

## What Is Original Versus Borrowed

It helps to separate implementation borrowing from architectural borrowing.

### Direct Chatterbox inheritance

- Chatterbox `S3Gen` directly inherits the CosyVoice-style token-to-mel path:
  - speech-token embedding
  - token-to-mel upsampling encoder
  - prompt mel prefix conditioning
  - speaker conditioning
  - conditional flow matching mel decoder

### Direct CosyVoice inheritance

- CosyVoice explicitly borrows the flow-model side from `Matcha-TTS`
- CosyVoice also borrows encoder / Conformer infrastructure from `WeNet` and `ESPnet`-style components
- the "speech token" side is where CosyVoice is more novel: supervised semantic tokens are used as the main intermediate unit for scalable zero-shot multilingual TTS

### Practical takeaway

So if we ask "where did the S3 token-to-mel idea come from?", the answer is:

- the exact Chatterbox version comes from `CosyVoice`
- the flow decoder core comes from the `Matcha-TTS` / `conditional flow matching` line
- that line itself comes from the earlier `Grad-TTS` / `Glow-TTS` style acoustic-model branch
- the speech-token front end is the more CosyVoice-specific contribution

## Why This Path Is Hard To Scale

The central issue is not only "too many diffusion steps."

The deeper issue is that the architecture compounds multiple expensive effects:

### 1. Sequence expansion

- speech tokens run at about `25 Hz`
- mel frames run at about `50 fps`
- the upsampling encoder doubles the temporal resolution before flow decoding even starts

So the expensive decoder operates on the longer mel timeline, not on the shorter token timeline.

### 2. Iterative generation over the full mel sequence

- the conditional flow solver updates the mel tensor repeatedly
- every step runs the estimator over the whole current mel-length sequence
- longer utterances increase both the per-step compute and the activation footprint

### 3. Heavy per-step estimator

- the inner estimator is not a small projection head
- it is a causal U-Net-like stack with:
  - ResNet1D blocks
  - transformer blocks
  - down path
  - mid path
  - up path
  - skip connections

So "one step" can still be expensive if that single step is a large whole-sequence model pass.

### 4. Upstream serial dependence still remains

- `T3` still generates speech tokens autoregressively
- `S3` still decodes those tokens into mel afterwards

That means the stack stays sequential twice:

1. text to speech tokens
2. speech tokens to mel

### 5. GPU scaling pressure

This is why the problem is not just latency.

It is also:

- VRAM pressure from whole-sequence decoding
- weak scaling with long utterances
- weak scaling under concurrent load
- poor batching efficiency if sequence lengths differ a lot

So this is fundamentally a GPU resource and serial computation problem, not just a kernel-tuning problem.

## Why Turbo-Style Distillation Is Only A Partial Fix

Reducing the S3 flow decoder from around `10` steps to `1` step is useful.

But it is still a patch-level optimization, not a full architectural solution, because it does not remove:

- the mel-rate sequence expansion
- the heavy whole-sequence estimator
- the upstream autoregressive `T3` generation stage

So step reduction can improve practical latency a lot while still leaving the main scalability limits in place.

## Important Clarification

Arabic in Chatterbox multilingual is not stored as a clean detachable submodel.

It is selected by:

- a language control tag like `[ar]`
- shared multilingual text vocabulary
- shared transformer weights

That means:

- Arabic can be run in isolation at inference
- Arabic cannot be cleanly "cut out" of the checkpoint by deleting a few modules

The cleaner path is:

- keep the multilingual checkpoint as `teacher` or `initializer`
- build an `Arabic-only student` later if needed

## Current Priorities

### Priority 1: Benchmark the Current Stack

Measure:

- tokenizer time
- T3 generation time
- S3 token-to-mel time
- vocoder time
- memory / VRAM behavior

### Priority 2: Isolate S3 Scalability Work

Focus on:

- fewer CFM steps
- per-step estimator cost
- sequence-length scaling
- batch-size / concurrency scaling
- meanflow / distilled decoder behavior
- runtime and memory improvements in `S3 token -> mel`

Do not change the speech-token interface yet unless benchmarking justifies it.

Important:

- this is still an optimization phase
- not the final architecture answer if the sequential structure remains the core problem
- the real question is whether we are optimizing a bottleneck or optimizing around a design that still does not scale well enough

### Priority 3: Arabic-Only Student Design

Only after the scalability path is understood:

- rebuild Arabic-only text tokenizer / vocab
- rebuild text-side embeddings / heads as needed
- transfer the shared transformer and speech-side modules where reasonable

If the architecture still scales poorly after S3 optimization, the student should remove one or both sequential bottlenecks instead of copying them blindly.

### Priority 4: Bahraini Adaptation

Only after the architecture path is stable:

- adapt toward Arabic-only
- then adapt toward Bahraini dialect

## What We Are Not Doing Right Now

- Not building the Stage 1 pronunciation review workflow
- Not building a lexicon-first front end right now
- Not training a FastSpeech 2 style system first
- Not changing the speech tokenizer blindly
- Not treating Arabic quality and runtime scalability as one single issue

## Why The Speech Tokenizer Is Not A Small Swap

Changing the speech tokenizer affects:

- what `T3` predicts
- the speech-token embedding / head in `T3`
- the token embedding inside `S3Gen`
- the `S3 token -> mel` decoder behavior

So a new speech tokenizer or frame rate is not a one-file optimization. It is a coordinated retraining problem.

## Files In This Repo

| File | Purpose |
|------|---------|
| `architecture/bahraini_tts_architecture.drawio` | earlier Bahraini-only architecture reference |
| `architecture/chatterbox_arabic_specialization.drawio` | current Chatterbox specialization diagram |
| `architecture/chatterbox_s3_token_to_mel.drawio` | focused diagram of the S3 speech-token-to-mel stack |
| `CHATTERBOX_SCALING_PLAN.md` | current scaling-first execution direction |
| `TRAINING_DEBUG_CHECKLIST.md` | checklist for remote training reruns and debugging |
| `CONTEXT.md` | this file |
| `PROGRESS.md` | current status, decisions, next steps |

## Current Decision

The current project direction is:

1. use `Chatterbox` as the main architecture under study
2. profile the stack before redesigning it
3. treat `S3 token -> mel` as the first scalability target
4. treat Turbo-style step reduction as useful but incomplete
5. decide whether a real scalable student must also replace the autoregressive `T3` path and/or the heavy S3 mel decoder
6. treat `Arabic-only student` design as the clean specialization path
7. postpone full Bahraini front-end work until the architecture path is clearer
