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
`research/r02/local/`, which is ignored by git. The active fixture is
`local/valparaiso_central/`. A copied `local/santiago_cumming/` directory is an
inactive archive unless the owner explicitly selects it; merely placing it next
to Valparaíso must not change the bundle.

## Commands

```bash
python3 tools/r02_story.py validate
python3 tools/r02_story.py paths
python3 tools/r02_story.py linearize --mission m01 --condition B
python3 tools/r02_verify_geo.py \
  --snapshot research/r02/local/valparaiso_central/osm_snapshot.json
python3 tools/r02_build_master.py \
  --binding research/r02/local/valparaiso_central/current.binding.json \
  --output-dir research/r02/local/valparaiso_central/audio
python3 tools/r02_verify_field.py \
  --audio-dir research/r02/local/valparaiso_central/audio
python3 tools/r02_prepare_ios.py \
  --fixture-dir research/r02/local/valparaiso_central \
  --output-dir ios/RunGameFounder/Resources/Local
python3 tools/r02_preflight.py \
  --fixture-dir research/r02/local/valparaiso_central \
  --ios-resources-dir ios/RunGameFounder/Resources/Local
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

Equivalent bundle command: `make r02-preflight`. Its strongest possible result
is `READY_FOR_DEVICE_SMOKE`: it checks offline integrity and prepared-resource
identity but never grants route, workout, participant, or M1-A approval.

After a real walkthrough, analyze the local GPX offline, with the standard-library
tool and no network calls, without sending the raw trace to an LLM:

```bash
python3 tools/r02_analyze_gpx.py \
  --gpx /absolute/local/path/to/walkthrough.gpx \
  --mission ios/RunGameFounder/Resources/Local/mission.json \
  --manifest ios/RunGameFounder/Resources/Local/m01_solo_founder_30min.manifest.json
```

Or run `make r02-analyze-gpx GPX=/absolute/local/path/to/walkthrough.gpx`.
The JSON output contains only derived geometry and relative timing. It contains
no coordinates, place names, exact start time, or input path and makes no safety
or approval decision. Missing/invalid points, required arrivals, or cues fail
closed with a non-zero exit status.

The active founder fixture is `local/valparaiso_central/`. It remains local and
git-ignored because its binding, audio, route measurements, and run evidence may
contain sensitive location data. OSM identity checks do not imply that a route
is safe or workout-ready; those approvals stay false until the founder performs
the documented daytime walk-through.

The current master is a fixed-time research asset. Its 27 `NAV` events are
workout/run-walk cues, not turn-by-turn route instructions. Geo prose and its
authored fallbacks are present in the script, but the native founder slice does
not select them from live geofences. The first silent walkthrough is therefore
required to measure arrivals and decide whether the master must be retimed and
rebuilt before the run.

Condition A requires a manually approved field binding for participant export.
Draft linearization may retain placeholders; it is not a participant bundle.
