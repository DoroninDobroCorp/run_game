#!/usr/bin/env python3
"""r02_doctor.py: Environment readiness and pre-test verification tool.

Inspects Python version, OS platform, git status, local fixture availability,
audio probes (afinfo/ffprobe), Xcode, xcodegen, and simulators without mutations.
Outputs machine-readable JSON status (PASS/WARN/BLOCKED).
"""

from __future__ import annotations

import argparse
import json
import platform
from pathlib import Path
import subprocess
import sys
from typing import Any

import os
import shutil

ROOT = Path(__file__).resolve().parents[1]

EXPECTED_MASTER_SHA256 = "17aece84537542363fc4950f82ff73355b2c8db70497e3b6121b7ecf3239eb22"
DEFAULT_FIXTURE = ROOT / "research/r02/local/valparaiso_central"
DEFAULT_IOS_RESOURCES = ROOT / "ios/RunGameFounder/Resources/Local"
DEFAULT_PROJECT_YML = ROOT / "ios/RunGameFounder/project.yml"


def inspect_python() -> dict[str, Any]:
    executable = os.environ.get("PYTHON") or sys.executable
    version = platform.python_version()
    major, minor = sys.version_info[:2]

    pyexpat_ok = False
    pyexpat_error = None
    try:
        import pyexpat
        parser = pyexpat.ParserCreate()
        parser.Parse(b"<xml/>", True)
        pyexpat_ok = True
    except Exception as exc:
        pyexpat_ok = False
        pyexpat_error = str(exc)

    ok = (major, minor) >= (3, 8) and pyexpat_ok
    status = "PASS" if ok else "BLOCKED"

    detail = f"Python {version} ({executable})"
    if not pyexpat_ok:
        detail += f" - pyexpat XML parsing failed: {pyexpat_error}"

    return {
        "status": status,
        "detail": detail,
        "version": version,
        "executable": executable,
        "pyexpat_ok": pyexpat_ok,
        "pyexpat_error": pyexpat_error,
    }


def inspect_tools() -> dict[str, Any]:
    tools_status: dict[str, str] = {}
    for tool_name in ("ruff", "mypy"):
        path = shutil.which(tool_name)
        if path:
            try:
                res = subprocess.run([tool_name, "--version"], capture_output=True, text=True, timeout=5)
                tools_status[tool_name] = "PASS" if res.returncode == 0 else "FAIL"
            except Exception:
                tools_status[tool_name] = "FAIL"
        else:
            tools_status[tool_name] = "NOT_INSTALLED"

    return {
        "status": "PASS",
        "detail": f"ruff: {tools_status.get('ruff')}, mypy: {tools_status.get('mypy')}",
        "tools": tools_status,
    }


def inspect_platform() -> dict[str, Any]:
    system = platform.system()
    machine = platform.machine()
    release = platform.release()
    is_mac = system == "Darwin"
    return {
        "status": "PASS" if is_mac else "WARN",
        "detail": f"{system} {release} ({machine})",
        "system": system,
        "machine": machine,
        "release": release,
    }


def inspect_git() -> dict[str, Any]:
    try:
        res = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            cwd=ROOT,
            timeout=10,
        )
        if res.returncode != 0:
            return {"status": "WARN", "detail": f"git status exited with code {res.returncode}"}
        lines = [line for line in res.stdout.splitlines() if line.strip()]
        branch_res = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            cwd=ROOT,
            timeout=10,
        )
        branch = branch_res.stdout.strip() if branch_res.returncode == 0 else "unknown"
        status = "PASS" if not lines else "WARN"
        detail = f"Branch '{branch}', {len(lines)} uncommitted change(s)" if lines else f"Branch '{branch}', clean working tree"
        return {
            "status": status,
            "detail": detail,
            "branch": branch,
            "uncommitted_count": len(lines),
        }
    except Exception as exc:
        return {"status": "WARN", "detail": f"Git inspection failed: {exc}"}


