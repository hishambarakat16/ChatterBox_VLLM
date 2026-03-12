# Workflow

## Purpose

This file defines how HM and the agent work through ideas and execution.

## Two Loops

### 1. Understanding Loop

Use this when reasoning about architecture, tradeoffs, and concepts.

1. State the current question.
2. Explain the idea briefly.
3. Ask HM to react or explain it back in HM's own words.
4. Validate what HM said.
5. Correct only the missing or wrong part.
6. Log confirmed understanding in [understand.md](/Users/hisham/Code/Bahraini_TTS/understand.md).

### 2. Execution Loop

Use this when turning decisions into repo changes.

1. State the concrete output.
2. Identify the source files or reference repos.
3. Make the smallest useful change.
4. Verify it.
5. Summarize the result.
6. Update the relevant project docs if needed.

## Discussion Rules

- Keep answers short.
- Prefer one core point at a time.
- Tie explanations to actual files.
- If a concept is abstract, point to the exact implementation file.
- If HM seems to skip a point, repeat only that point.
- If HM is clearly driving toward a decision, help narrow the decision.

## Reading Order For This Project

When discussing architecture:

1. [CONTEXT.md](/Users/hisham/Code/Bahraini_TTS/CONTEXT.md)
2. [IMPLEMENTATION_CHECKLIST.md](/Users/hisham/Code/Bahraini_TTS/IMPLEMENTATION_CHECKLIST.md)
3. Relevant reference files in `external/`

When discussing project state:

1. [PROGRESS.md](/Users/hisham/Code/Bahraini_TTS/PROGRESS.md)
2. [understand.md](/Users/hisham/Code/Bahraini_TTS/understand.md)

When discussing upstream sources:

1. [REFERENCE_REPOS.md](/Users/hisham/Code/Bahraini_TTS/REFERENCE_REPOS.md)

## Current Working Order

For this thesis, use this order unless HM redirects:

1. Lock scope.
2. Audit data.
3. Define text and phoneme representation.
4. Prove alignment.
5. Build preprocessing.
6. Build acoustic training.
7. Build vocoder training.
8. Integrate and evaluate.

## What Not To Do

- Do not confuse repo cloning with implementation progress.
- Do not start large code work before the representation layer is clear.
- Do not overload HM with long explanations.
- Do not repeat full context when only one point matters.
- Do not force a rigid plan if HM wants to jump between phases.
