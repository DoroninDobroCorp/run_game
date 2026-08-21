# Run Game — Geo-Narrative Running Companion

> **Human handoff:** Before installing on a physical iPhone, follow
> [`HUMAN_FIRST_IPHONE_SMOKE_TEST.md`](./HUMAN_FIRST_IPHONE_SMOKE_TEST.md).

> **Current Project Phase:** Stage `R02` `IN_PROGRESS`; engineering candidate prepared, a reconstituted technical handoff and physical-device checks pending. Stages `R03`/`R04` are `NOT_STARTED`.
> **Accepted Master Audio SHA-256:** `17aece84537542363fc4950f82ff73355b2c8db70497e3b6121b7ecf3239eb22`
> **Planned Field Fixture:** Valparaíso Central, Chile. The original private fixture is lost; a local, ignored replacement is technical-QA-only and has no field approval.
> **Readiness truth:** clean-clone Python/static/privacy checks and synthetic iOS build pass; local Swift runtime execution is `NOT_RUN` because the Xcode simulator launcher stalls after compilation.

---

## 1. Product Thesis & Boundaries

### Primary Product Thesis
> **Your city becomes the game level:** Run Game builds a Couch-to-5K training route through real physical locations near your starting point and transforms them into scenes of an immersive story that could only happen right here.

### Architectural Rules & Invariants
* **Pre-Compiled Offline Bundles:** Zero live LLM generation or cloud streaming during runs. All route geometry, audio narration, and narrative triggers are pre-compiled into an offline `RouteBundle` prior to workout start.
* **Workout Grid Inviolability:** Beginner training intervals (Couch to 5K) take absolute priority. Narrative scenes wrap around the workout structure, never modifying physical training intensity or interval durations.
* **Strict Privacy by Default:** Raw GPX coordinates and exact start locations remain strictly local to the device. LLMs receive no raw coordinate traces, and derived research reports strip precise start locations.
* **Home-Territory Product Scope vs. Traveler Founder Research:**
  * **Product Scope:** Home-territory-based. A user develops a single home territory over time. Cross-city continuity and travel mechanics are explicitly out of MVP scope.
  * **Founder Research Scope:** Traveler-based. Current field research uses Valparaíso Central as an interchangeable field fixture without baking temporary cities into narrative canon.

### Explicit Product Boundaries
* **No Production Backend:** Operates entirely offline; no cloud server infrastructure.
* **No Dynamic Cloud TTS:** Master audio is pre-rendered M4A narration.
* **No TestFlight or Public Release:** Current iOS app (`ios/RunGameFounder`) is a local, founder-only research instrument. No public distribution, TestFlight, or multi-user accounts exist.

---

## 2. Hardened R02 Founder Research Instrument

The local iOS slice (`ios/RunGameFounder`) provides a deterministic, offline-first instrument for executing field walkthroughs, GPS-triggered audio playback, lock-screen audio checks, and post-run debriefs for Mission 1 (M1 - "Layer Zero" / *Нулевой слой* universe).

### Key iOS Components
* **`SessionStateMachine`:** Pure, state-driven execution engine managing pre-run validation, countdown, active tracking, audio playback, pause/resume, and mission completion with full state replay test coverage.
* **`ActiveRunJournal`:** Atomic session state persistence ensuring crash recovery and context restoration without data loss.
* **`LocationRecorder`:** GPS filter and distance accumulator with accuracy-gated waypoint matching (`START_DISTANCE_LIMIT_M = 100m`, `ROUTE_POINT_RADIUS_M = 100m`).
* **`FileDurability`:** Fail-safe file writing helpers using atomic temporary writes and `.withoutOverwriting` protection.

---

## 3. Technical Tooling & Tool Chain

The repository includes a Python-based utility suite in `tools/` for preflight verification, audio inspection, privacy auditing, GPX analysis, evidence locking, synthetic experimentation, and demand evaluation.

