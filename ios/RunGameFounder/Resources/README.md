# Local founder resources

The selected research fixture is currently
`research/r02/local/valparaiso_central/`. Santiago is inactive. From the
repository root, prepare and verify the ignored `Local/` bundle explicitly:

```bash
python3 tools/r02_prepare_ios.py \
  --fixture-dir research/r02/local/valparaiso_central \
  --output-dir ios/RunGameFounder/Resources/Local
python3 tools/r02_preflight.py \
  --fixture-dir research/r02/local/valparaiso_central \
  --ios-resources-dir ios/RunGameFounder/Resources/Local
```

`make r02-preflight` performs the same preparation and integrity preflight before
opening/installing the app. A successful result is only
`READY_FOR_DEVICE_SMOKE`; it is not route safety, workout, audio-listening, or
M1-A approval.

The prepared inventory is exactly `mission.json`, the M4A master, and its
manifest. These files contain exact public research-route coordinates and must
remain ignored/local. Do not commit or broadly share them. Apple Maps preview is
an online Apple service; the app otherwise has no project backend or analytics.
