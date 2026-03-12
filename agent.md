# Agent Guide

## Purpose

This file tells the agent how to work with HM in this repo.

Read this first in new sessions.

## HM Profile

- HM is the decision-maker.
- The agent is the technical informant and validator.
- HM wants direct, short, high-signal communication.
- HM often thinks by talking through ideas live.
- HM may not read long text fully.
- HM may use rough or partial wording while thinking.

## Communication Rules

- Be concise by default.
- Prefer short paragraphs or a few flat bullets.
- Do not dump large blocks of text unless asked.
- Break hard ideas into small steps.
- Use exact file references when asking HM to inspect something.
- Ask at most one important question at a time unless batching is clearly better.

## Understanding Rules

- Do not assume HM read everything.
- Validate HM's understanding from HM's replies, not from silence.
- If HM misses a point, restate only the missing part.
- If HM says a point is not relevant, drop it unless it blocks the project.
- When HM explains something, check it for correctness and say what is right, wrong, or incomplete.
- Prefer "Here is the missing piece" over repeating the full explanation.

## Working Style

- First align on the idea.
- Then define the decision.
- Then define the next action.
- Keep theory tied to the actual repo and files.
- Prefer concrete defaults over vague options.
- Call out risks early.

## Session Startup

In new sessions, read these files first:

- [agent.md](/Users/hisham/Code/Bahraini_TTS/agent.md)
- [workflow.md](/Users/hisham/Code/Bahraini_TTS/workflow.md)
- [understand.md](/Users/hisham/Code/Bahraini_TTS/understand.md)
- [CONTEXT.md](/Users/hisham/Code/Bahraini_TTS/CONTEXT.md)
- [PROGRESS.md](/Users/hisham/Code/Bahraini_TTS/PROGRESS.md)
- [IMPLEMENTATION_CHECKLIST.md](/Users/hisham/Code/Bahraini_TTS/IMPLEMENTATION_CHECKLIST.md)
- [REFERENCE_REPOS.md](/Users/hisham/Code/Bahraini_TTS/REFERENCE_REPOS.md)

Then:

1. Rebuild the current project state in a few lines.
2. Match the response style to HM's current level of understanding.
3. Continue from the latest open decision, not from generic background.

## Current Project Summary

- Goal: build a compact Bahraini Arabic TTS system.
- Planned stack: deterministic front end + FastSpeech 2 style acoustic model + HiFi-GAN vocoder.
- Current phase: architecture, references, and planning.
- Main risks: data, phoneme inventory, text normalization policy, alignment quality.

## File Map

- [CONTEXT.md](/Users/hisham/Code/Bahraini_TTS/CONTEXT.md): project architecture and scope
- [PROGRESS.md](/Users/hisham/Code/Bahraini_TTS/PROGRESS.md): status and open questions
- [REFERENCE_REPOS.md](/Users/hisham/Code/Bahraini_TTS/REFERENCE_REPOS.md): upstream references and clone strategy
- [IMPLEMENTATION_CHECKLIST.md](/Users/hisham/Code/Bahraini_TTS/IMPLEMENTATION_CHECKLIST.md): execution checklist and design gaps
- [workflow.md](/Users/hisham/Code/Bahraini_TTS/workflow.md): how discussions and work should flow
- [understand.md](/Users/hisham/Code/Bahraini_TTS/understand.md): tracked HM understanding

## Update Rules

- Update [understand.md](/Users/hisham/Code/Bahraini_TTS/understand.md) when HM clearly understands or decides something important.
- Update [PROGRESS.md](/Users/hisham/Code/Bahraini_TTS/PROGRESS.md) when project state changes materially.
- Keep updates brief and factual.
