PYTHON ?= /usr/bin/python3

IOS_DIR := ios/RunGameFounder
SIMULATOR ?= $(shell $(PYTHON) tools/r02_resolve_simulator.py)
ALLOW_UNSUPPORTED_SANITIZERS ?= 0
IOS_BUNDLE_ID ?= com.doronindobro.rungame.founder
IOS_DEVELOPMENT_TEAM ?=
R02_FIXTURE ?= research/r02/local/valparaiso_central
R02_IOS_RESOURCES ?= $(IOS_DIR)/Resources/Local
R02_AUDIO_MANIFEST := $(R02_IOS_RESOURCES)/m01_solo_founder_30min.manifest.json

.PHONY: ios-prepare ios-synthetic-prepare ios-open ios-build ios-unit-test ios-ui-test ios-test ios-synthetic-build ios-synthetic-build-for-testing ios-synthetic-unit-test ios-synthetic-ui-test ios-synthetic-test test-asan test-tsan quality r02-doctor r02-audit-privacy r02-preflight r02-synthetic-ios r02-handoff-create r02-handoff-verify r02-recover-cached-assets remote-python-ci r02-audio-qa r02-validate-evidence r02-analyze-gpx verify-synthetic verify-pretest verify-tester-package verify-clean-room verify py-compile ast-cross-contract r02-story-validate strict-ab-validate r02-evidence-validate negative-smoke-test r03-synthetic-validate r04-unset-reject

ios-prepare: r02-preflight
	cd $(IOS_DIR) && RUN_GAME_BUNDLE_ID='$(IOS_BUNDLE_ID)' RUN_GAME_DEVELOPMENT_TEAM='$(IOS_DEVELOPMENT_TEAM)' xcodegen generate

ios-synthetic-prepare: r02-synthetic-ios
	cd $(IOS_DIR) && RUN_GAME_BUNDLE_ID='$(IOS_BUNDLE_ID)' RUN_GAME_DEVELOPMENT_TEAM='$(IOS_DEVELOPMENT_TEAM)' xcodegen generate

ios-open: ios-prepare
	open $(IOS_DIR)/RunGameFounder.xcodeproj

ios-build: ios-prepare
	xcodebuild -project $(IOS_DIR)/RunGameFounder.xcodeproj -scheme RunGameFounder -destination '$(SIMULATOR)' -derivedDataPath $(IOS_DIR)/DerivedData build

ios-unit-test: ios-prepare
	xcodebuild -project $(IOS_DIR)/RunGameFounder.xcodeproj -scheme RunGameFounder -destination '$(SIMULATOR)' -derivedDataPath $(IOS_DIR)/DerivedData -parallel-testing-enabled NO -only-testing:RunGameFounderTests test

ios-ui-test: ios-prepare
	xcodebuild -project $(IOS_DIR)/RunGameFounder.xcodeproj -scheme RunGameFounder -destination '$(SIMULATOR)' -derivedDataPath $(IOS_DIR)/DerivedData -parallel-testing-enabled NO -only-testing:RunGameFounderUITests test

ios-test: ios-unit-test ios-ui-test

ios-synthetic-build: ios-synthetic-prepare
	xcodebuild -project $(IOS_DIR)/RunGameFounder.xcodeproj -scheme RunGameFounder -destination '$(SIMULATOR)' -derivedDataPath $(IOS_DIR)/DerivedData build

ios-synthetic-build-for-testing: ios-synthetic-prepare
	xcodebuild -project $(IOS_DIR)/RunGameFounder.xcodeproj -scheme RunGameFounder -destination '$(SIMULATOR)' -derivedDataPath $(IOS_DIR)/DerivedData -parallel-testing-enabled NO build-for-testing

ios-synthetic-unit-test: ios-synthetic-prepare
	xcodebuild -project $(IOS_DIR)/RunGameFounder.xcodeproj -scheme RunGameFounder -destination '$(SIMULATOR)' -derivedDataPath $(IOS_DIR)/DerivedData -parallel-testing-enabled NO -only-testing:RunGameFounderTests test

