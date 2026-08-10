"""Shared domain threshold constants for Python tools and Swift components.

These thresholds MUST match Swift components (Models.swift, LocationRecorder.swift, MissionRunView.swift)
and Python tools (r02_analyze_gpx.py) exactly.
"""

from __future__ import annotations

# GPS accuracy limits
MAX_EVIDENCE_ACCURACY_M: float = 50.0  # Max mean horizontal accuracy for track evidence
MISSION_START_ACCURACY_M: float = 35.0  # Max horizontal accuracy for initial mission start fix

# Distance limits
START_DISTANCE_LIMIT_M: float = 100.0  # Max distance from public start for mission start fix / walkthrough start
ROUTE_POINT_RADIUS_M: float = 100.0   # Radius around route POIs / arrival radius
MIN_EVIDENCE_DISTANCE_M: float = 200.0  # Minimum required track distance
MAX_START_FINISH_CLOSURE_M: float = 150.0  # Maximum start-to-finish closure distance

# Sample counts & durations
MIN_SAMPLES_PER_ROUTE_POINT: int = 3   # Minimum required samples within radius per route point
MIN_EVIDENCE_SAMPLES: int = 20         # Minimum total accepted GPS samples
MIN_WALKTHROUGH_DURATION_SEC: float = 120.0  # Minimum walkthrough duration
MAX_SAMPLE_GAP_SEC: float = 120.0      # Maximum allowed gap between consecutive GPS samples

# Schema versions
SCHEMA_VERSION_DEBRIEF: str = "0.3"
SCHEMA_VERSION_JOURNAL: str = "0.1"
SCHEMA_VERSION_WALKTHROUGH: str = "0.2"
SCHEMA_VERSION_AUDIO_APPROVAL: str = "0.2"
SCHEMA_VERSION_RECALL: str = "0.2"
