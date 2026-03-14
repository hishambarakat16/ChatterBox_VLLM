# Prompt For A Visual Architecture Agent

Use this prompt with another agent to update the existing left-to-right HTML diagram of the current Chatterbox state flow and the planned concurrency-safe redesign.

```text
Create a single self-contained HTML file that updates the existing Chatterbox multilingual inference diagram to reflect the new validated concurrency results and the next architectural target.

Repo context:
- Root: /Users/hisham/Code/Bahraini_TTS
- State-flow reference: /Users/hisham/Code/Bahraini_TTS/CHATTERBOX_STATE_FLOW.md
- Existing serving-shape visual: /Users/hisham/Code/Bahraini_TTS/architecture/chatterbox_serving_shape_current_vs_target.html
- Concurrency findings: /Users/hisham/Code/Bahraini_TTS/architecture/t3_concurrent_inference_findings.md
- Benchmark results: /Users/hisham/Code/Bahraini_TTS/TRACE_RUN_RESULTS.md

What the HTML should show:

1. A left-to-right pipeline for the current baseline path.
2. Under each box, include:
   - file path
   - main function/class
   - input types/shapes
   - output types/shapes
   - whether the state is shared immutable, per-request mutable, or shared synchronized
3. Highlight the original concurrency breakpoints in red:
   - self.conds in mtl_tts.py
   - self.compiled / self.patched_model in t3.py
   - forward hooks in alignment_stream_analyzer.py
   - batch-size-1 assumption in s3gen.py
4. Show the implemented first-pass fix as a second horizontal lane:
   - request comes in
   - request-local context created
   - coarse T3 decode lock
   - request-local T3 backend
   - request-local alignment analyzer
   - shared S3 worker
   - waveform out
5. Show the long-term target redesign as a third horizontal lane:
   - request comes in
   - request-local context created
   - scheduler queue
   - shared T3 worker
   - per-request decode state
   - shared S3 worker
   - waveform out
6. Make the implemented and target lanes explicitly show:
   - shared weights are reused
   - mutable decode state is per request
   - the current first-pass fix still serializes T3
   - the target design replaces coarse T3 serialization with scheduler-owned active-request stepping
7. Add a compact legend:
   - blue = shared immutable
   - orange = per-request mutable
   - green = scheduler/shared synchronized
   - red = current race hazard / bottleneck
8. Add a compact validated-results panel:
   - `concurrency=2` now works in the `concurrent` path with `errors=[]`
   - both saved `concurrency=2` outputs sounded correct
   - `concurrency=4` also works with `errors=[]`
   - throughput does not scale well because T3 is still effectively queued by the coarse full-decode lock
   - the next blocker is T3 scheduling efficiency, not immediate correctness
9. Make it easy to scan, not artsy. Use precise labels and arrows.

Output requirements:
- One `.html` file only
- No external assets
- Desktop-first but readable on laptop widths
- Update the existing HTML in place instead of creating a redundant second visual
- Put the current path on top, the implemented first-pass fix in the middle, and the longer-term target below it
- Add a small note explaining that:
  - the correctness milestone is achieved
  - the correctness result now holds through `concurrency=4`
  - the next milestone is replacing the coarse T3 lock with a scheduler or finer stepping model
```
