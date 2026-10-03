# Pre-First-Test Readiness

**Date:** October 2, 2026

**Phase:** Stage `R02` `IN_PROGRESS`; Stages `R03`/`R04` `NOT_STARTED`

**Branch:** `codex/el-bolson-finish`

**Overall status:** `LOCAL_TEST_CANDIDATE / DEVICE_AND_FIELD_REVIEW_PENDING`

**Pinned El Bolsón M4A SHA-256:** `4b9572d6807902f053da756a36448cd2277da38622b01d6457f83fdc4eee864e`

The local route starts halfway along Avenida Patagonia Argentina and follows
a 1.91 km closed OSM street loop. The geometry, Russian audio and explicit
simulation are prepared. No physical run or human approval is claimed.

## Readiness matrix

| Lane | Status | Evidence / remaining work |
| :--- | :--- | :--- |
| Git base | `PASS` | After fetch, starting commit `5ffe87a` contained every remote tip and was 73 commits ahead of `origin/main`. |
| Python suite | `PASS_WITH_SKIPS` | `make verify-synthetic`: 262 tests, no failures, 6 skips for unavailable historical private assets. |
| Static analysis | `PASS` | `make quality py-compile`: Ruff, mypy and bytecode compilation pass. |
| Real-bundle iOS runtime | `PASS` | Final `make el-bolson-test` after report-list polish: 86 Swift unit tests and 6 UI tests, no failures. Logs are saved in ignored `research/r02/local/el_bolson/final-ios-tests.log`. |
| Address / Thread Sanitizer | `PASS` | Each sanitizer executes 86 unit tests without failures. |
| Route and audio integrity | `PASS` | `make el-bolson-prepare`: `READY_FOR_DEVICE_SMOKE`; independent pinned SHA, 1800.0 s, AAC / 44.1 kHz / mono, peak −1.6 dB, no clipping. |
| Offline rehearsal | `PASS_SIMULATED` | Manual and UI-automated 30-minute completion: 5/5 waypoints including finish, 8 run intervals, 901 virtual GPS samples. The separate report says `fieldEvidence: false` and `audioPlaybackVerified: false`. |
| Durable evidence queues | `PASS` | Existing queue, recovery, corruption and lock tests still pass. Simulation reports are separated from field evidence and do not create research queues. |
| Research validators | `PASS` | Strict A/B checks, synthetic R03 analysis and rejection of unset R04 decisions pass; no real R03/R04 results are asserted. |
| Signing | `MANUAL` | Choose the owner's Apple Team and connected physical iPhone. |
| Physical iPhone smoke | `PENDING` | GPS, background recovery, audio and lock-screen controls require hardware. |
| Daylight route/workout review | `PENDING` | Surface, crossings, accessibility, grade and actual arrival timing require an on-foot review. All corresponding fixture approvals remain false. |
| Full listening / M1-A | `PENDING` | Home listening and founder field run remain separate from simulation. |
| GitHub Actions | `NOT_RECHECKED` | The historical run was blocked by account billing. Local results do not claim current cloud CI success. |

## Run locally

```sh
make el-bolson-preview
```

Then select **Попробовать маршрут**. See the Russian
[test-run guide](EL_BOLSON_TEST_RUN.md) for map sources, GPX, playback and
physical-device preparation.

For a clean clone without private data, `make verify-clean-room` and
`make ios-synthetic-test` generate a visibly marked synthetic bundle.
Restore the actual route afterwards with `make el-bolson-prepare`.

## Final local package

From a clean release commit, create and verify the ignored local manifest:

```sh
make r02-handoff-create HANDOFF_MANIFEST=research/r02/local/el_bolson/RELEASE_MANIFEST.json
make verify-tester-package HANDOFF_MANIFEST=research/r02/local/el_bolson/RELEASE_MANIFEST.json
```

The manifest binds the exact commit and five private source/audio files.
Its snapshot includes the checksum-protected offline route. GPX and OSM source
are local planning aids, not recorded field evidence. Keep private assets out
of Git. Changing a source file or release commit requires a new manifest.

The original Valparaíso inventory loss and its technical reconstruction are
historical. They do not describe the new El Bolsón package.

The earlier UI rerun interrupted by a full host disk was repeated successfully
after stopping an idle second simulator. The launcher now recognizes renamed
iPhones by their device type and reuses a booted device instead of starting an
unnecessary second runtime. The interruption is resolved, not counted as a pass.
