# R03 Consent & Privacy Verification Checklist

## Stage Status: NOT_STARTED (Offline Scaffolding & Synthetic Evaluation Only)

This checklist establishes mandatory privacy, data minimization, consent, and pseudonymous ID invariants for all current synthetic tools and future R03 field evaluations of narrative audio conditioning.

---

## 1. Informed Consent Protocols
- [ ] **Voluntary Participation**: Participant explicitly opts in prior to allocation or audio session start.
- [ ] **Withdrawal Rights**: Clear, immediate right to stop or abort session at any time without data penalty.
- [ ] **Scope Transparency**: Explicit disclosure that evaluation measures next-workout habit formation, audio experience perception, and place recall.

## 2. Pseudonymization & Identity Safety
- [ ] **Pseudonymous Participant ID**: Local non-PII UUID generated on device (`participant_id`).
- [ ] **Zero PII Storage**: Never collect or persist names, email addresses, phone numbers, or account credentials.
- [ ] **Zero PII Export**: Automated JSON export schemas disallow PII fields or personal contact info.

## 3. Location & GPS Data Minimization
- [ ] **No Raw Coordinates in Journal/Debrief**: Active run journals and debrief JSON records store exact partial GPX track basenames (`partialGPXBasename`), never raw coordinate arrays or lat/lon pairs.
- [ ] **Aggregated Traversal Summary**: Only non-sensitive summary metrics (total distance, duration, elevation delta, average pace) are computed locally and exported.
- [ ] **Local GPS File Quarantine**: Any GPX files created for audio transition anchoring remain strictly local on device and are never committed to git repositories or remote servers.

## 4. Audio Data Privacy
- [ ] **No Unsanctioned Voice Recording**: Debriefs use structured Likert/count UI inputs or explicit localized audio captures without continuous ambient listening.
- [ ] **Master Audio Durability**: Master audio assets are SHA-256 verified locally (`17aece84537542363fc4950f82ff73355b2c8db70497e3b6121b7ecf3239eb22`).

## 5. Automated Privacy Fail-Closed Auditing
- [ ] **Real Data Leak Pattern Guards**: Analysis scripts (`tools/r03_analyze.py`) run regular expressions checking for email, phone, and raw coordinate patterns, failing closed if detected.
- [ ] **Strict JSON Verification**: `load_strict_json` rejects duplicate keys, non-finite floats, and invalid schemas.
- [ ] **Synthetic Dataset Isolation**: All synthetic fixtures (`synthetic_fixture.json`) are tagged `synthetic: true` with `dataset_type: "synthetic_ab_trial"`.

---
*Verification Tooling*: `python3 tools/r02_doctor.py --strict`, `python3 tools/r03_analyze.py`, `python3 tools/r02_audit_privacy.py`.
