# Diagram HTML Skill (Plain Guide)

Purpose:
- Produce concise, engineering-focused HTML flow diagrams that reflect the current repo facts, with trace shapes and measured metrics.

Scope:
- Used for architecture boards, runtime evolution timelines, and flow/shape contract diagrams.
- Outputs a single self-contained HTML file per board.

Inputs:
- One or more source-of-truth markdown files.
- Optional: code anchors for specific modules.
- Optional: trace results with shapes and timings.

Process:
1. Read the source-of-truth markdown file(s).
2. Extract:
   - The current path/flow.
   - The measured shapes.
   - The measured timings.
   - The stated conclusions and next steps.
3. Decide board type:
   - Flow board: left-to-right pipeline with shapes.
   - Evolution board: timeline with deltas per change.
   - Layering board: stack view + options table.
4. Draft the HTML skeleton:
   - Hero section with title + short subtitle.
   - Summary cards with 2–4 key takeaways.
   - Main visual (pipeline/timeline/stack).
   - Tables for shapes/timings where relevant.
   - Footer with “still open” or interpretation note.
5. For shapes:
   - Use tuple format like `(1, 80, 170)`.
   - Append semantic axis labels when the meanings are explicit.
   - Do not guess axis meanings.
6. For timings:
   - Use the most recent measured values from the sources.
   - Note when data is from a different GPU box.
7. Keep the style consistent:
   - Grayscale palette.
   - Clean tables and rectangular boxes.
   - Readable spacing.
   - No external assets.
8. Validate consistency:
   - Shapes and numbers must match the source file.
   - No stale values left over from older runs.
9. Add or update PROGRESS.md with a one-line reference to the new board.

Output:
- One HTML file in `architecture/`.

Style rules:
- Grayscale only.
- No external JS or CSS.
- Use simple shapes, plain borders, and compact text.
- Prefer left-to-right flow.
- Avoid marketing language.

Checklist:
- [ ] Source-of-truth files read.
- [ ] All numbers match source.
- [ ] Flow direction is clear.
- [ ] Shapes are annotated when known.
- [ ] Board referenced in PROGRESS.md.
