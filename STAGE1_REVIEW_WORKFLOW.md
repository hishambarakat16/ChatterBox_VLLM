# Stage 1 Review Workflow

## Goal

Build a fast local review tool for pronunciation validation.

The tool should let HM go clip by clip:

- read
- listen
- inspect candidate pronunciation
- accept or edit
- save
- move to next

## Input Format

Current sample folder shape:

- one `metadata.csv`
- one `wavs/` directory
- one row per clip

Example folder:

- [speaker_export_SPK_17](/Users/hisham/Code/Bahraini_TTS/speaker_export_SPK_17)

Observed fields in [metadata.csv](/Users/hisham/Code/Bahraini_TTS/speaker_export_SPK_17/metadata.csv):

- `id`
- `speaker`
- `gender`
- `text`
- `phonetic_text`
- `duration`
- `sampling_rate`
- `original_file`
- `relative_wav_path`

Observed facts from `speaker_export_SPK_17`:

- `3681` clips
- all `phonetic_text` values currently empty
- sample rate is `24000`
- duration range is about `0.4s` to `6.0s`
- many rows contain mixed Arabic and English

## Speaker Question

### Does speaker identity matter?

Yes, but differently for different stages.

### For Stage 1 lexicon and pronunciation review

Speaker identity matters somewhat, but less than for model training.

What matters most here:

- dialect consistency
- transcript quality
- audio clarity
- pronunciation stability

If a speaker folder is somewhat noisy but still mostly the same dialect and mostly understandable, it can still be useful for lexicon building.

### For Stage 2 and Stage 3 training

Speaker identity matters much more.

For acoustic quality, a cleaner single-speaker dataset is strongly preferred for v1.

## Practical Recommendation

For the review UI:

- start with one folder at a time
- prefer cleaner folders first
- do not assume speaker ID is perfectly clean
- allow HM to skip bad clips
- allow marking clips as `bad_audio`, `wrong_speaker`, or `bad_transcript`

So the review tool should help curate data, not just curate pronunciations.

## Core UI Flow

One clip is the main review unit.

For each clip:

1. Show clip metadata
2. Show transcript
3. Tokenize the transcript
4. Generate candidate pronunciation per token
5. Play the source audio
6. Let HM validate at token level
7. Save accepted outputs
8. Move to next clip

## Recommended UI Layout

### Top Section

- selected folder
- clip index
- clip ID
- speaker ID
- duration
- original source path

### Main Section

- transcript text
- normalized transcript
- audio player for the wav clip

### Token Review Table

Each row should represent one token.

Columns:

- token
- normalized token
- token type
- candidate pronunciation
- pronunciation source
- confidence or status
- action

Suggested token types:

- `arabic`
- `english_latin`
- `arabic_script_loanword`
- `number`
- `punctuation`
- `unknown`

Suggested pronunciation sources:

- `lexicon`
- `rule`
- `english_fallback`
- `manual_edit`
- `unknown`

Suggested actions:

- `accept`
- `edit`
- `skip`
- `reject`
- `mark uncertain`

## What Gets Reviewed

Do not force HM to re-approve every repeated token from scratch.

Better logic:

- if token already exists in accepted lexicon, prefill and lock by default
- if token is new, show it for review
- if token was seen before but marked uncertain, show it again
- if same token appears in a suspicious new context, allow review override

This makes the workflow much faster.

## Audio Strategy

Primary validation audio:

- the real source clip from the dataset

Optional later:

- a synthetic proxy preview from a phoneme-capable TTS engine

For now, real source audio is enough to start.

## Saved Outputs

The tool should save at least three artifacts.

### 1. Accepted Lexicon

Suggested file:

- `stage1_outputs/accepted_lexicon.csv`

Suggested columns:

- `token`
- `normalized_token`
- `pronunciation`
- `language_type`
- `source`
- `status`
- `notes`
- `first_clip_id`
- `last_updated`

### 2. Review Log

Suggested file:

- `stage1_outputs/review_log.csv`

Suggested columns:

- `clip_id`
- `token`
- `action`
- `candidate_pronunciation`
- `final_pronunciation`
- `review_status`
- `notes`
- `timestamp`

### 3. Clip Quality Log

Suggested file:

- `stage1_outputs/clip_flags.csv`

Suggested columns:

- `clip_id`
- `flag`
- `notes`

Suggested flags:

- `bad_audio`
- `wrong_speaker`
- `bad_transcript`
- `mixed_speaker`
- `unclear_pronunciation`
- `skip`

## Processing Logic

### Step 1: Load Folder

Input:

- path to one `speaker_export_*` folder

Process:

- load `metadata.csv`
- resolve relative wav paths
- validate files exist

### Step 2: Normalize Text

Apply lightweight normalization only:

- Unicode normalization
- whitespace cleanup
- punctuation cleanup

Do not over-normalize yet.

### Step 3: Tokenize

Split transcript into reviewable tokens.

Important:

- keep punctuation visible
- preserve mixed English tokens
- preserve numbers

### Step 4: Candidate Pronunciation

Per token:

- lexicon lookup first
- Bahraini rule fallback for Arabic tokens
- English fallback for Latin tokens
- mark unknowns for review

### Step 5: Human Review

HM should be able to:

- listen to clip
- inspect token sequence
- accept or edit token pronunciations
- flag bad clips quickly

### Step 6: Save

Persist accepted decisions immediately.

Do not wait until the end of the session to save.

## What To Ignore In V1

- perfect multi-word phrase modeling
- perfect forced alignment at token level
- perfect synthetic pronunciation playback
- full automatic loanword detection

## V1 Scope

Build the smallest useful system:

- one folder input
- clip-by-clip review
- token-level pronunciation acceptance
- save lexicon and logs
- skip bad clips

## Good V1 UX Rules

- keyboard shortcuts for `accept`, `skip`, `next`
- autosave after every action
- show only unresolved tokens by default
- let HM replay audio quickly
- let HM mark a whole clip as unusable in one click

## Recommended Build Order

1. folder loader
2. metadata parser
3. audio playback
4. tokenizer
5. candidate generation stub
6. token review table
7. save accepted lexicon
8. save clip flags
9. fast navigation