ios-synthetic-ui-test: ios-synthetic-prepare
	xcodebuild -project $(IOS_DIR)/RunGameFounder.xcodeproj -scheme RunGameFounder -destination '$(SIMULATOR)' -derivedDataPath $(IOS_DIR)/DerivedData -parallel-testing-enabled NO -only-testing:RunGameFounderUITests test

ios-synthetic-test: ios-synthetic-unit-test ios-synthetic-ui-test

test-asan:
	@if command -v xcodebuild >/dev/null 2>&1; then \
		$(MAKE) ios-prepare && \
		xcodebuild -project $(IOS_DIR)/RunGameFounder.xcodeproj -scheme RunGameFounder -destination '$(SIMULATOR)' -derivedDataPath $(IOS_DIR)/DerivedData -parallel-testing-enabled NO -enableAddressSanitizer YES -only-testing:RunGameFounderTests test; \
	else \
		echo "SKIPPED: xcodebuild is unavailable; AddressSanitizer was not verified"; \
		test "$(ALLOW_UNSUPPORTED_SANITIZERS)" = "1"; \
	fi

test-tsan:
	@if command -v xcodebuild >/dev/null 2>&1; then \
		$(MAKE) ios-prepare && \
		xcodebuild -project $(IOS_DIR)/RunGameFounder.xcodeproj -scheme RunGameFounder -destination '$(SIMULATOR)' -derivedDataPath $(IOS_DIR)/DerivedData -parallel-testing-enabled NO -enableThreadSanitizer YES -only-testing:RunGameFounderTests test; \
	else \
		echo "SKIPPED: xcodebuild is unavailable; ThreadSanitizer was not verified"; \
		test "$(ALLOW_UNSUPPORTED_SANITIZERS)" = "1"; \
	fi

quality:
	@command -v ruff >/dev/null 2>&1 || (echo "BLOCKED: install development requirements with '$(PYTHON) -m pip install -r requirements-dev.txt'" >&2; exit 2)
	@command -v mypy >/dev/null 2>&1 || (echo "BLOCKED: install development requirements with '$(PYTHON) -m pip install -r requirements-dev.txt'" >&2; exit 2)
	ruff check tools tests
	mypy tools

r02-doctor:
	$(PYTHON) tools/r02_doctor.py --strict

r02-audit-privacy:
	$(PYTHON) tools/r02_audit_privacy.py

r02-preflight:
	$(PYTHON) tools/r02_prepare_ios.py --fixture-dir $(R02_FIXTURE) --output-dir $(R02_IOS_RESOURCES)
	$(PYTHON) tools/r02_preflight.py --fixture-dir $(R02_FIXTURE) --ios-resources-dir $(R02_IOS_RESOURCES)

r02-synthetic-ios:
	$(PYTHON) tools/r02_prepare_synthetic_ios.py --output-dir $(R02_IOS_RESOURCES)

r02-handoff-create:
	@test -n "$(HANDOFF_MANIFEST)" || (echo 'Usage: make r02-handoff-create HANDOFF_MANIFEST=/secure/path/RELEASE_MANIFEST.json' >&2; exit 2)
	$(PYTHON) tools/r02_handoff_manifest.py create --fixture-dir $(R02_FIXTURE) --out "$(HANDOFF_MANIFEST)"

r02-handoff-verify:
	@test -n "$(HANDOFF_MANIFEST)" || (echo 'Usage: make r02-handoff-verify HANDOFF_MANIFEST=/secure/path/RELEASE_MANIFEST.json' >&2; exit 2)
	$(PYTHON) tools/r02_handoff_manifest.py verify --fixture-dir $(R02_FIXTURE) --manifest "$(HANDOFF_MANIFEST)"

r02-recover-cached-assets:
	@test -n "$(CACHED_M4A)" && test -n "$(CACHED_MANIFEST)" && test -n "$(R02_RECOVERY_DIR)" || (echo 'Usage: make r02-recover-cached-assets CACHED_M4A=/path/to/m01_solo_founder_30min.m4a CACHED_MANIFEST=/path/to/m01_solo_founder_30min.manifest.json R02_RECOVERY_DIR=research/r02/local/recovered_cache' >&2; exit 2)
	$(PYTHON) tools/r02_recover_cached_assets.py --audio-source "$(CACHED_M4A)" --manifest-source "$(CACHED_MANIFEST)" --output-dir "$(R02_RECOVERY_DIR)"

