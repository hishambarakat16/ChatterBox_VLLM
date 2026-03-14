# T3 Medusa Distillation Plan

_Last updated: 2026-03-14_

## Direct Answer

For the first Medusa experiment, an Arabic-only distillation dataset is the right scope.

Why:

- the current bottleneck we care about is the Arabic concurrent planner path
- smaller scope means faster dataset creation, faster training, and faster debugging
- we do not need to preserve multilingual quality in the very first Medusa proof-of-concept

Tradeoff:

- an Arabic-only student will not be a multilingual replacement
- that is acceptable for the first paper-quality planner experiment if the goal is to prove planner acceleration on the Arabic path

## Recommended Scope

### First target

- `language_id = ar`
- one fixed prompt voice, or a very small prompt bank
- head-only Medusa training on top of the existing multilingual `T3`

### What stays fixed

- `T3` backbone
- `S3`
- speech-token vocabulary
- BOS/EOS semantics
- conditioning format
- CFG serving path

### What changes

- new future-token heads
- distillation dataset
- training loop for those heads

## Data Source Recommendation

Do not start with OpenAI-generated Arabic prompts.

Start with the local Arabic data already in the repo:

- [metadata.csv](/Users/hisham/Code/Bahraini_TTS/data/speaker_export_SPK_01/metadata.csv)
- [bahraini_conversation_multiturn_gen_single_speaker_cleaned.jsonl](/Users/hisham/Code/Bahraini_TTS/data/bahraini_conversation_multiturn_gen_single_speaker_cleaned.jsonl)
- [bahraini_sft_conversation_gen_single_speaker_cleaned.jsonl](/Users/hisham/Code/Bahraini_TTS/data/bahraini_sft_conversation_gen_single_speaker_cleaned.jsonl)
- [bahraini_sft_conversation_gen_cleaned.jsonl](/Users/hisham/Code/Bahraini_TTS/data/bahraini_sft_conversation_gen_cleaned.jsonl)

Why:

- it already contains `3,352` Arabic transcript rows
- the JSONL files add about `3,053` cleaner synthetic Bahraini Arabic entries
- it is local
- it removes API dependency
- it reflects the domain and spelling noise we are actually dealing with

Synthetic Arabic prompt generation can still be added later if we need more diversity.

Recommended order:

1. start with the cleaned JSONL files for the first manifest because they are likely cleaner
2. supplement with metadata transcript rows if we want more volume or more natural transcription noise

## Dataset Size Recommendation

Use a phased plan.

### Phase 0: smoke test

- `250` samples

Goal:

- verify dataset generation
- verify training code runs
- verify Medusa heads can overfit enough to improve acceptance at all

### Phase 1: pilot

- `1,000` samples

Goal:

- first real benchmark on acceptance and concurrency

### Phase 2: main Arabic experiment

- `3,000` samples

Goal:

- enough data to judge whether Arabic-only Medusa heads are viable

This repo already has enough local Arabic text to reach Phase 2 immediately.

## Distillation Dataset Unit

The correct training unit is not a chat conversation.

It is:

- normalized Arabic text
- language id
- prompt conditioning reference
- teacher speech-token sequence

## Recommended Output Schema

Each sample record should contain:

- `sample_id`
- `text`
- `normalized_text`
- `language_id`
- `audio_prompt_path`
- `conditionals_path`
- `text_tokens`
- `speech_tokens`
- `num_text_tokens`
- `num_speech_tokens`
- `teacher_decode`

Where:

- `text_tokens` are the single logical text-token row with start/stop tokens added
- `speech_tokens` are the teacher-generated target sequence after invalid-token filtering
- `conditionals_path` points to a serialized conditioning bundle that can be reused at training time

## Teacher Generation Policy

For the first distillation set, use deterministic teacher generation.

Recommended:

- `temperature = 0.0`
- `top_p = 1.0`
- `min_p = 0.0`
- `repetition_penalty = 1.0`
- `cfg_weight = 0.5`

Why:

- this makes the teacher targets stable
- it reduces label noise
- it matches the Medusa-style training assumption better than sampling-heavy outputs

## Shape Targets For The Distillation Set

### Stored text tokens

Recommended stored text token shape per sample:

- `(1, T_text)`

These should already include:

- text BOS
- text EOS

Do not store the duplicated CFG rows in the dataset file.

CFG duplication can be reconstructed at training time.

### Stored speech tokens

Recommended stored speech token shape per sample:

- `(1, T_speech)`

These are the teacher targets for Medusa-head training.

## Training Target Alignment

For the first Medusa training recipe:

- base `speech_head` corresponds to token offset `+1`
- Medusa head `0` should predict offset `+2`
- Medusa head `1` should predict offset `+3`
- ...

So the training data only needs:

- current teacher speech-token sequence

The shifted targets can be derived during training.

## Prompt Strategy

For the first dataset, use one fixed prompt audio path.

Why:

- it keeps conditioning stable
- it makes it easier to isolate whether the future-token heads work at all
- it reduces dataset complexity

Later, if the first experiment works, extend to:

- a small prompt bank of `4` to `16` voices

## Scripts Added For This Plan

Text-manifest preparation:

- [prepare_arabic_medusa_manifest.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/prepare_arabic_medusa_manifest.py)

Teacher dataset generation:

- [build_t3_medusa_distill_dataset.py](/Users/hisham/Code/Bahraini_TTS/external/chatterbox/build_t3_medusa_distill_dataset.py)

## Suggested First Commands

### 1. Prepare a clean Arabic manifest

```bash
python external/chatterbox/prepare_arabic_medusa_manifest.py \
  --input-csv data/bahraini_sft_conversation_gen_single_speaker_cleaned.jsonl \
  --output-csv data/arabic_medusa_manifest.csv \
  --limit 1000
```

The same script also accepts:

- metadata CSV input
- multiturn JSONL input
- SFT JSONL input

### 2. Generate the teacher distillation set

```bash
PYTHONPATH=external/chatterbox/src python external/chatterbox/build_t3_medusa_distill_dataset.py \
  --manifest-csv data/arabic_medusa_manifest.csv \
  --audio-prompt-path "$PROMPT_AUDIO" \
  --language-id ar \
  --device cuda \
  --checkpoint-dir /path/to/local/chatterbox/checkpoint \
  --output-dir data/t3_medusa_distill_ar \
  --max-new-tokens 128
```

## What Success Looks Like

For the dataset generation stage:

- no teacher crashes
- valid `text_tokens`
- valid `speech_tokens`
- stable token lengths
- clean JSONL output

For the first training stage:

- Medusa heads learn the future-token shifts
- acceptance improves above the failed layer-subset baseline
- concurrency benchmark improves without changing `S3`

## Bottom Line

Arabic-only first is the right move.

We already have enough local Arabic text to start.
The correct next step is not more theory:

- build a clean Arabic manifest
- generate a deterministic teacher speech-token dataset
- train head-only Medusa heads against that teacher
