---
name: diagram-html
description: Create self-contained, grayscale, engineering-style HTML flow diagrams from repo source-of-truth docs.
---

# Diagram HTML Skill

## When To Use

Use this skill when the user asks for:
- Architecture diagrams
- Runtime evolution timelines
- Shape/contract flow boards
- Any “create an HTML board/diagram” request tied to repo docs

## Inputs

Required:
- One or more source-of-truth markdown files in the repo

Optional:
- Code anchors
- Trace output data
- Target HTML filename and location

## Output

Single HTML file:
- Self-contained
- Grayscale palette
- Engineering/diagram style
- Left-to-right flow where applicable
- No external assets

## Procedure

1. Read the requested source-of-truth markdown files.
2. Extract:
   - Current flow/stack/timeline
   - Measured shapes and timings
   - Conclusions and open questions
3. Choose the board type:
   - Flow board (pipeline)
   - Timeline board (evolution)
   - Layer board (stack + options)
4. Build the HTML:
   - Hero: title + 1–2 sentence subtitle
   - Summary cards: 2–4 key takeaways
   - Main visual: pipeline/timeline/stack
   - Tables for shapes/timings
   - Footer: open risks/next step
5. Shapes:
   - Use tuple format `(B, T, D)`
   - Add axis labels only when meanings are explicit in the sources
6. Timings:
   - Use the latest recorded metrics
   - If metrics are from a different GPU, note it in a footnote
7. Keep it concise:
   - Avoid narrative bloat
   - Prefer tables and labeled boxes
8. Update `PROGRESS.md` with a one-line reference to the new HTML file.

## Style Rules

- Grayscale palette only
- No external CSS/JS/assets
- Simple borders, compact typography
- Clear left-to-right flow
- No marketing language

## Sanity Checklist

- [ ] Numbers and shapes match the source docs
- [ ] No stale metrics
- [ ] Board matches user’s requested scope
- [ ] HTML is self-contained
