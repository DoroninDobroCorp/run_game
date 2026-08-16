#!/usr/bin/env python3

from __future__ import annotations

import unittest
from unittest.mock import patch

from tools import r02_resolve_simulator


class R02ResolveSimulatorTests(unittest.TestCase):
    def test_prefers_booted_iphone_even_when_newer_runtime_exists(self) -> None:
        payload = {
            "devices": {
                "com.apple.CoreSimulator.SimRuntime.iOS-18-5": [
                    {"name": "iPhone 16 Pro", "udid": "BOOTED", "state": "Booted", "isAvailable": True}
                ],
                "com.apple.CoreSimulator.SimRuntime.iOS-26-0": [
                    {"name": "iPhone 17 Pro", "udid": "NEWER", "state": "Shutdown", "isAvailable": True}
                ],
            }
        }
        self.assertEqual(
            r02_resolve_simulator.resolve_from_simctl(payload),
            "platform=iOS Simulator,id=BOOTED",
        )

    def test_chooses_latest_available_iphone_when_none_is_booted(self) -> None:
        payload = {
            "devices": {
                "com.apple.CoreSimulator.SimRuntime.iOS-18-5": [
                    {"name": "iPhone 16 Pro", "udid": "OLD", "state": "Shutdown", "isAvailable": True}
                ],
                "com.apple.CoreSimulator.SimRuntime.iOS-26-0": [
                    {"name": "iPhone 17 Pro", "udid": "LATEST", "state": "Shutdown", "isAvailable": True}
                ],
            }
        }
        self.assertEqual(
            r02_resolve_simulator.resolve_from_simctl(payload),
            "platform=iOS Simulator,id=LATEST",
        )

    def test_falls_back_when_simctl_is_unavailable(self) -> None:
        with patch("subprocess.run", side_effect=FileNotFoundError):
            self.assertEqual(r02_resolve_simulator.resolve(), r02_resolve_simulator.FALLBACK_DESTINATION)


if __name__ == "__main__":
    unittest.main()
