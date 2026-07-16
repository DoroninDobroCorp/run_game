# R02 — narrative proof workspace

This directory contains the smallest executable authoring process for the R02
Wizard-of-Oz narrative proof.

The product assumption is **one persistent home territory per user**. The
founder's current city is only a replaceable research fixture; travel is not a
story mechanic and never enters canonical story state.

## Files

- `tournament/scorecard.json` — the editorial comparison of the three worlds.
- `selection.json` — the provisional universe decision.
- `narrative_graph.v0.1.json` — the complete three-mission authored graph.
- `mission_01_beats.v0.1.json` — the playable M1 cue/script foundation.
- `fixtures/choices.example.json` — one deterministic branch selection.
- `fixtures/field_binding.example.json` — privacy-safe template for the current city.
- `fixtures/field_run.example.json` — pre-run, immediate, and 24-hour founder evidence form.

Exact coordinates, start/end points, GPX, and raw traces belong in
`research/r02/local/`, which is ignored by git.

## Commands

```bash
python3 tools/r02_story.py validate
python3 tools/r02_story.py paths
python3 tools/r02_story.py linearize --mission m01 --condition B
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

Condition A requires a manually approved field binding for participant export.
Draft linearization may retain placeholders; it is not a participant bundle.
