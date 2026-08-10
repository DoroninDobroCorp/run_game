#!/usr/bin/env python3
"""r02_audit_privacy.py: Enforce privacy and security audit rules.

Fulfills assertion VAL-PRIVACY-001.

Validates:
1. Git-ignored pattern enforcement:
   - research/r02/local/
   - ios/RunGameFounder/Resources/Local/
2. Tracked git file audit:
   - Verifies no tracked files contain raw GPX files or coordinates.
   - Ensures no tracked files match ignored local fixture patterns.
3. Shareable JSON privacy inspection:
   - Verifies shareable JSON files contain zero raw coordinates (latitude, longitude, track_points, etc.).
   - Verifies shareable JSON files contain zero absolute local file paths (e.g. /Users/..., /home/...).
4. API secret / key exposure audit:
   - Scanning repository text files for potential API keys, secret tokens, or private key blocks.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

# Git ignored rules required for local fixtures
REQUIRED_GITIGNORE_PATTERNS = [
    "research/r02/local/",
    "ios/RunGameFounder/Resources/Local/",
]

# Regex patterns for raw coordinate key leakage
LAT_LON_KEY_RE = re.compile(
    r"^(latitude|longitude|lat|lon|lats|lons|coordinates|track_points)$",
    re.IGNORECASE,
)

# Regex pattern for absolute local filesystem path leakage
# Matches Unix/macOS paths starting with /Users/, /home/, /private/, /var/, /tmp/, /Users/...
ABSOLUTE_LOCAL_PATH_RE = re.compile(
    r"(?:/Users/|/home/|/private/|/var/|/tmp/)[a-zA-Z0-9_\-\.\/]+",
    re.IGNORECASE,
)

# Regex patterns for common secret keys / tokens / private keys
SECRET_PATTERNS = [
    (re.compile(r"(?:api[_\-]?key|api[_\-]?secret|access[_\-]?token|secret[_\-]?key)\s*[:=]\s*['\"]([A-Za-z0-9_\-]{16,})['\"]", re.IGNORECASE), "Embedded API Key or Secret"),
    (re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |PRIVATE )?PRIVATE KEY-----"), "Embedded Private Key"),
    (re.compile(r"(?:sk_live_[0-9a-zA-Z]{24,}|ghp_[0-9a-zA-Z]{36}|glpat-[0-9a-zA-Z\-]{20,})"), "Known API Token Format"),
]


def audit_gitignore(root_dir: Path = ROOT) -> dict[str, Any]:
    gitignore_path = root_dir / ".gitignore"
    if not gitignore_path.is_file():
        return {
            "ok": False,
            "status": "FAIL",
            "detail": ".gitignore file missing",
            "missing": REQUIRED_GITIGNORE_PATTERNS,
        }

    content = gitignore_path.read_text(encoding="utf-8")
    lines = [line.strip() for line in content.splitlines()]

    missing = []
    for req in REQUIRED_GITIGNORE_PATTERNS:
        if req not in lines and (req.rstrip("/") not in lines and req + "/" not in lines):
            # Check relaxed match
            if not any(req in line for line in lines):
                missing.append(req)

    ok = len(missing) == 0
    return {
        "ok": ok,
        "status": "PASS" if ok else "FAIL",
        "detail": "All required fixture directories are git-ignored" if ok else f"Missing gitignore entries: {missing}",
        "missing": missing,
    }


def audit_git_tracked_files(root_dir: Path = ROOT) -> dict[str, Any]:
    """Audit tracked git files to verify no raw GPX files, coordinates, or ignored local resources are committed."""
    try:
        res = subprocess.run(
            ["git", "ls-files"],
            capture_output=True,
            text=True,
            cwd=root_dir,
            timeout=10,
        )
        if res.returncode != 0:
            return {"ok": False, "status": "FAIL", "detail": f"git ls-files failed: {res.stderr}"}

        tracked_files = [line.strip() for line in res.stdout.splitlines() if line.strip()]

        leaking_files = []
        for file_str in tracked_files:
            p = Path(file_str)
            # Check 1: Must not be in ignored directories
            if file_str.startswith("research/r02/local/") or file_str.startswith("ios/RunGameFounder/Resources/Local/"):
                leaking_files.append({"file": file_str, "reason": "Ignored local fixture directory tracked in git"})
                continue

            # Check 2: Must not be raw .gpx file
            if p.suffix.lower() == ".gpx":
                leaking_files.append({"file": file_str, "reason": "Raw GPX file tracked in git"})
                continue

        ok = len(leaking_files) == 0
        return {
            "ok": ok,
            "status": "PASS" if ok else "FAIL",
            "detail": f"{len(tracked_files)} tracked files checked, zero raw GPX/fixture leaks found" if ok else f"{len(leaking_files)} privacy violations in tracked files",
            "leaking_files": leaking_files,
        }
    except Exception as exc:
        return {"ok": False, "status": "FAIL", "detail": f"Git tracked files audit error: {exc}"}


def inspect_json_privacy(obj: Any, path: str = "$") -> list[str]:
    """Recursively inspect JSON structures for raw coordinate leakage or absolute local paths."""
    violations: list[str] = []

    if isinstance(obj, dict):
        for key, val in obj.items():
            current_path = f"{path}.{key}"
            if LAT_LON_KEY_RE.match(key):
                if key in {"track", "track_summary"} and isinstance(val, dict):
                    pass
                else:
                    violations.append(f"Forbidden raw coordinate key detected: {current_path}")
            violations.extend(inspect_json_privacy(val, current_path))
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            violations.extend(inspect_json_privacy(item, f"{path}[{idx}]"))
    elif isinstance(obj, str):
        if ABSOLUTE_LOCAL_PATH_RE.search(obj):
            violations.append(f"Forbidden absolute path detected at {path}: {obj!r}")

    return violations


def audit_secrets(root_dir: Path = ROOT) -> dict[str, Any]:
    """Scan tracked codebase files for embedded secrets or API keys."""
    try:
        res = subprocess.run(
            ["git", "ls-files"],
            capture_output=True,
            text=True,
            cwd=root_dir,
            timeout=10,
        )
        if res.returncode != 0:
            return {"ok": False, "status": "FAIL", "detail": f"git ls-files failed: {res.stderr}"}

        tracked_files = [line.strip() for line in res.stdout.splitlines() if line.strip()]
        findings = []

        for rel_path in tracked_files:
            file_path = root_dir / rel_path
            if not file_path.is_file():
                continue
            # Skip binary files or common non-code files if any
            if file_path.suffix.lower() in {".m4a", ".aiff", ".png", ".jpg", ".icns", ".zip"}:
                continue

            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                for pattern, desc in SECRET_PATTERNS:
                    matches = pattern.findall(content)
                    if matches:
                        findings.append({
                            "file": rel_path,
                            "type": desc,
                            "matches": [str(m) for m in matches[:3]],
                        })
            except Exception:
                pass

        ok = len(findings) == 0
        return {
            "ok": ok,
            "status": "PASS" if ok else "FAIL",
            "detail": "Zero embedded API secrets or keys detected" if ok else f"Found {len(findings)} potential secret leakage(s)",
            "findings": findings,
        }
    except Exception as exc:
        return {"ok": False, "status": "FAIL", "detail": f"Secrets audit failed: {exc}"}


def audit_json_files(root_dir: Path = ROOT) -> dict[str, Any]:
    """Audit shareable and tracked R02/R03 JSON files for raw coordinate or local path leakage."""
    try:
        res = subprocess.run(
            ["git", "ls-files", "*.json"],
            capture_output=True,
            text=True,
            cwd=root_dir,
            timeout=10,
        )
        if res.returncode != 0:
            return {"ok": False, "status": "FAIL", "detail": f"git ls-files failed: {res.stderr}"}

        json_files = [line.strip() for line in res.stdout.splitlines() if line.strip()]
        json_violations = []
        audited_count = 0

        for rel_path in json_files:
            # Skip historical R01 frozen research dataset which is documented in R01 memo
            if rel_path.startswith("docs/r01_"):
                continue

            file_path = root_dir / rel_path
            if not file_path.is_file():
                continue

            audited_count += 1
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
                violations = inspect_json_privacy(data)
                if violations:
                    json_violations.append({
                        "file": rel_path,
                        "violations": violations,
                    })
            except Exception as exc:
                json_violations.append({
                    "file": rel_path,
                    "violations": [f"JSON parse error: {exc}"],
                })

        ok = len(json_violations) == 0
        return {
            "ok": ok,
            "status": "PASS" if ok else "FAIL",
            "detail": f"{audited_count} tracked shareable JSON files checked, zero privacy violations found" if ok else f"{len(json_violations)} JSON files failed privacy inspection",
            "json_violations": json_violations,
        }
    except Exception as exc:
        return {"ok": False, "status": "FAIL", "detail": f"JSON privacy audit failed: {exc}"}


def audit_all(root_dir: Path = ROOT) -> dict[str, Any]:
    gitignore_report = audit_gitignore(root_dir)
    git_files_report = audit_git_tracked_files(root_dir)
    json_report = audit_json_files(root_dir)
    secrets_report = audit_secrets(root_dir)

    all_ok = (
        gitignore_report["ok"]
        and git_files_report["ok"]
        and json_report["ok"]
        and secrets_report["ok"]
    )

    return {
        "schema_version": "0.1",
        "tool": "r02_audit_privacy",
        "status": "PASS" if all_ok else "FAIL",
        "ok": all_ok,
        "audits": {
            "gitignore": gitignore_report,
            "git_tracked_files": git_files_report,
            "json_privacy": json_report,
            "secrets": secrets_report,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, help="Optional path to output JSON audit report")
    args = parser.parse_args(argv)

    report = audit_all()
    report_json = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)

    if args.out:
        args.out.write_text(report_json + "\n", encoding="utf-8")

    print(report_json)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
