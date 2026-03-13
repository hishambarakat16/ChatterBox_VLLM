# Bahraini TTS Implementation Checklist

This checklist tracks the `current` plan.

The current plan is:

1. benchmark `Chatterbox`
2. isolate the real scalability bottleneck
3. optimize `S3 token -> mel` first if it is the bottleneck
4. only after that, design an `Arabic-only student`
5. only after that, attempt `Bahraini` adaptation

## Main Risk

The main risk is solving the wrong problem.

If we change tokenization, Arabic specialization, and runtime optimizations at the same time, we will not know which change actually mattered.

## What We Need To Prove First

### 1. Where does latency actually go?

- [ ] Measure multilingual tokenizer time
- [ ] Measure `T3` generation time
- [ ] Measure `S3 token -> mel` time
- [ ] Measure vocoder time
- [ ] Measure total wall-clock latency
- [ ] Measure VRAM / memory usage

### 2. Is `S3 token -> mel` really the bottleneck?

- [ ] Confirm whether `S3 token -> mel` dominates runtime
- [ ] Confirm whether the problem is step count, model width, memory movement, or vocoder follow-up cost
- [ ] Confirm whether the issue affects sync inference only or also streaming

### 3. Can we improve S3 without changing the token interface?

- [ ] Test fewer CFM steps
- [ ] Test meanflow / distilled S3 behavior
- [ ] Check precision and kernel choices
- [ ] Check batching and cache behavior
- [ ] Check whether vocoder cost becomes dominant after S3 is reduced

## What We Should Not Change Yet

- [ ] Do not replace the speech tokenizer yet
- [ ] Do not change the speech-token frame rate yet
- [ ] Do not redesign Arabic front-end logic yet
- [ ] Do not mix Arabic quality debugging with runtime scalability work

Reason:

Changing the speech tokenizer changes:

- the speech-token IDs that `T3` predicts
- the speech embeddings / head in `T3`
- the token embeddings in `S3Gen`
- the token-to-mel decoder interface

That is a coordinated retraining problem, not a local optimization.

## Read This Code First

### 1. Multilingual text path

- [tokenizer.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/tokenizers/tokenizer.py#L256)

Goal:

- understand what `language_id="ar"` actually does
- understand that Arabic is mostly `shared tokenizer + [ar] tag`

### 2. T3 path

- [t3.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/t3/t3.py#L40)

Goal:

- understand that `T3` predicts speech tokens, not waveform
- understand where text embeddings, speech embeddings, and shared transformer weights sit

### 3. S3 path

- [s3gen.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/s3gen/s3gen.py#L47)
- [s3gen.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/src/chatterbox/models/s3gen/s3gen.py#L234)

Goal:

- understand the `speech-token -> mel -> waveform` stack
- understand where the iterative decoder sits

### 4. Turbo clue

- [README.md](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/README.md#L15)

Goal:

- confirm that the repo authors themselves identify `speech-token -> mel` as the bottleneck

## Execution Checklist

### Phase 0: Local Baseline

- [ ] Run the current multilingual Chatterbox stack locally
- [ ] Use Arabic input only
- [ ] Record end-to-end latency on fixed prompts
- [ ] Save one baseline table of timings

### Phase 1: Profiling

- [ ] Separate timings for tokenizer, `T3`, `S3 flow`, and vocoder
- [ ] Record number of speech tokens produced
- [ ] Record `n_cfm_timesteps`
- [ ] Record hardware and precision mode

### Phase 2: S3 Scaling Work

- [ ] Compare default S3 steps vs reduced steps
- [ ] Compare default path vs meanflow / distilled path if available
- [ ] Document quality drop vs latency gain
- [ ] Decide whether S3 alone is enough to optimize

### Phase 3: Architecture Decision

- [ ] Decide whether to keep multilingual Chatterbox as-is
- [ ] Decide whether to build an Arabic-only student
- [ ] Decide whether speech-token interface changes are justified

### Phase 4: Arabic-Only Student

- [ ] Define Arabic-only text vocab / tokenizer
- [ ] Decide which text-side weights are rebuilt
- [ ] Decide which shared weights are transferred
- [ ] Decide which speech-side weights are transferred

### Phase 5: Bahraini Adaptation

- [ ] Define the adaptation dataset split
- [ ] Decide whether adaptation is Arabic-only first or directly Bahraini
- [ ] Define evaluation prompts for dialect quality

## Current Default Recommendation

For now, the default plan is:

- keep the existing speech-token interface
- keep the multilingual checkpoint as teacher / initializer
- improve `S3 token -> mel` first
- postpone Arabic-only student work until the runtime story is clearer
