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

## Multi-Agent Coordination

- HM may run multiple agents in parallel in the same repo.
- Shared `.md` files may change during your session because another agent added context, findings, or decisions.
- Do not assume the first version of a doc you read is still the latest version.
- Before editing shared docs, reread them and preserve useful additions from other agents.
- Treat unexpected doc changes as likely valid teammate context unless they clearly conflict with the task or known facts.
- Prefer additive edits and short handoff notes over large rewrites.
- If HM assigns you an identity like `Agent 1`, keep that identity stable for the session and include it in relevant handoff notes.
- Pick up from where another agent left off when possible instead of restarting from stale assumptions.
- If another agent's note conflicts with your current conclusion, record the conflict clearly instead of silently overwriting it.
- When you finish meaningful work, update the relevant shared `.md` files so the repo reflects the new state and later agents do not redo completed research.
- If you create a new artifact such as a diagram, HTML explainer, benchmark note, or architecture write-up, add it to the relevant `.md` files instead of leaving it undocumented.

## Session Startup

In new sessions, read these files first:

- [agent.md](/Users/hisham/Code/Bahraini_TTS/agent.md)
- [workflow.md](/Users/hisham/Code/Bahraini_TTS/workflow.md)
- [understand.md](/Users/hisham/Code/Bahraini_TTS/understand.md)
- [CONTEXT.md](/Users/hisham/Code/Bahraini_TTS/CONTEXT.md)
- [PROGRESS.md](/Users/hisham/Code/Bahraini_TTS/PROGRESS.md)
- [CHATTERBOX_SCALING_PLAN.md](/Users/hisham/Code/Bahraini_TTS/CHATTERBOX_SCALING_PLAN.md)
- [IMPLEMENTATION_CHECKLIST.md](/Users/hisham/Code/Bahraini_TTS/IMPLEMENTATION_CHECKLIST.md)
- [REFERENCE_REPOS.md](/Users/hisham/Code/Bahraini_TTS/REFERENCE_REPOS.md)

Then:

1. Rebuild the current project state in a few lines.
2. Match the response style to HM's current level of understanding.
3. Continue from the latest open decision, not from generic background.
4. Recheck shared docs if the repo may have changed while you were working.

## Current Project Summary

- Goal: improve the Chatterbox serving shape for streaming concurrency per GPU.
- Current focus: validate the local Layer 1 streaming runtime on a GPU box and compare it against the untouched baseline.
- Next architectural step: only redesign `S3` if the runtime cleanup is still not enough.
- Main risks: mistaking runtime cleanup for a full model fix, skipping baseline measurement, or changing the speech-token path too early.

## File Map

- [CONTEXT.md](/Users/hisham/Code/Bahraini_TTS/CONTEXT.md): project architecture and scope
- [PROGRESS.md](/Users/hisham/Code/Bahraini_TTS/PROGRESS.md): status and open questions
- [CHATTERBOX_SCALING_PLAN.md](/Users/hisham/Code/Bahraini_TTS/CHATTERBOX_SCALING_PLAN.md): current execution direction for scaling work
- [chatterbox_serving_shape_current_vs_target.html](/Users/hisham/Code/Bahraini_TTS/architecture/chatterbox_serving_shape_current_vs_target.html): current vs target serving architecture with code anchors
- [CLOUD_GPU_QUICKSTART.md](/Users/hisham/Code/Bahraini_TTS/CLOUD_GPU_QUICKSTART.md): required-only GPU setup and baseline-vs-streaming run commands
- [cosyvoice_v1_linear_parallel_breakdown.md](/Users/hisham/Code/Bahraini_TTS/architecture/cosyvoice_v1_linear_parallel_breakdown.md): focused CozyVoice step-by-step and parallelism analysis
- [s3_origin_story.html](/Users/hisham/Code/Bahraini_TTS/architecture/s3_origin_story.html): lightweight visual explainer for the S3 lineage and current architecture
- [REFERENCE_REPOS.md](/Users/hisham/Code/Bahraini_TTS/REFERENCE_REPOS.md): upstream references and clone strategy
- [IMPLEMENTATION_CHECKLIST.md](/Users/hisham/Code/Bahraini_TTS/IMPLEMENTATION_CHECKLIST.md): execution checklist and design gaps
- [workflow.md](/Users/hisham/Code/Bahraini_TTS/workflow.md): how discussions and work should flow
- [understand.md](/Users/hisham/Code/Bahraini_TTS/understand.md): tracked HM understanding

## Current Agent Notes

### Agent 1

- I am `Agent 1`.
- HM asked me to hyper-focus on the CozyVoice path and explain exactly how it works step by step, especially what is linear and what can or cannot be parallelized.
- I created [cosyvoice_v1_linear_parallel_breakdown.md](/Users/hisham/Code/Bahraini_TTS/architecture/cosyvoice_v1_linear_parallel_breakdown.md).
- Main result: prompt preprocessing branches can be parallelized and pipeline-overlapped, but the single-utterance path still stays serial at the speech-token LM loop and the mel-level flow solver.

## Update Rules

- Update [understand.md](/Users/hisham/Code/Bahraini_TTS/understand.md) when HM clearly understands or decides something important.
- Update [PROGRESS.md](/Users/hisham/Code/Bahraini_TTS/PROGRESS.md) when project state changes materially.
- Update [CONTEXT.md](/Users/hisham/Code/Bahraini_TTS/CONTEXT.md), [CHATTERBOX_SCALING_PLAN.md](/Users/hisham/Code/Bahraini_TTS/CHATTERBOX_SCALING_PLAN.md), and other relevant `.md` files when research clarifies architecture, lineage, bottlenecks, or decisions.
- Do not leave completed work only in your terminal output; record the result in the shared docs so another agent can pick it up without repeating the work.
- Keep updates brief and factual.
