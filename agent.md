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
- Current focus: correctness is now validated through `concurrency=4` in the `concurrent` path; the next step is replacing coarse `T3` serialization with a scheduler or finer stepping model.
- Next architectural step: improve `T3` scheduling first, then reassess how much of the remaining bottleneck belongs to `S3`.
- Main risks: mistaking restored correctness for real scalability, skipping throughput analysis after the coarse `T3` lock, or changing the speech-token path too early.

## File Map

- [skills/diagram-html-skill.md](/Users/hisham/Code/Bahraini_TTS/skills/diagram-html-skill.md): plain guide for creating self-contained HTML diagrams
- [skills/researcher-context-skill.md](/Users/hisham/Code/Bahraini_TTS/skills/researcher-context-skill.md): plain guide for context-first research memos tied to the current codebase
- [CONTEXT.md](/Users/hisham/Code/Bahraini_TTS/CONTEXT.md): project architecture and scope
- [PROGRESS.md](/Users/hisham/Code/Bahraini_TTS/PROGRESS.md): status and open questions
- [CHATTERBOX_SCALING_PLAN.md](/Users/hisham/Code/Bahraini_TTS/CHATTERBOX_SCALING_PLAN.md): current execution direction for scaling work
- [chatterbox_serving_shape_current_vs_target.html](/Users/hisham/Code/Bahraini_TTS/architecture/chatterbox_serving_shape_current_vs_target.html): self-contained engineering diagram for current flow, traced tensor shapes, concurrency hazards, validated concurrent checkpoint, and target concurrent redesign
- [CLOUD_GPU_QUICKSTART.md](/Users/hisham/Code/Bahraini_TTS/CLOUD_GPU_QUICKSTART.md): required-only GPU setup and baseline-vs-streaming run commands
- [cosyvoice_v1_linear_parallel_breakdown.md](/Users/hisham/Code/Bahraini_TTS/architecture/cosyvoice_v1_linear_parallel_breakdown.md): focused CozyVoice step-by-step and parallelism analysis
- [t3_concurrent_inference_findings.md](/Users/hisham/Code/Bahraini_TTS/architecture/t3_concurrent_inference_findings.md): focused T3 concurrent-inference hazard review and architecture recommendation
- [t3_serving_research_memo.md](/Users/hisham/Code/Bahraini_TTS/architecture/t3_serving_research_memo.md): focused research memo on whether shared-instance `prefill + step + scheduler` serving is already solved in TTS
- [t3_speculative_decoding_research_memo.md](/Users/hisham/Code/Bahraini_TTS/architecture/t3_speculative_decoding_research_memo.md): focused research memo on whether speculative decoding is a good fit for the current multilingual `T3` architecture
- [t3_hydra_dataset_adaptation_plan.md](/Users/hisham/Code/Bahraini_TTS/architecture/t3_hydra_dataset_adaptation_plan.md): exact plan for reusing the current `Medusa` distill dataset as a `Hydra` starting corpus, including what must be added for planner-side supervision and which `T3` shape validations must remain fixed
- [t3_planner_rearchitecture_prior_art_memo.md](/Users/hisham/Code/Bahraini_TTS/architecture/t3_planner_rearchitecture_prior_art_memo.md): focused prior-art memo on replacing only the planner while keeping the downstream renderer fixed or mostly fixed
- [s3_origin_story.html](/Users/hisham/Code/Bahraini_TTS/architecture/s3_origin_story.html): lightweight visual explainer for the S3 lineage and current architecture
- [References/speculative_decoding/README.md](/Users/hisham/Code/Bahraini_TTS/References/speculative_decoding/README.md): local primary-source bundle for speculative-decoding papers and supporting docs
- [References/planner_rearchitecture/README.md](/Users/hisham/Code/Bahraini_TTS/References/planner_rearchitecture/README.md): local primary-source bundle for planner-only and stage-local TTS re-architecture work
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
- I also created [t3_concurrent_inference_findings.md](/Users/hisham/Code/Bahraini_TTS/architecture/t3_concurrent_inference_findings.md) after tracing the current Chatterbox `T3` concurrency failure.
- Main result: the first correctness blocker is shared mutable `T3` inference state, especially request-local backend state stored on `self` and persistent forward hooks on shared transformer layers.
- I also created [t3_serving_research_memo.md](/Users/hisham/Code/Bahraini_TTS/architecture/t3_serving_research_memo.md) after checking whether this serving problem is already solved elsewhere.
- Main result: the closest existing TTS-side solutions already adapt `LLM` serving engines like `vLLM` and `SGLang`, so the right next move for Chatterbox `T3` is adaptation of that design, not inventing the scheduler pattern from scratch.
- I also created [t3_speculative_decoding_research_memo.md](/Users/hisham/Code/Bahraini_TTS/architecture/t3_speculative_decoding_research_memo.md) after checking whether speculative decoding is a good next architecture candidate for multilingual `T3`.
- Main result: speculative decoding looks promising here, but only if we train or obtain a verifier-compatible smaller multilingual draft `T3`; `Chatterbox Turbo` is useful as a speed reference, not as a drop-in draft/verifier pair.
- I also created [t3_planner_rearchitecture_prior_art_memo.md](/Users/hisham/Code/Bahraini_TTS/architecture/t3_planner_rearchitecture_prior_art_memo.md) after checking whether people already replace only the planner while leaving the downstream renderer intact.
- Main result: yes in broad form, especially in `SPEAR-TTS`, `VALL-E 2`, `VALL-E R`, `MaskGCT`, and `SoundStorm`; but an open-source multilingual `T3-only` swap into an existing `T3 -> S3` contract still looks relatively open.
- I also created [t3_hydra_dataset_adaptation_plan.md](/Users/hisham/Code/Bahraini_TTS/architecture/t3_hydra_dataset_adaptation_plan.md) after checking whether the current `Medusa` distill dataset can be reused for `Hydra`.
- Main result: yes as the base teacher corpus, no as a drop-in Hydra dataset; the next clean step is a `T3`-native Hydra builder that preserves the current JSONL corpus and adds planner-side hidden-state supervision plus shape checks tied to the traced `T3` contract.

## Update Rules

- Update [understand.md](/Users/hisham/Code/Bahraini_TTS/understand.md) when HM clearly understands or decides something important.
- Update [PROGRESS.md](/Users/hisham/Code/Bahraini_TTS/PROGRESS.md) when project state changes materially.
- Update [CONTEXT.md](/Users/hisham/Code/Bahraini_TTS/CONTEXT.md), [CHATTERBOX_SCALING_PLAN.md](/Users/hisham/Code/Bahraini_TTS/CHATTERBOX_SCALING_PLAN.md), and other relevant `.md` files when research clarifies architecture, lineage, bottlenecks, or decisions.
- Do not leave completed work only in your terminal output; record the result in the shared docs so another agent can pick it up without repeating the work.
- Keep updates brief and factual.
