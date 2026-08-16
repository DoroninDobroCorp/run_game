#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import r02_handoff_manifest


class R02HandoffManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.fixture = Path(self.temp.name) / "fixture"
        for relative_name in r02_handoff_manifest.EXPECTED_FILES:
            path = self.fixture / relative_name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(f"bytes:{relative_name}".encode())
        self.m4a = self.fixture / "audio/m01_solo_founder_30min.m4a"
        self.accepted_sha = r02_handoff_manifest.sha256(self.m4a)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_create_and_verify_exact_private_inventory(self) -> None:
        release_commit = "a" * 40
        with patch.object(r02_handoff_manifest.r02_prepare_ios, "validate_fixture"), patch.object(
            r02_handoff_manifest.r02_doctor,
            "EXPECTED_MASTER_SHA256",
            self.accepted_sha,
        ):
            manifest = r02_handoff_manifest.create_manifest(self.fixture, release_commit)
            manifest_path = Path(self.temp.name) / "RELEASE_MANIFEST.json"
            r02_handoff_manifest.write_manifest(manifest, manifest_path)
            verified = r02_handoff_manifest.verify_manifest(
                self.fixture,
                manifest_path,
                expected_release_commit=release_commit,
            )

        self.assertEqual(verified["release_commit"], release_commit)
        self.assertEqual([entry["path"] for entry in verified["files"]], list(r02_handoff_manifest.EXPECTED_FILES))
        self.assertIs(verified["transport_encryption_verified"], False)
        self.assertNotIn(str(self.fixture), json.dumps(verified))

    def test_verification_rejects_tampered_asset(self) -> None:
        with patch.object(r02_handoff_manifest.r02_prepare_ios, "validate_fixture"), patch.object(
            r02_handoff_manifest.r02_doctor,
            "EXPECTED_MASTER_SHA256",
            self.accepted_sha,
        ):
            manifest = r02_handoff_manifest.create_manifest(self.fixture, "b" * 40)
            manifest_path = Path(self.temp.name) / "RELEASE_MANIFEST.json"
            r02_handoff_manifest.write_manifest(manifest, manifest_path)
            self.m4a.write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError, "inventory/hash mismatch"):
                r02_handoff_manifest.verify_manifest(
                    self.fixture,
                    manifest_path,
                    expected_release_commit="b" * 40,
                )

    def test_create_rejects_unaccepted_master(self) -> None:
        with patch.object(r02_handoff_manifest.r02_prepare_ios, "validate_fixture"), patch.object(
            r02_handoff_manifest.r02_doctor,
            "EXPECTED_MASTER_SHA256",
            "0" * 64,
        ):
            with self.assertRaisesRegex(ValueError, "accepted release SHA-256"):
                r02_handoff_manifest.create_manifest(self.fixture, "c" * 40)

    def test_verification_rejects_wrong_checkout(self) -> None:
        with patch.object(r02_handoff_manifest.r02_prepare_ios, "validate_fixture"), patch.object(
            r02_handoff_manifest.r02_doctor,
            "EXPECTED_MASTER_SHA256",
            self.accepted_sha,
        ):
            manifest = r02_handoff_manifest.create_manifest(self.fixture, "d" * 40)
            manifest_path = Path(self.temp.name) / "RELEASE_MANIFEST.json"
            r02_handoff_manifest.write_manifest(manifest, manifest_path)
            with self.assertRaisesRegex(ValueError, "does not match checked-out HEAD"):
                r02_handoff_manifest.verify_manifest(
                    self.fixture,
                    manifest_path,
                    expected_release_commit="e" * 40,
                )

    def test_default_release_creation_rejects_dirty_worktree(self) -> None:
        with patch.object(r02_handoff_manifest.r02_prepare_ios, "validate_fixture"), patch.object(
            r02_handoff_manifest.r02_doctor,
            "EXPECTED_MASTER_SHA256",
            self.accepted_sha,
        ), patch.object(
            r02_handoff_manifest,
            "_ensure_clean_worktree",
            side_effect=ValueError("dirty Git worktree"),
        ):
            with self.assertRaisesRegex(ValueError, "dirty Git worktree"):
                r02_handoff_manifest.create_manifest(self.fixture)
