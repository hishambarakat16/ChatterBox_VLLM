# Bahraini TTS Implementation Checklist

This is the working checklist for turning the current architecture into a trainable system.

## The Core Thesis

The design still makes sense:

- deterministic Bahraini front end
- FastSpeech 2 style acoustic model
- separate HiFi-GAN vocoder

This is a good v1 design if the goal is:

- low latency
- small footprint
- strong dialect control
- easier debugging than end-to-end black-box TTS

## The Biggest Holes Right Now

These are the gaps that can break the whole project if we ignore them.

### 1. We do not yet know the data situation

Without clean Bahraini speech plus transcripts, the rest is theory.

We need to know:

- whether we already have recordings
- how many hours we have
- sample rate and recording quality
- whether transcripts already exist
- whether transcripts match spoken Bahraini or drift toward MSA

### 2. We do not yet have a text representation policy

This is the largest front-end design hole.

We need to decide:

- what the input transcript format is
- whether we keep Arabic script as the source of truth
- whether we add internal normalized forms
- whether we keep diacritics if present
- how we represent English code-switch words
- whether phonemes are IPA, X-SAMPA, Buckwalter-like symbols, or a custom inventory

### 3. We do not yet have a phoneme inventory

The whole acoustic model depends on a stable symbol set.

We need:

- a Bahraini phoneme list
- silence / pause symbols
- word boundary policy
- gemination policy
- long vowel policy
- loanword handling rules

### 4. Alignment is a real risk

FastSpeech 2 training depends on usable duration targets.

The reference preprocessor assumes:

- aligned `TextGrid` phone boundaries already exist
- each utterance has a `.lab` transcript
- pitch, energy, and mel are extracted after alignment

See:

- [preprocessor.py](/Users/hisham/Code/Bahraini_TTS/external/FastSpeech2/preprocessor/preprocessor.py#L16)
- [alignment_example.md](/Users/hisham/Code/Bahraini_TTS/external/Montreal-Forced-Aligner/docs/source/first_steps/alignment_example.md#L55)

If Bahraini pronunciation differs too much from available Arabic resources, MFA alignments may be noisy until we build a better dictionary.

### 5. The current repo has architecture but not the training glue

The reference repos are not plug-and-play for our design.

We still need to define:

- corpus directory structure
- metadata manifest format
- preprocessing entrypoints
- training configs
- checkpoint layout
- inference wrapper

### 6. “Streaming inference” is premature

Low-latency synthesis is realistic. True streaming should not be treated as a v1 requirement.

## What The Reference Code Tells Us

### FastSpeech 2 is the right mental model

The core model wiring is exactly the architecture we drew:

- encoder
- variance adaptor
- decoder
- mel linear
- postnet

See:

- [fastspeech2.py](/Users/hisham/Code/Bahraini_TTS/external/FastSpeech2/model/fastspeech2.py#L13)
- [modules.py](/Users/hisham/Code/Bahraini_TTS/external/FastSpeech2/model/modules.py#L17)

### But the reference training stack is not our final stack

The upstream FastSpeech 2 training loop uses `DataParallel`, not DDP.

See:

- [train.py](/Users/hisham/Code/Bahraini_TTS/external/FastSpeech2/train.py#L40)

So if we want DDP from day one, we should treat this repo as an architectural reference, not our final trainer.

### HiFi-GAN is a strong v1 vocoder choice

The generator/discriminator setup is clean and standard:

- generator converts 80-bin mel to waveform
- multi-period discriminator
- multi-scale discriminator

See:

- [models.py](/Users/hisham/Code/Bahraini_TTS/external/hifi-gan/models.py#L75)
- [train.py](/Users/hisham/Code/Bahraini_TTS/external/hifi-gan/train.py#L24)

It also already uses DDP-style training patterns, which is useful for our future trainer design.

### CAMeL Tools is useful, but only as a utility layer

It gives us normalization and dediacritization helpers, but it is not a Bahraini G2P.

See:

- [normalize.py](/Users/hisham/Code/Bahraini_TTS/external/camel_tools/camel_tools/utils/normalize.py#L48)
- [dediac.py](/Users/hisham/Code/Bahraini_TTS/external/camel_tools/camel_tools/utils/dediac.py#L56)

Important caution:

- some normalizations collapse distinctions we may want to preserve for pronunciation
- we should not blindly normalize away all orthographic variation

## Decisions We Must Make Before Writing The First Real Training File

- Choose target sample rate for v1: likely `22050` or `24000`
- Choose mel config for both acoustic model and vocoder
- Choose phoneme inventory
- Choose transcript normalization policy
- Choose single-speaker or multi-speaker metadata format
- Choose alignment bootstrap plan
- Choose whether pitch and energy are phoneme-level or frame-level
- Choose whether we start with a minimal trainer or adapt an existing one

## Recommended V1 Defaults

These are my recommended defaults unless the data pushes us elsewhere.

- Single speaker only
- `22050 Hz` sample rate
- `80` mel bins
- `1024` FFT / `256` hop as the first baseline
- phoneme-level duration, pitch, and energy supervision
- separate training for acoustic model and vocoder
- lexicon-first front end with rules as fallback

These line up with:

- [preprocess.yaml](/Users/hisham/Code/Bahraini_TTS/external/FastSpeech2/config/LJSpeech/preprocess.yaml#L9)
- [model.yaml](/Users/hisham/Code/Bahraini_TTS/external/FastSpeech2/config/LJSpeech/model.yaml#L1)
- [config_v1.json](/Users/hisham/Code/Bahraini_TTS/external/hifi-gan/config_v1.json#L11)

## What You Should Read First

This is the shortest useful reading path.

### 1. Understand the acoustic model

Read:

- [fastspeech2.py](/Users/hisham/Code/Bahraini_TTS/external/FastSpeech2/model/fastspeech2.py)
- [modules.py](/Users/hisham/Code/Bahraini_TTS/external/FastSpeech2/model/modules.py)

Goal:

- understand exactly how text-side states become mel frames

### 2. Understand preprocessing assumptions

Read:

- [preprocessor.py](/Users/hisham/Code/Bahraini_TTS/external/FastSpeech2/preprocessor/preprocessor.py)

Goal:

- understand what files must exist before training starts
- understand how duration, pitch, energy, and mel are generated

### 3. Understand the vocoder boundary

Read:

- [models.py](/Users/hisham/Code/Bahraini_TTS/external/hifi-gan/models.py)
- [train.py](/Users/hisham/Code/Bahraini_TTS/external/hifi-gan/train.py)

Goal:

- understand what the acoustic model must output for the vocoder

### 4. Understand alignment expectations

Read:

- [alignment_example.md](/Users/hisham/Code/Bahraini_TTS/external/Montreal-Forced-Aligner/docs/source/first_steps/alignment_example.md)

Goal:

- understand why OOV words and bad dictionaries break alignments

### 5. Understand safe Arabic normalization utilities

Read:

- [normalize.py](/Users/hisham/Code/Bahraini_TTS/external/camel_tools/camel_tools/utils/normalize.py)
- [dediac.py](/Users/hisham/Code/Bahraini_TTS/external/camel_tools/camel_tools/utils/dediac.py)

Goal:

- understand what can be reused versus what must stay Bahraini-specific

## Execution Checklist

### Phase 0: Scope Lock

- [ ] Confirm v1 is single speaker
- [ ] Confirm v1 is Bahraini-only, not general Arabic
- [ ] Confirm v1 target is low-latency batch synthesis, not true streaming

### Phase 1: Data Audit

- [ ] Inventory all available Bahraini speech data
- [ ] Measure total hours
- [ ] Check recording consistency and background noise
- [ ] Check transcript availability and quality
- [ ] Identify code-switch frequency
- [ ] Decide train / val / test split policy

### Phase 2: Front-End Definition

- [ ] Define normalization policy
- [ ] Define phoneme inventory
- [ ] Define pronunciation lexicon format
- [ ] Define fallback G2P rules
- [ ] Define code-switch handling rules
- [ ] Define punctuation and number expansion rules

### Phase 3: Corpus And Alignment

- [ ] Define raw corpus folder structure
- [ ] Define utterance metadata manifest format
- [ ] Create `.lab` or equivalent text files for each utterance
- [ ] Build starter pronunciation dictionary
- [ ] Run alignment experiments
- [ ] Inspect alignment failures and OOVs
- [ ] Iterate on the lexicon until durations are usable

### Phase 4: Preprocessing Pipeline

- [ ] Implement Bahraini-specific text normalization module
- [ ] Implement phoneme conversion module
- [ ] Extract mel, pitch, energy, and duration targets
- [ ] Save normalized stats and manifests
- [ ] Verify one utterance end to end by hand

### Phase 5: Acoustic Model

- [ ] Create our own model config
- [ ] Port or reimplement FastSpeech 2 structure cleanly
- [ ] Write dataset loader for our manifests
- [ ] Write training loop
- [ ] Decide whether to use DDP immediately or add it after baseline training
- [ ] Train a first overfit-small-batch sanity check

### Phase 6: Vocoder

- [ ] Train HiFi-GAN on Bahraini mel/audio pairs
- [ ] Confirm mel config matches acoustic model exactly
- [ ] Evaluate reconstruction quality on held-out audio
- [ ] Keep BigVGAN as optional comparison, not day-one scope

### Phase 7: Integration

- [ ] Connect front end to acoustic model
- [ ] Connect acoustic model to vocoder
- [ ] Run end-to-end inference on curated sample texts
- [ ] Check pronunciation, prosody, and latency

### Phase 8: Evaluation

- [ ] Build a representative Bahraini test sentence set
- [ ] Evaluate pronunciation accuracy
- [ ] Evaluate naturalness
- [ ] Evaluate latency
- [ ] Track common failure cases

## What I Need You To Decide Soon

- Do we already have Bahraini recordings?
- If yes, where are they and what format are they in?
- Do we want to commit to a phoneme-based front end, or are you still considering grapheme input?
- Do you want the first implementation to prioritize simplicity over DDP?

## The Main Strategic Point

We should not begin by writing a giant training script.

We should begin by fixing the representation problem:

text -> normalized text -> phonemes -> aligned durations

If that layer is weak, the rest of the stack will look broken even when the neural code is fine.
