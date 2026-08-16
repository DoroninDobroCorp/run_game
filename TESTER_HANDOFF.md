# Tester handoff cover sheet

Use this page as the release cover sheet. The executable protocol is
[`HUMAN_FIRST_IPHONE_SMOKE_TEST.md`](HUMAN_FIRST_IPHONE_SMOKE_TEST.md).

## Release fields — owner fills before sending

```text
Release commit (full SHA): BLOCKED
CI run URL/result: BLOCKED
RELEASE_MANIFEST.json: BLOCKED
Private bundle transferred with encryption: BLOCKED
make r02-handoff-verify: BLOCKED
make verify-pretest: BLOCKED
make verify-tester-package: BLOCKED
Physical iPhone/model/iOS assigned: BLOCKED
Apple Team + unique QA bundle ID assigned: BLOCKED
```

These fields are deliberately `BLOCKED` in Git. They are evidence from the
final commit, private transfer and tester hardware, so they must not be
pre-filled or inferred from an earlier run.

## Proven on the engineering checkout

- 245 Python tests pass; 6 real-asset tests skip because the private fixture is
  absent.
- `ruff`, `mypy`, Python compile and the five-part privacy/history audit pass.
- The synthetic iOS app and all test targets compile under Xcode 26.3 with 76
  unit-test methods and 5 UI-test methods.
- Swift runtime execution is `NOT_RUN` locally: Xcode's simulator launcher
  stalled after compilation and executed 0 test methods.
- Pending evidence queue mutations now use durable transaction markers,
  fail-closed relaunch recovery and explicit quarantine/reset handling.

## Scope for external QA

External QA may test clone/bootstrap, manifest checks, build/install, launch,
layout/accessibility, map preview, diagnostic GPS/background recovery, audio
controls, interruption behavior and queue persistence. External QA must not:

- perform the Valparaíso route or exercise for the purpose of this research;
- set route, workout, public-start or M1 human approvals;
- treat synthetic resources as field data;
- upload raw GPX, private fixture files or screenshots containing coordinates;
- erase corruption/quarantine evidence before reporting it.

## Severity and report format

- `S0 STOP`: safety/privacy breach, wrong/private asset exposure, unexpected M1
  unlock, evidence loss or unrecoverable corruption.
- `S1 BLOCKER`: cannot install/launch, preflight/hash failure, crash, map 4/4,
  GPS recovery or lock-screen audio failure.
- `S2 MAJOR`: important flow/accessibility/relaunch defect with a workaround.
- `S3 MINOR`: visual/copy issue with no evidence or safety impact.

Every report must include the full release commit, device/OS/Xcode, first
failing step, exact error and privacy-safe media. One issue should describe one
reproducible defect. Never attach raw GPX or the private bundle.