remote-python-ci:
	tools/r02_remote_python_ci.sh

r02-audio-qa: r02-preflight
	$(PYTHON) tools/r02_audio_qa.py --m4a $(R02_IOS_RESOURCES)/m01_solo_founder_30min.m4a --manifest $(R02_AUDIO_MANIFEST)

r02-validate-evidence:
	@if [ -n "$(EVIDENCE)" ]; then \
		$(PYTHON) tools/r02_validate_evidence.py "$(EVIDENCE)"; \
	elif [ -n "$(IMMEDIATE)" ] && [ -n "$(RECALL)" ]; then \
		$(PYTHON) tools/r02_validate_evidence.py --immediate "$(IMMEDIATE)" --recall "$(RECALL)"; \
	else \
		echo 'Usage: make r02-validate-evidence EVIDENCE=/path/to/evidence.json OR make r02-validate-evidence IMMEDIATE=/path/to/imm.json RECALL=/path/to/rec.json' >&2; \
		exit 2; \
	fi

r02-analyze-gpx:
	@test -n "$(GPX)" || (echo 'Usage: make r02-analyze-gpx GPX=/absolute/local/path/to/track.gpx' >&2; exit 2)
	$(PYTHON) tools/r02_analyze_gpx.py --gpx "$(GPX)" --mission $(R02_IOS_RESOURCES)/mission.json --manifest $(R02_AUDIO_MANIFEST)

py-compile:
	$(PYTHON) -m py_compile tools/*.py tests/*.py

ast-cross-contract:
	$(PYTHON) -m unittest tests/test_cross_contract.py

r02-story-validate:
	$(PYTHON) tools/r02_story.py validate

strict-ab-validate:
	$(PYTHON) -m unittest tests/test_r02_build_master.py tests/test_r02_verify_field.py
	@if [ -f "$(R02_FIXTURE)/audio/m01_solo_founder_30min_condition_b.manifest.json" ]; then \
		$(PYTHON) tools/r02_verify_field.py --manifest $(R02_FIXTURE)/audio/m01_solo_founder_30min.manifest.json --compare-manifest $(R02_FIXTURE)/audio/m01_solo_founder_30min_condition_b.manifest.json; \
	else \
		$(PYTHON) tools/r02_verify_field.py --audio-dir $(R02_FIXTURE)/audio; \
	fi

r02-evidence-validate:
	$(PYTHON) -m unittest tests/test_r02_validate_evidence.py

negative-smoke-test:
	$(PYTHON) -m unittest tests/test_r02_doctor.py tests/test_r02_verify_field.py

r03-synthetic-validate:
	$(PYTHON) tools/r03_analyze.py

r04-unset-reject:
	@! $(PYTHON) tools/r04_validate_decision.py --template research/r04/decision_template.json >/dev/null 2>&1 || (echo "R04 UNSET rejection failed" && exit 1)

verify-synthetic:
	$(PYTHON) -m unittest discover -s tests -p 'test_*.py' -v

verify-pretest: r02-doctor r02-audit-privacy r02-preflight r02-audio-qa quality py-compile ast-cross-contract r02-story-validate strict-ab-validate r02-evidence-validate negative-smoke-test r03-synthetic-validate r04-unset-reject verify-synthetic ios-build ios-test test-asan test-tsan

verify-tester-package: r02-handoff-verify r02-doctor r02-audit-privacy r02-preflight r02-audio-qa ios-build

verify-clean-room: quality py-compile r02-audit-privacy verify-synthetic ios-synthetic-build-for-testing

verify: r02-preflight
	$(PYTHON) tools/r02_story.py validate
	$(PYTHON) tools/r02_verify_field.py --audio-dir $(R02_FIXTURE)/audio
	$(PYTHON) -m unittest discover -s tests -p 'test_*.py' -v
