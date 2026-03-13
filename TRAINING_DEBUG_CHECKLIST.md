# Training Debug Checklist

Use this when rerunning training on the remote server. The goal is not just to train again. The goal is to bring back enough evidence to identify the failure mode.

## What To Save

- model name and repo name
- git commit or branch
- full training command
- full config file
- dataset size in hours
- number of training samples
- speaker count
- sample rate
- text normalization/transcript format

## What To Log During Training

- train loss by step
- eval loss by step
- learning rate by step
- checkpoint save steps
- any warnings about tokenizer, NaNs, skipped batches, missing files, or bad text

## What Audio To Export

Use the same fixed text prompts every time.

- 5 simple sentences
- 5 Bahraini-heavy sentences
- 3 very short prompts like `hello`, `شلونك`, `كيف الحال`

Export these at:

- before fine-tuning if possible
- early checkpoint
- middle checkpoint
- late checkpoint
- best checkpoint by eval, if available
- final checkpoint

## What To Bring Back Here

- training script
- config file
- exact launch command
- console log or log file
- train/eval loss curves or raw values
- the fixed prompt outputs from several checkpoints
- one example transcript from the dataset
- one matching audio clip for that transcript

## Minimum Comparison Matrix

For one rerun, try to compare:

1. early checkpoint audio
2. middle checkpoint audio
3. late checkpoint audio
4. best eval checkpoint audio

If early is better than late, that strongly suggests instability or overfitting.

## Questions We Need To Answer

- does the model improve at all before it collapses?
- does eval loss agree with audio quality?
- do simple phrases fail too, or only Bahraini phrases?
- does the model drift away from intelligibility with more steps?
- is the text format exactly what the model expects?
- is Arabic tokenization/normalization consistent?

## Short Paste Template

When you come back from the server, paste this:

```text
Model:
Repo/commit:
Train command:
Config:
Hours of data:
Number of samples:
Speaker count:
Sample rate:
Text format:

Best checkpoint:
Final checkpoint:

Observed behavior:
- Early:
- Middle:
- Late:

Loss behavior:
- Train:
- Eval:

Warnings/errors:

Attached files:
- config
- train script
- logs
- sample outputs
```
