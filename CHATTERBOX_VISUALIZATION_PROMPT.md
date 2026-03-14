# Prompt For A Visual Architecture Agent

Use this prompt with another agent to create a left-to-right HTML diagram of the current Chatterbox state flow and the planned concurrency-safe redesign.

```text
Create a single self-contained HTML file that visualizes the current Chatterbox multilingual inference path and the target concurrency-safe redesign.

Repo context:
- Root: /Users/hisham/Code/Bahraini_TTS
- State-flow reference: /Users/hisham/Code/Bahraini_TTS/CHATTERBOX_STATE_FLOW.md
- Existing serving-shape visual: /Users/hisham/Code/Bahraini_TTS/architecture/chatterbox_serving_shape_current_vs_target.html

What the HTML should show:

1. A left-to-right pipeline for the current baseline path.
2. Under each box, include:
   - file path
   - main function/class
   - input types/shapes
   - output types/shapes
   - whether the state is shared immutable, per-request mutable, or shared synchronized
3. Highlight the concurrency breakpoints in red:
   - self.conds in mtl_tts.py
   - self.compiled / self.patched_model in t3.py
   - forward hooks in alignment_stream_analyzer.py
   - batch-size-1 assumption in s3gen.py
4. Show the target redesign as a second horizontal lane:
   - request comes in
   - request-local context created
   - scheduler queue
   - shared T3 worker
   - per-request decode state
   - shared S3 worker
   - waveform out
5. Make the concurrency-safe lane explicitly show:
   - shared weights are reused
   - mutable decode state is per request
   - scheduler owns active-request batching
6. Add a compact legend:
   - blue = shared immutable
   - orange = per-request mutable
   - green = scheduler/shared synchronized
   - red = current race hazard / bottleneck
7. Make it easy to scan, not artsy. Use precise labels and arrows.

Output requirements:
- One `.html` file only
- No external assets
- Desktop-first but readable on laptop widths
- Put the current path on top and the target path below it
- Add a small note explaining that the immediate milestone is:
  `2 simultaneous correct requests on one shared model instance`
```
