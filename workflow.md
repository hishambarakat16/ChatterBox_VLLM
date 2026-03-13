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

## Multi-Agent Coordination

- Assume shared docs may be changing while you work because HM may have multiple agents running in parallel.
- Before editing a shared `.md` file, reread it.
- Preserve useful notes from other agents unless they are clearly wrong or directly superseded.
- Leave short factual handoff notes instead of rewriting large sections when a small update is enough.
- If HM gave you an agent identity, include it in your handoff note so other agents can follow the trail.
- If you inherit a task from another agent, continue from their latest valid note instead of redoing the whole investigation.
- If two agent notes disagree, surface the disagreement explicitly and tie it to files or code.

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
2. [CHATTERBOX_SCALING_PLAN.md](/Users/hisham/Code/Bahraini_TTS/CHATTERBOX_SCALING_PLAN.md)
3. [cosyvoice_v1_linear_parallel_breakdown.md](/Users/hisham/Code/Bahraini_TTS/architecture/cosyvoice_v1_linear_parallel_breakdown.md) when the discussion is about token-to-mel flow or linear vs parallel decoding
4. Relevant Chatterbox or CozyVoice files in `external/`
5. [IMPLEMENTATION_CHECKLIST.md](/Users/hisham/Code/Bahraini_TTS/IMPLEMENTATION_CHECKLIST.md)

When discussing project state:

1. [PROGRESS.md](/Users/hisham/Code/Bahraini_TTS/PROGRESS.md)
2. [understand.md](/Users/hisham/Code/Bahraini_TTS/understand.md)

When discussing upstream sources:

1. [REFERENCE_REPOS.md](/Users/hisham/Code/Bahraini_TTS/REFERENCE_REPOS.md)

## Current Working Order

For this thesis, use this order unless HM redirects:

1. Benchmark Chatterbox.
2. Isolate runtime bottlenecks.
3. Focus on `S3 token -> mel` scalability work.
4. Decide whether an Arabic-only student is justified.
5. Only then discuss Bahraini specialization.

## What Not To Do

- Do not confuse repo cloning with implementation progress.
- Do not redesign the speech-token interface before profiling the current stack.
- Do not assume your local context is complete if another agent may have updated the docs.
- Do not overload HM with long explanations.
- Do not repeat full context when only one point matters.
- Do not force a rigid plan if HM wants to jump between phases.
