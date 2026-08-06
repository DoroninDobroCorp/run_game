.PHONY: ios-prepare ios-open ios-build ios-unit-test ios-ui-test ios-test verify

IOS_DIR := ios/RunGameFounder
SIMULATOR := platform=iOS Simulator,name=iPhone 16 Pro,OS=18.5

ios-prepare:
	python3 tools/r02_prepare_ios.py
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

verify:
	python3 tools/r02_story.py validate
	python3 tools/r02_verify_field.py
	python3 -m unittest discover -s tests -p 'test_*.py' -v