def inspect_local_fixtures(fixture_dir: Path, ios_resources_dir: Path) -> dict[str, Any]:
    fixture_exists = fixture_dir.is_dir()
    ios_resources_exist = ios_resources_dir.is_dir()

    missing = []
    if not fixture_exists:
        missing.append(f"fixture_dir ({fixture_dir.name})")
    if not ios_resources_exist:
        missing.append(f"ios_resources_dir ({ios_resources_dir.name})")

    if missing:
        return {
            "status": "WARN",
            "detail": f"Missing optional local fixtures: {', '.join(missing)}",
            "fixture_dir_exists": fixture_exists,
            "ios_resources_dir_exists": ios_resources_exist,
            "m4a_exists": False,
            "manifest_exists": False,
            "mission_exists": False,
            "master_audio_sha": None,
            "master_audio_sha_matches": False,
        }

    # Check for expected resources
    m4a_path = ios_resources_dir / "m01_solo_founder_30min.m4a"
    if not m4a_path.is_file():
        alt_m4a = fixture_dir / "audio/m01_solo_founder_30min.m4a"
        if alt_m4a.is_file():
            m4a_path = alt_m4a

    manifest_path = ios_resources_dir / "m01_solo_founder_30min.manifest.json"
    mission_path = ios_resources_dir / "mission.json"

    import hashlib
    m4a_sha = None
    master_sha_matches = False
    if m4a_path.is_file():
        digest = hashlib.sha256()
        with m4a_path.open("rb") as f:
            while chunk := f.read(65536):
                digest.update(chunk)
        m4a_sha = digest.hexdigest()
        master_sha_matches = (m4a_sha == EXPECTED_MASTER_SHA256)

    files_ok = m4a_path.is_file() and manifest_path.is_file() and mission_path.is_file() and master_sha_matches
    status = "PASS" if files_ok else "WARN"
    detail = "All iOS local resources present and master audio SHA verified" if files_ok else "Some iOS local resource files missing or master audio SHA mismatch"

    return {
        "status": status,
        "detail": detail,
        "fixture_dir_exists": fixture_exists,
        "ios_resources_dir_exists": ios_resources_exist,
        "m4a_exists": m4a_path.is_file(),
        "manifest_exists": manifest_path.is_file(),
        "mission_exists": mission_path.is_file(),
        "master_audio_sha": m4a_sha,
        "master_audio_sha_matches": master_sha_matches,
    }


def inspect_audio_probes() -> dict[str, Any]:
    has_afinfo = False
    has_ffprobe = False

    try:
        res = subprocess.run(["afinfo", "-h"], capture_output=True, timeout=5)
        has_afinfo = (res.returncode == 0 or res.returncode == 1)
    except Exception:
        has_afinfo = False

    try:
        res = subprocess.run(["ffprobe", "-version"], capture_output=True, timeout=5)
        has_ffprobe = (res.returncode == 0)
    except Exception:
        has_ffprobe = False

    if has_afinfo and has_ffprobe:
        status = "PASS"
        detail = "Both afinfo and ffprobe available"
    elif has_afinfo or has_ffprobe:
        status = "PASS"
        tool_name = "afinfo" if has_afinfo else "ffprobe"
        detail = f"Audio probe available via {tool_name}"
    else:
        status = "WARN"
        detail = "Neither afinfo nor ffprobe found in PATH"

    return {
        "status": status,
        "detail": detail,
        "has_afinfo": has_afinfo,
        "has_ffprobe": has_ffprobe,
    }


def inspect_xcode() -> dict[str, Any]:
    try:
        res = subprocess.run(["xcodebuild", "-version"], capture_output=True, text=True, timeout=10)
        if res.returncode == 0:
            lines = res.stdout.strip().splitlines()
            xcode_ver = lines[0] if lines else "Xcode present"
            return {
                "status": "PASS",
                "detail": xcode_ver,
                "version": xcode_ver,
            }
        else:
            return {
                "status": "BLOCKED",
                "detail": f"xcodebuild failed with exit code {res.returncode}",
            }
    except Exception as exc:
        return {
            "status": "BLOCKED",
            "detail": f"xcodebuild not found or failed: {exc}",
        }


