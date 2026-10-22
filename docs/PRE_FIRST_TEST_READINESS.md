# Pre-First-Test Readiness

**Date:** October 3, 2026

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
| Git base | `PASS` | Rechecked with `git fetch --all --prune`: every remote tip is contained locally. Before this audit, `155ba62` was 7 commits ahead of `origin/codex/tester-readiness` and 80 ahead of `origin/main`, with none missing locally. |
| Python suite | `PASS_WITH_SKIPS` | `make verify-synthetic`: 271 tests, no failures, 6 skips for unavailable historical private assets. |
| Static analysis | `PASS` | `make quality py-compile`: Ruff, mypy and bytecode compilation pass. |
| Real-bundle iOS runtime | `PASS` | Full iOS 18.5 run: 94 Swift unit tests and 7 UI tests, no failures. New cases cover synchronous GPX-save error callbacks, invalid player/incident times, two saved rehearsals surviving model reload, and pause/navigation/background recovery. Log: ignored `research/r02/local/el_bolson/final-audit-ios-tests.log`. |
| AddressSanitizer | `PASS` | The final audit reran all 94 unit tests with AddressSanitizer, with no test failures or sanitizer errors. Log: `final-audit-asan.log`. |
| ThreadSanitizer | `PREVIOUS_PASS` | The earlier run executed 86 unit tests without failures. This audit does not claim a new ThreadSanitizer run. |
| Live OSM verification | `PASS` | Current street topology, avenue midpoint and full loop match the saved geometry. The CLI verifies source names and shared street nodes; translated UI labels are separate. This is map verification, not field approval. |
| Route and audio integrity | `PASS` | `make el-bolson-prepare`: `READY_FOR_DEVICE_SMOKE`; independent pinned SHA, 1800.0 s, AAC / 44.1 kHz / mono, peak −1.6 dB, no clipping. |
| Offline rehearsal | `PASS_SIMULATED` | Manual completion on iOS 26.2 and UI-automated completion on iOS 18.5: 5/5 waypoints including finish, 8 run intervals, 901 virtual GPS samples. A full-disk save failure recovered after freeing space and retrying; the saved report appeared on the dashboard. The report says `fieldEvidence: false` and `audioPlaybackVerified: false`. |
| Durable evidence queues | `PASS` | Existing queue, recovery, corruption and lock tests still pass. Simulation reports are separated from field evidence and do not create research queues. |
| Rehearsal recovery | `PASS` | Failure injection before writing, before publication and after publication/sync verifies successful retries with one file, retained results and no overwrite of conflicting bytes. UI testing verifies returning to the completed result from the dashboard. |
| Fixture publication | `PASS` | Simulated full-disk and publication failures leave no partial fixture and preserve existing reviews. All four new files are published together. |
| Clean checkout and reproducibility | `PASS` | An isolated Git checkout with current tracked sources and no private fixtures passes 271 Python tests (6 skips) and actually generates a 30-minute synthetic AAC bundle with approvals false. Independent real-bundle preparation, repeated twice, exactly matches the active three-file package. Logs: `final-audit-clean-room.log` and `final-audit-reproducibility.log`. |
| Research validators | `PASS` | Strict A/B checks, synthetic R03 analysis and rejection of unset R04 decisions pass; no real R03/R04 results are asserted. |
| Physical-device compilation | `PREVIOUS_COMPILE_PASS` | The earlier Debug ARM64 build for `generic/platform=iOS` succeeded with `CODE_SIGNING_ALLOWED=NO`. This audit targets Simulator; it does not claim another signed build, install or physical runtime pass. |
| Signing | `DEFERRED_BY_USER` | The user explicitly postponed the real account. The previous attempt found a valid development identity but rejected Xcode login and no provisioning profile. No account authentication was retried during this audit. |
| Physical iPhone smoke | `DEFERRED_BY_USER` | Installation follows account setup later; actual GPS, background recovery, audio and lock-screen controls still require hardware. |
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

Repeat the full standard iOS suite with `make el-bolson-test`. The final audit
used the same unit/UI targets in one `xcodebuild test` invocation with
`COMPILER_INDEX_STORE_ENABLE=NO` to reduce disk usage.

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

During the October 2 recheck, Xcode first reported a missing cached Info.plist task
context. Cleaning this project's derived build cache resolved it; the full
90-unit / 6-UI run passed afterwards. Private route/audio files were
preserved. Static, Python, live-map, audio and privacy logs use the `recheck-`
prefix in the ignored El Bolsón directory.

After the October 2 tests completed, an optional extra manual preview was stopped when
the host had only about 312 MiB free. The QA simulator was shut down and only
this project's regenerable index/module caches were removed. About 502 MiB
remained. The automated UI pass stands; this extra preview is not counted as
another pass. Free host storage before starting another simulator session.

The October 3 audit began with roughly 0.5 GiB free. Compilation disabled index
storage, and available space rose to roughly 2 GiB before the full iOS test run.
The run completed successfully. The audit neither removed private assets nor
changed Apple account settings.