| Tool | Path | Purpose |
| :--- | :--- | :--- |
| **Pre-Test Doctor** | `tools/r02_doctor.py` | Reports environment/tool availability and validates the exact private fixture inventory; `make quality` performs static checks. |
| **Privacy Audit** | `tools/r02_audit_privacy.py` | Scans tracked files, JSON outputs, and git history for coordinate leaks, personal identifiers, or API keys. |
| **Offline Preflight** | `tools/r02_preflight.py` | Verifies route bundle integrity, audio file presence, manifest checksums, and iOS resource alignment. |
| **Audio QA Probe** | `tools/r02_audio_qa.py` | Validates master audio format (AAC/44.1kHz mono), exact 30-min duration (1800.0s), peak levels (-1.6dB), and SHA-256 fingerprint (`17aece84537542363fc4950f82ff73355b2c8db70497e3b6121b7ecf3239eb22`). |
| **Offline GPX Analyzer** | `tools/r02_analyze_gpx.py` | Derives distance, pace, bounding box, and POI arrival timestamps from raw GPX tracks without saving raw coordinates in public artifacts. |
| **Evidence Validator** | `tools/r02_validate_evidence.py` | Enforces fail-closed evidence locking rules (`evidenceCaptureLocked = true`) until all pending queues and human gates pass. |
| **iOS Resource Sync** | `tools/r02_prepare_ios.py` | Packages research fixtures (`research/r02/local/valparaiso_central`) into iOS bundle resources (`ios/RunGameFounder/Resources/Local`). |
| **Synthetic iOS Bundle** | `tools/r02_prepare_synthetic_ios.py` | Creates a visibly marked, fail-closed bundle for clean-clone compilation and CI only; it is forbidden for field use. |
| **Private Handoff Manifest** | `tools/r02_handoff_manifest.py` | Binds the five private files and accepted audio hash to one full release commit without placing private data in Git. |
| **Story Authoring** | `tools/r02_story.py` | Validates authoring graph nodes, clue setups, and deterministic linearization for the M1 narrative. |
| **Synthetic R03 Engine** | `tools/r03_analyze.py` | Executes offline statistical analysis and metric simulation for synthetic A/B trial data against `research/r03/preregistration.v0.1.json`. |
| **R04 Decision Template** | `research/r04/decision_template.md` | Decision-ready framework for preorder / deposit demand evaluation (`G0_DEMAND`) with explicit spend stop-loss and conversion rules. |

---

## 4. Cross-Language Contracts & Thresholds

Physical limits and validation constants are strictly synchronized between Python tools and Swift components via `tools/domain_thresholds.py`:

```python
# Shared Domain Constants (tools/domain_thresholds.py <-> Swift Models.swift)
MAX_EVIDENCE_ACCURACY_M = 50.0       # Max mean horizontal accuracy for track evidence (m)
MISSION_START_ACCURACY_M = 35.0      # Max accuracy required for mission start fix (m)
START_DISTANCE_LIMIT_M = 100.0       # Max distance from public start to begin mission (m)
ROUTE_POINT_RADIUS_M = 100.0         # Arrival radius around POI waypoints (m)
MIN_EVIDENCE_DISTANCE_M = 200.0      # Minimum required total track distance (m)
MAX_START_FINISH_CLOSURE_M = 150.0   # Maximum start-to-finish closure distance (m)
MIN_SAMPLES_PER_ROUTE_POINT = 3      # Required GPS samples inside POI radius
MIN_EVIDENCE_SAMPLES = 20            # Minimum accepted GPS samples per track
MIN_WALKTHROUGH_DURATION_SEC = 120.0 # Minimum duration for valid walkthrough (s)
MAX_SAMPLE_GAP_SEC = 120.0           # Maximum allowed gap between GPS fixes (s)
```

Verified automatically via `tests/test_cross_contract.py`.

---

## 5. Synthetic R03 Analysis & R04 Demand Framework

### Synthetic R03 Analysis Harness
* **Preregistration Spec:** `research/r03/preregistration.v0.1.json` defines primary KPIs (Narrative Immersion Index, Completion Rate) and statistical testing protocols.
* **Offline Analysis Engine:** `tools/r03_analyze.py` computes sample size requirements, effect size estimation, and confidence intervals on synthetic A/B trial datasets.
* **Test Suite:** Fully tested via `tests/test_r03_analyze.py`.

