# Pre-First-Test Readiness

**Date:** August 16, 2026

**Phase:** Stage `R02` `IN_PROGRESS`; Stages `R03`/`R04` `NOT_STARTED`

**Branch:** `codex/tester-readiness`

**Overall status:** `ENGINEERING_RC / BLOCKED_ON_PRIVATE_HANDOFF_AND_DEVICE`

**Accepted M4A SHA-256:** `17aece84537542363fc4950f82ff73355b2c8db70497e3b6121b7ecf3239eb22`

This is the current evidence ledger. `PASS` means the named command was run on
this checkout. `COMPILED` is not a runtime-test pass. `BLOCKED` means required
evidence is unavailable, not that the check was waived.

## Readiness matrix

| Lane | Status | Evidence / remaining gate |
| :--- | :--- | :--- |
| Git branch consolidation | `PASS` | All six remote development tips were inspected; they form one linear history and this candidate is based on the newest tip. |
| Python runtime | `PASS` | `/usr/bin/python3` imports `pyexpat`; the broken Homebrew interpreter is no longer the Makefile default. |
| Python suite | `PASS_WITH_SKIPS` | 245 tests pass; 6 master-audio/fixture tests skip because the private bundle is absent. |
| Static analysis | `PASS` | `ruff check tools tests` and `mypy tools` pass with pinned versions in `requirements-dev.txt`. |
| Privacy audit | `PASS` | Five checks cover ignored private paths, tracked raw GPX/private fixtures, scoped JSON coordinates/paths, current secrets, and reachable Git patch history. Public R01 OSM research is explicitly allowlisted. |
| Clean-clone iOS resources | `PASS` | A visibly marked synthetic bundle builds without private data and keeps every human approval false. |
| iOS strict compile | `PASS` | Xcode 26.3 compiles app, 76 unit-test methods and 5 UI-test methods with strict concurrency and warnings-as-errors. |
| iOS runtime suites on this Mac | `NOT_RUN` | Xcode compiles all test targets but the simulator launcher stalls after `Testing started`; the run was canceled after 90 seconds with 0 test methods executed. CI and a second Mac are required. |
| Durable evidence queues | `PASS_AT_COMPILE_AND_SOURCE_TEST_LEVEL` | Queue mutations use write-ahead durable markers, read-back verification, fail-closed relaunch recovery and recoverable quarantine/reset UI. Runtime coverage is present among the 76 compiled Swift methods. |
| Signing portability | `PASS` | Bundle ID and Apple team are parameters; the generated project has no required personal team. |
| CI definition | `BLOCKED_ACCOUNT_BILLING` | Branch push created [Actions run #1](https://github.com/DoroninDobroCorp/run_game/actions/runs/31917107276), but GitHub started neither job because the account is locked by a billing issue. Workflow execution remains required after the owner unlocks Actions. |
| Reconstituted technical inventory | `READY_FOR_VALIDATION` | Original binding/snapshot/AIFF are lost. An ignored replacement fixture preserves the accepted M4A, derives an AIFF and reconstructs route JSON from a retained installed-app projection; its approvals remain false. |
| Accepted master hash | `PASS` | The recovered M4A rehashes to the fixed accepted SHA-256 above. |
| Reconstituted preflight/audio QA | `PENDING_FINAL_RUN` | Run the explicit `R02_FIXTURE=research/r02/local/valparaiso_central_reconstituted_20260821` gates after the final code commit. |
| Private handoff binding | `PENDING_FINAL_RUN` | The handoff manifest must declare `RECONSTITUTED_TECHNICAL_FIXTURE_NOT_FIELD_APPROVED`, reject tampering/wrong Git HEAD and be transferred privately. |
| Physical iPhone smoke | `BLOCKED` | Requires tester hardware, Apple signing, install, map/GPS/recovery/audio checks. |
| Daylight route/workout review | `BLOCKED` | Founder-only field gate; an external QA tester must not approve it. |
| Full lock-screen audio and M1-A | `BLOCKED` | Requires the accepted real master and the founder-only sequence after the route gate. |

## Commands

Clean clone, no private assets:

```bash
/usr/bin/python3 -m pip install -r requirements-dev.txt
make verify-clean-room IOS_DEVELOPMENT_TEAM=""
```

Maintainer, for the reconstituted technical fixture:

```bash
make r02-handoff-verify R02_FIXTURE=research/r02/local/valparaiso_central_reconstituted_20260821 HANDOFF_MANIFEST=/secure/path/RELEASE_MANIFEST.json
make verify-tester-package R02_FIXTURE=research/r02/local/valparaiso_central_reconstituted_20260821 HANDOFF_MANIFEST=/secure/path/RELEASE_MANIFEST.json
```

Create the handoff manifest only from the final clean release commit:

```bash
make r02-handoff-create R02_FIXTURE=research/r02/local/valparaiso_central_reconstituted_20260821 HANDOFF_MANIFEST=/secure/path/RELEASE_MANIFEST.json
```

The five private files and the manifest must be sent through encrypted private
transport. Do not commit them, attach raw GPX to issues, or interpret a
synthetic build as permission for a route test.
