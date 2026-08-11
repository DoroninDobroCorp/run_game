PYTHON ?= python3

IOS_DIR := ios/RunGameFounder
SIMULATOR ?= platform=iOS Simulator,name=iPhone 16 Pro,OS=18.5
R02_FIXTURE ?= research/r02/local/valparaiso_central
R02_IOS_RESOURCES ?= $(IOS_DIR)/Resources/Local
R02_AUDIO_MANIFEST := $(R02_IOS_RESOURCES)/m01_solo_founder_30min.manifest.json

.PHONY: ios-prepare ios-open ios-build ios-unit-test ios-ui-test ios-test test-asan test-tsan r02-doctor r02-audit-privacy r02-preflight r02-audio-qa r02-validate-evidence r02-analyze-gpx verify-synthetic verify-pretest verify py-compile ast-cross-contract r02-story-validate strict-ab-validate r02-evidence-validate negative-smoke-test r03-synthetic-validate r04-unset-reject

ios-prepare: r02-preflight
	cd $(IOS_DIR) && xcodegen generate

ios-open: ios-prepare
	open $(IOS_DIR)/RunGameFounder.xcodeproj

ios-build: ios-prepare
	xcodebuild -project $(IOS_DIR)/RunGameFounder.xcodeproj -scheme RunGameFounder -destination '$(SIMULATOR)' -derivedDataPath $(IOS_DIR)/DerivedData build

ios-unit-test: ios-prepare
	xcodebuild -project $(IOS_DIR)/RunGameFounder.xcodeproj -scheme RunGameFounder -destination '$(SIMULATOR)' -derivedDataPath $(IOS_DIR)/DerivedData -parallel-testing-enabled NO -only-testing:RunGameFounderTests test

ios-ui-test: ios-prepare
	xcodebuild -project $(IOS_DIR)/RunGameFounder.xcodeproj -scheme RunGameFounder -destination '$(SIMULATOR)' -derivedDataPath $(IOS_DIR)/DerivedData -parallel-testing-enabled NO -only-testing:RunGameFounderUITests test

ios-test: ios-unit-test ios-ui-test

test-asan:
	@if command -v xcodebuild >/dev/null 2>&1; then \
		$(MAKE) ios-prepare && \
		if ! xcodebuild -showdestinations -project $(IOS_DIR)/RunGameFounder.xcodeproj -scheme RunGameFounder 2>&1 | grep -q "iPhone 16 Pro"; then \
			echo "UNSUPPORTED: Simulator destination '$(SIMULATOR)' is unavailable on this system"; \
			exit 0; \
		fi; \
		xcodebuild -project $(IOS_DIR)/RunGameFounder.xcodeproj -scheme RunGameFounder -destination '$(SIMULATOR)' -derivedDataPath $(IOS_DIR)/DerivedData -parallel-testing-enabled NO -enableAddressSanitizer YES -only-testing:RunGameFounderTests test; \
	else \
		echo "UNSUPPORTED: xcodebuild is unavailable on this system"; \
		exit 0; \
	fi

test-tsan:
	@if command -v xcodebuild >/dev/null 2>&1; then \
		$(MAKE) ios-prepare && \
		if ! xcodebuild -showdestinations -project $(IOS_DIR)/RunGameFounder.xcodeproj -scheme RunGameFounder 2>&1 | grep -q "iPhone 16 Pro"; then \
			echo "UNSUPPORTED: Simulator destination '$(SIMULATOR)' is unavailable on this system"; \
			exit 0; \
		fi; \
		xcodebuild -project $(IOS_DIR)/RunGameFounder.xcodeproj -scheme RunGameFounder -destination '$(SIMULATOR)' -derivedDataPath $(IOS_DIR)/DerivedData -parallel-testing-enabled NO -enableThreadSanitizer YES -only-testing:RunGameFounderTests test; \
	else \
		echo "UNSUPPORTED: xcodebuild is unavailable on this system"; \
		exit 0; \
	fi

r02-doctor:
	$(PYTHON) tools/r02_doctor.py --strict

r02-audit-privacy:
	$(PYTHON) tools/r02_audit_privacy.py

r02-preflight:
	$(PYTHON) tools/r02_prepare_ios.py --fixture-dir $(R02_FIXTURE) --output-dir $(R02_IOS_RESOURCES)
	$(PYTHON) tools/r02_preflight.py --fixture-dir $(R02_FIXTURE) --ios-resources-dir $(R02_IOS_RESOURCES)

r02-audio-qa:
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

verify-pretest: r02-doctor r02-audit-privacy r02-preflight r02-audio-qa py-compile ast-cross-contract r02-story-validate strict-ab-validate r02-evidence-validate negative-smoke-test r03-synthetic-validate r04-unset-reject verify-synthetic ios-build ios-test test-asan test-tsan

verify: r02-preflight
	$(PYTHON) tools/r02_story.py validate
	$(PYTHON) tools/r02_verify_field.py --audio-dir $(R02_FIXTURE)/audio
	$(PYTHON) -m unittest discover -s tests -p 'test_*.py' -v
