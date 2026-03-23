---
name: researcher-context
description: Context-first research workflow tied to the current repo and implementation. Use for research, tradeoff analysis, and compatibility checks.
---

# Researcher Context Skill (Plain Guide)

Purpose:
- Produce a grounded research memo that starts with local repo context, then uses external sources to validate or compare approaches.

Scope:
- Use when the task requires choosing between approaches, validating compatibility, or comparing serving/runtime designs.
- Not for general brainstorming without evidence.

Inputs:
- Local source-of-truth files (current implementation, benchmarks, contracts).
- External sources: official docs, papers, and repos.

Process:
1. Local context sweep:
   - Read the most relevant implementation files first.
   - Extract constraints: shapes, interfaces, config flags, known bottlenecks.
2. Define unknowns and decision criteria:
   - What must be verified externally?
   - What tradeoffs matter most (latency, throughput, risk, compatibility)?
3. External research:
   - Prefer primary sources.
   - Capture versions and dates for time-sensitive claims.
4. Synthesis:
   - Map each option to local constraints.
   - Identify what disappears, what stays custom, and what must be rewritten.
5. Deliverable:
   - Direct answer first.
   - Comparison table.
   - Recommended order and minimal first spike plan.
6. Update repo docs:
   - Record the memo in `PROGRESS.md`.
   - Add any new artifacts to `CONTEXT.md` or relevant tracking files.

Output:
- One detailed `.md` memo in `architecture/`.

Checklist:
- [ ] Local constraints extracted before external research
- [ ] Primary sources cited for key claims
- [ ] Options mapped to the current codebase boundary
- [ ] Recommendation includes a minimal first spike
