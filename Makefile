PYTHON ?= python3

IOS_DIR := ios/RunGameFounder
SIMULATOR ?= platform=iOS Simulator,name=iPhone 16 Pro,OS=18.5
R02_FIXTURE ?= research/r02/local/valparaiso_central
R02_IOS_RESOURCES ?= $(IOS_DIR)/Resources/Local
R02_AUDIO_MANIFEST := $(R02_IOS_RESOURCES)/m01_solo_founder_30min.manifest.json

.PHONY: ios-prepare ios-open ios-build ios-unit-test ios-ui-test ios-test test-asan test-tsan r02-doctor r02-audit-privacy r02-preflight r02-audio-qa r02-validate-evidence r02-analyze-gpx verify-synthetic verify-pretest verify

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
		xcodebuild -project $(IOS_DIR)/RunGameFounder.xcodeproj -scheme RunGameFounder -destination '$(SIMULATOR)' -derivedDataPath $(IOS_DIR)/DerivedData -parallel-testing-enabled NO -enableAddressSanitizer YES -only-testing:RunGameFounderTests test || { \
			status=$$?; \
			echo "UNSUPPORTED: AddressSanitizer execution failed or is unsupported on destination (exit code $$status)"; \
			exit $$status; \
		}; \
	else \
		echo "UNSUPPORTED: xcodebuild is unavailable on this system"; \
	fi

test-tsan:
	@if command -v xcodebuild >/dev/null 2>&1; then \
		$(MAKE) ios-prepare && \
		xcodebuild -project $(IOS_DIR)/RunGameFounder.xcodeproj -scheme RunGameFounder -destination '$(SIMULATOR)' -derivedDataPath $(IOS_DIR)/DerivedData -parallel-testing-enabled NO -enableThreadSanitizer YES -only-testing:RunGameFounderTests test || { \
			status=$$?; \
			echo "UNSUPPORTED: ThreadSanitizer execution failed or is unsupported on destination (exit code $$status)"; \
			exit $$status; \
		}; \
	else \
		echo "UNSUPPORTED: xcodebuild is unavailable on this system"; \
	fi

r02-doctor:
	$(PYTHON) tools/r02_doctor.py

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

verify-synthetic:
	$(PYTHON) -m unittest discover -s tests -p 'test_*.py' -v

verify-pretest: r02-doctor r02-audit-privacy r02-preflight r02-audio-qa verify-synthetic ios-test

verify: r02-preflight
	$(PYTHON) tools/r02_story.py validate
	$(PYTHON) tools/r02_verify_field.py --audio-dir $(R02_FIXTURE)/audio
	$(PYTHON) -m unittest discover -s tests -p 'test_*.py' -v