def inspect_xcodegen() -> dict[str, Any]:
    has_project_yml = DEFAULT_PROJECT_YML.is_file()
    try:
        res = subprocess.run(["xcodegen", "--version"], capture_output=True, text=True, timeout=10)
        if res.returncode == 0:
            version = res.stdout.strip()
            return {
                "status": "PASS" if has_project_yml else "WARN",
                "detail": f"xcodegen {version} (project.yml {'present' if has_project_yml else 'missing'})",
                "version": version,
                "project_yml_exists": has_project_yml,
            }
        else:
            return {
                "status": "WARN",
                "detail": f"xcodegen exited with code {res.returncode}",
                "project_yml_exists": has_project_yml,
            }
    except Exception as exc:
        return {
            "status": "WARN",
            "detail": f"xcodegen tool not found in PATH: {exc}",
            "project_yml_exists": has_project_yml,
        }


def inspect_simulators() -> dict[str, Any]:
    try:
        res = subprocess.run(["xcrun", "simctl", "list", "devices", "available", "--json"], capture_output=True, text=True, timeout=15)
        if res.returncode != 0:
            return {
                "status": "WARN",
                "detail": f"simctl list devices failed with code {res.returncode}",
            }
        data = json.loads(res.stdout)
        devices = data.get("devices", {})
        total_available = 0
        ios_devices = 0
        for runtime, dev_list in devices.items():
            for dev in dev_list:
                if dev.get("isAvailable", False):
                    total_available += 1
                    if "iOS" in runtime:
                        ios_devices += 1
        if ios_devices > 0:
            return {
                "status": "PASS",
                "detail": f"{ios_devices} iOS simulator(s) available",
                "ios_simulators": ios_devices,
                "total_available": total_available,
            }
        elif total_available > 0:
            return {
                "status": "WARN",
                "detail": f"{total_available} total simulator(s) available, 0 iOS simulators",
                "ios_simulators": 0,
                "total_available": total_available,
            }
        else:
            return {
                "status": "WARN",
                "detail": "No available simulators found",
                "ios_simulators": 0,
                "total_available": 0,
            }
    except Exception as exc:
        return {
            "status": "WARN",
            "detail": f"Simulator inspection failed: {exc}",
        }


def diagnose(
    fixture_dir: Path = DEFAULT_FIXTURE,
    ios_resources_dir: Path = DEFAULT_IOS_RESOURCES,
) -> dict[str, Any]:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import tools.r02_audit_privacy as r02_audit_privacy
    inspections = {
        "python": inspect_python(),
        "tools": inspect_tools(),
        "platform": inspect_platform(),
        "git": inspect_git(),
        "local_fixtures": inspect_local_fixtures(fixture_dir, ios_resources_dir),
        "privacy": r02_audit_privacy.audit_all(),
        "audio_probes": inspect_audio_probes(),
        "xcode": inspect_xcode(),
        "xcodegen": inspect_xcodegen(),
        "simulators": inspect_simulators(),
    }

    statuses = [item["status"] for item in inspections.values()]
    if "BLOCKED" in statuses:
        overall_status = "BLOCKED"
    elif "WARN" in statuses:
        overall_status = "WARN"
    else:
        overall_status = "PASS"

    return {
        "schema_version": "0.1",
        "tool": "r02_doctor",
        "status": overall_status,
        "inspections": inspections,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture-dir", type=Path, default=DEFAULT_FIXTURE, help="Path to local fixture directory")
    parser.add_argument("--ios-resources-dir", type=Path, default=DEFAULT_IOS_RESOURCES, help="Path to iOS resources directory")
    parser.add_argument("--out", type=Path, help="Optional output JSON report path")
    parser.add_argument("--strict", action="store_true", help="Return non-zero exit code if status is WARN or BLOCKED")
    args = parser.parse_args(argv)

    report = diagnose(args.fixture_dir, args.ios_resources_dir)
    report_json = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)

    if args.out:
        args.out.write_text(report_json + "\n", encoding="utf-8")

    print(report_json)
    if args.strict:
        return 0 if report["status"] == "PASS" else 1
    return 0 if report["status"] != "BLOCKED" else 1


if __name__ == "__main__":
    sys.exit(main())