### R04 Decision-Ready Demand Template
* **Template Spec:** `research/r04/decision_template.md` specifies refundable deposit / preorder smoke test rules for the demand gate (`G0_DEMAND`).
* **Fail-Closed Guardrails:** Requires explicit founder sign-off on ad spend stop-loss, qualified visitor criteria, and deposit conversion targets (all parameters initialized to `UNSET`) **prior** to any landing page publication or marketing spend.

---

## 6. How to Run Tests & Verification Commands

All project verification workflows are accessible via `Makefile` targets:

### Core Verification Targets
```bash
# Install pinned static-analysis tools
/usr/bin/python3 -m pip install -r requirements-dev.txt

# Clean-clone verification without private field assets
make verify-clean-room

# Full maintainer verification; requires the real private Valparaíso bundle
make verify-pretest

# Run Pre-Test Environment Doctor
make r02-doctor

# Run Privacy & Security Audit
make r02-audit-privacy

# Run Preflight Bundle & Asset Checks
make r02-preflight

# Run Python Unit Tests & Synthetic Harness (245 tests; 6 asset-dependent skips here)
make verify-synthetic

# Run iOS Unit & UI Tests with the explicitly marked synthetic bundle
make ios-synthetic-test IOS_DEVELOPMENT_TEAM=""

# Validate the exact real tester package before device installation
make verify-tester-package HANDOFF_MANIFEST=/secure/path/RELEASE_MANIFEST.json
```

### Specialized Field Tools
```bash
# Validate Field Evidence JSON File
make r02-validate-evidence EVIDENCE=/absolute/path/to/evidence.json

# Analyze Raw GPX Track (Leads to derived privacy-safe report)
make r02-analyze-gpx GPX=/absolute/path/to/track.gpx

# Audio File Inspection & Quality Check
make r02-audio-qa
```

---

## 7. Fail-Closed Human Safety & Approval Gates

The engineering candidate is intentionally not declared field-ready on this checkout. `make verify-pretest` and `make verify-tester-package` require the missing private Valparaíso source bundle, and physical field testing remains governed by fail-closed human approval gates:

1. **Human Route Approval (`binding.human_route_approved`):** Requires physical daylight walkthrough of the Valparaíso Central route by the founder.
2. **Workout Approval (`binding.workout_approved`):** Requires physical verification of Couch-to-5K interval timing safety and ground conditions.
3. **M1-A Human Approval (`binding.human_approved`):** Requires explicit founder confirmation following route and workout approval.
4. **Public Start Confirmation (`binding.public_start`):** Requires physical check of starting location accessibility and GPS visibility.
5. **Lock-Screen Audio Review:** Requires full 30-minute listening test of master audio on physical iPhone hardware with screen locked.

---

## 8. Documentation Index

For detailed specifications and historical logs, consult the `docs/` directory:

* [`docs/PRE_FIRST_TEST_READINESS.md`](./docs/PRE_FIRST_TEST_READINESS.md) — Master 18-lane readiness matrix and test summary.
* [`docs/EXECUTION_STATUS.md`](./docs/EXECUTION_STATUS.md) — Single source of truth for phase progress, gates, and decision log.
* [`TESTER_HANDOFF.md`](./TESTER_HANDOFF.md) — Release cover sheet, external-QA scope and severity rules.
* [`HUMAN_FIRST_IPHONE_SMOKE_TEST.md`](./HUMAN_FIRST_IPHONE_SMOKE_TEST.md) — Exact manifest-bound first-device smoke protocol.
* [`docs/GEO_NARRATIVE_PRODUCT_STRATEGY.md`](./docs/GEO_NARRATIVE_PRODUCT_STRATEGY.md) — Product vision, investment gates, and core constraints.
* [`docs/R02_FOUNDER_IPHONE_TEST_GUIDE.md`](./docs/R02_FOUNDER_IPHONE_TEST_GUIDE.md) — Protocol for physical iPhone walkthrough and field execution.
* [`docs/GEO_NARRATIVE_TECHNICAL_SPEC.md`](./docs/GEO_NARRATIVE_TECHNICAL_SPEC.md) — System design and technical kill criteria.
* [`research/r04/decision_template.md`](./research/r04/decision_template.md) — R04 demand test template and decision matrix.
