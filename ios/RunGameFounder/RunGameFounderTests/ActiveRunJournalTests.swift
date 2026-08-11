import Foundation
import XCTest
@testable import RunGameFounder

final class ActiveRunJournalTests: XCTestCase {
    @MainActor
    func testJournalPersistsMetadataWithoutCoordinates() throws {
        let suiteName = "ActiveRunJournalTests.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suiteName)!
        defer { defaults.removePersistentDomain(forName: suiteName) }

        let docDir = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: docDir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: docDir) }

        let model = AppModel(defaults: defaults, documentsDirectory: docDir)
        let mission = try XCTUnwrap(model.mission)

        let journal = ActiveRunJournal(defaults: defaults, documentsDirectory: docDir)
        XCTAssertNil(journal.currentAttempt)

        let attempt = ActiveRunAttempt(
            schemaVersion: "0.1",
            runID: "test-run-123",
            missionID: mission.missionID,
            bindingID: mission.bindingID,
            audioSHA256: mission.audioSHA256,
            routeWorkoutFingerprint: mission.routeWorkoutFingerprint,
            partialGPXBasename: "test-run-123.partial.gpx",
            condition: "A",
            phase: .running,
            startedAt: Date(),
            pauseCount: 1,
            audioIncidents: ["Audio paused"],
            locationIncidents: []
        )

        try journal.save(attempt)
        XCTAssertNotNil(journal.currentAttempt)

        // Inspect file-backed active_run_journal.json on disk
        XCTAssertTrue(FileManager.default.fileExists(atPath: journal.journalFileURL.path))
        XCTAssertTrue(FileDurability.isExcludedFromBackup(url: journal.journalFileURL))

        let fileData = try Data(contentsOf: journal.journalFileURL)
        let jsonDict = try JSONSerialization.jsonObject(with: fileData) as! [String: Any]

        XCTAssertEqual(jsonDict["run_id"] as? String, "test-run-123")
        XCTAssertEqual(jsonDict["schema_version"] as? String, "0.1")
        XCTAssertEqual(jsonDict["partial_gpx_basename"] as? String, "test-run-123.partial.gpx")
        XCTAssertNil(jsonDict["latitude"])
        XCTAssertNil(jsonDict["longitude"])
        XCTAssertNil(jsonDict["coordinates"])
        XCTAssertNil(jsonDict["track_points"])
        XCTAssertNil(jsonDict["samples"])
        XCTAssertNil(jsonDict["gpx"])
    }

    @MainActor
    func testRelaunchWithActiveJournalRestoresAbortedContextAndLocksEvidence() throws {
        let suiteName = "ActiveRunJournalTests.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suiteName)!
        defer { defaults.removePersistentDomain(forName: suiteName) }

        let docDir = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: docDir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: docDir) }

        let initialModel = AppModel(defaults: defaults, documentsDirectory: docDir)
        let mission = try XCTUnwrap(initialModel.mission)

        // 1. Create an active run attempt in file-backed journal prior to AppModel init
        let attempt = ActiveRunAttempt(
            schemaVersion: "0.1",
            runID: "crashed-run-789",
            missionID: mission.missionID,
            bindingID: mission.bindingID,
            audioSHA256: mission.audioSHA256,
            routeWorkoutFingerprint: mission.routeWorkoutFingerprint,
            partialGPXBasename: "crashed-run-789.partial.gpx",
            condition: "A",
            phase: .running,
            startedAt: Date().addingTimeInterval(-300),
            pauseCount: 0,
            audioIncidents: [],
            locationIncidents: []
        )
        let preJournal = ActiveRunJournal(defaults: defaults, documentsDirectory: docDir)
        try preJournal.save(attempt)
        XCTAssertTrue(FileManager.default.fileExists(atPath: preJournal.journalFileURL.path))

        // 2. Initialize AppModel (simulating app relaunch)
        let model = AppModel(defaults: defaults, documentsDirectory: docDir)

        // 3. Verify evidence lock and restored aborted context
        XCTAssertTrue(model.evidenceCaptureLocked)
        XCTAssertEqual(model.pendingDebriefs.count, 1)

        let restored = try XCTUnwrap(model.pendingDebriefs.first)
        XCTAssertEqual(restored.runID, "crashed-run-789")
        XCTAssertTrue(restored.aborted)
        XCTAssertFalse(restored.completed)
        XCTAssertTrue(restored.abortReason.contains("App relaunch recovery"))

        // 4. Verify active journal file and defaults key were cleared
        XCTAssertFalse(FileManager.default.fileExists(atPath: preJournal.journalFileURL.path))
        XCTAssertNil(defaults.data(forKey: ActiveRunJournal.journalKey))
    }

    @MainActor
    func testCorruptedJournalFailsClosedAndQuarantinesFileWithResetOption() throws {
        let suiteName = "ActiveRunJournalTests.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suiteName)!
        defer { defaults.removePersistentDomain(forName: suiteName) }

        let docDir = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: docDir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: docDir) }

        let journal = ActiveRunJournal(defaults: defaults, documentsDirectory: docDir)
        // Write corrupted data directly to active_run_journal.json
        let corruptedData = Data("corrupted json content".utf8)
        try corruptedData.write(to: journal.journalFileURL)

        let model = AppModel(defaults: defaults, documentsDirectory: docDir)

        XCTAssertTrue(model.evidenceCaptureLocked)
        XCTAssertTrue(model.journalCorrupted)
        XCTAssertNotNil(model.journalErrorBanner)

        // Verify corrupted file was removed from main path and quarantined
        XCTAssertFalse(FileManager.default.fileExists(atPath: journal.journalFileURL.path))
        XCTAssertTrue(FileManager.default.fileExists(atPath: journal.quarantineDirectoryURL.path))
        let files = try FileManager.default.contentsOfDirectory(atPath: journal.quarantineDirectoryURL.path)
        XCTAssertEqual(files.count, 1)
        XCTAssertTrue(files.first?.hasPrefix("corrupted-journal-") == true)

        // Reset quarantine via model UI flow
        model.resetJournalQuarantine()
        XCTAssertFalse(FileManager.default.fileExists(atPath: journal.quarantineDirectoryURL.path))
        XCTAssertFalse(model.journalCorrupted)
        XCTAssertNil(model.journalErrorBanner)
    }

    @MainActor
    func testUnsupportedSchemaVersionJournalRelocatedToQuarantine() throws {
        let suiteName = "ActiveRunJournalTests.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suiteName)!
        defer { defaults.removePersistentDomain(forName: suiteName) }

        let docDir = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: docDir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: docDir) }

        let journal = ActiveRunJournal(defaults: defaults, documentsDirectory: docDir)
        let invalidSchemaAttempt = ActiveRunAttempt(
            schemaVersion: "99.9",
            runID: "invalid-schema-run",
            missionID: "m01",
            bindingID: "b01",
            audioSHA256: "sha256",
            routeWorkoutFingerprint: "fp",
            phase: .running,
            startedAt: Date()
        )
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        let data = try encoder.encode(invalidSchemaAttempt)
        try data.write(to: journal.journalFileURL)

        let result = journal.loadJournal()
        if case .corrupted(let reason) = result {
            XCTAssertTrue(reason.contains("Unsupported active journal schema version 99.9"))
        } else {
            XCTFail("Expected .corrupted result")
        }

        XCTAssertFalse(FileManager.default.fileExists(atPath: journal.journalFileURL.path))
        XCTAssertTrue(FileManager.default.fileExists(atPath: journal.quarantineDirectoryURL.path))
    }

    @MainActor
    func testJournalClearedOnNormalFinishOrAbort() throws {
        let suiteName = "ActiveRunJournalTests.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suiteName)!
        defer { defaults.removePersistentDomain(forName: suiteName) }

        let docDir = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: docDir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: docDir) }

        let model = AppModel(defaults: defaults, documentsDirectory: docDir)
        let mission = try XCTUnwrap(model.mission)

        let journal = ActiveRunJournal(defaults: defaults, documentsDirectory: docDir)
        let attempt = ActiveRunAttempt(
            schemaVersion: "0.1",
            runID: "normal-run",
            missionID: mission.missionID,
            bindingID: mission.bindingID,
            audioSHA256: mission.audioSHA256,
            routeWorkoutFingerprint: mission.routeWorkoutFingerprint,
            partialGPXBasename: "normal-run.partial.gpx",
            condition: "A",
            phase: .running,
            startedAt: Date(),
            pauseCount: 0,
            audioIncidents: [],
            locationIncidents: []
        )
        try journal.save(attempt)
        XCTAssertNotNil(journal.currentAttempt)
        XCTAssertTrue(FileManager.default.fileExists(atPath: journal.journalFileURL.path))

        try journal.clear()
        XCTAssertNil(journal.currentAttempt)
        XCTAssertFalse(FileManager.default.fileExists(atPath: journal.journalFileURL.path))
        XCTAssertNil(defaults.data(forKey: ActiveRunJournal.journalKey))
    }

    @MainActor
    func testPendingDebriefsAndPendingRecallsUseFileBackedStorage() throws {
        let suiteName = "ActiveRunJournalTests.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suiteName)!
        defer { defaults.removePersistentDomain(forName: suiteName) }

        let docDir = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: docDir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: docDir) }

        let model = AppModel(defaults: defaults, documentsDirectory: docDir)
        let mission = try XCTUnwrap(model.mission)

        let context = RunSessionContext(
            runID: "file-backed-run",
            missionID: mission.missionID,
            bindingID: mission.bindingID,
            audioSHA256: mission.audioSHA256,
            routeWorkoutFingerprint: mission.routeWorkoutFingerprint,
            condition: "A",
            startedAt: Date(),
            endedAt: Date().addingTimeInterval(300),
            precommittedNextWorkoutAt: Date().addingTimeInterval(48 * 3600),
            completed: true,
            aborted: false,
            abortReason: "",
            audioElapsedSeconds: 300,
            pauseCount: 0,
            track: nil,
            routeTraversalEvidence: nil,
            audioIncidents: [],
            locationIncidents: []
        )

        try model.scheduleDebrief(for: context)
        try model.scheduleRecall(for: context)

        // Verify JSON files exist on disk in documentsDirectory
        XCTAssertTrue(FileManager.default.fileExists(atPath: model.pendingDebriefsFileURL.path))
        XCTAssertTrue(FileManager.default.fileExists(atPath: model.pendingRecallsFileURL.path))

        let restoredModel = AppModel(defaults: defaults, documentsDirectory: docDir)
        XCTAssertEqual(restoredModel.pendingDebriefs.count, 1)
        XCTAssertEqual(restoredModel.pendingDebriefs.first?.runID, "file-backed-run")
        XCTAssertEqual(restoredModel.pendingRecalls.count, 1)
        XCTAssertEqual(restoredModel.pendingRecalls.first?.runID, "file-backed-run")
    }

    @MainActor
    func testSaveFailureThrowsAndPreservesJournalState() throws {
        let suiteName = "ActiveRunJournalTests.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suiteName)!
        defer { defaults.removePersistentDomain(forName: suiteName) }

        let docDir = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: docDir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: docDir) }

        let journal = ActiveRunJournal(defaults: defaults, documentsDirectory: docDir)
        let fileURL = journal.journalFileURL

        // Create a directory at fileURL so writeAtomicStaging throws when trying to write a file
        try FileManager.default.createDirectory(at: fileURL, withIntermediateDirectories: true)

        let attempt = ActiveRunAttempt(
            runID: "test-save-failure",
            missionID: "m01",
            bindingID: "b01",
            audioSHA256: "sha256",
            routeWorkoutFingerprint: "fp",
            phase: .running,
            startedAt: Date()
        )

        XCTAssertThrowsError(try journal.save(attempt))
    }

    @MainActor
    func testDebriefEnqueueFailurePreservesActiveJournalAndDisplaysRecoverableError() throws {
        let suiteName = "ActiveRunJournalTests.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suiteName)!
        defer { defaults.removePersistentDomain(forName: suiteName) }

        let docDir = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: docDir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: docDir) }

        let model = AppModel(defaults: defaults, documentsDirectory: docDir)
        let mission = try XCTUnwrap(model.mission)

        let fakeAudio = FakeAudioController()
        let fakeRecorder = FakeLocationRecorder()
        fakeRecorder.startResult = .started

        let coordinator = SessionCoordinator(mission: mission, appModel: model, audio: fakeAudio, recorder: fakeRecorder)
        coordinator.send(.requestStart(runID: "failure-run-1", now: Date()))
        coordinator.send(.receiveGPSFix(accuracy: 10, distanceToStartMeters: 5))
        coordinator.send(.receiveGPSFix(accuracy: 10, distanceToStartMeters: 5))
        coordinator.send(.audioStarted())
        XCTAssertTrue(coordinator.isRunning)

        let journal = ActiveRunJournal(defaults: defaults, documentsDirectory: docDir)
        XCTAssertTrue(FileManager.default.fileExists(atPath: journal.journalFileURL.path))

        // Create a directory at pendingDebriefsFileURL so scheduleDebrief fails when saving
        let debriefsURL = model.pendingDebriefsFileURL
        try FileManager.default.createDirectory(at: debriefsURL, withIntermediateDirectories: true)

        coordinator.abortSession(reason: "Trigger failure injection")

        // Debrief enqueue fails -> clearJournal is skipped -> active journal remains intact
        XCTAssertTrue(FileManager.default.fileExists(atPath: journal.journalFileURL.path))
        XCTAssertNotNil(model.journalErrorBanner)
        XCTAssertTrue(model.journalErrorBanner?.contains("debrief") == true || model.journalErrorBanner?.contains("Не удалось") == true)
    }

    @MainActor
    func testDurableDebriefEnqueuedBeforeJournalClear() throws {
        let suiteName = "ActiveRunJournalTests.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suiteName)!
        defer { defaults.removePersistentDomain(forName: suiteName) }

        let model = AppModel(defaults: defaults)
        let mission = try XCTUnwrap(model.mission)
        let nextWorkout = Date().addingTimeInterval(48 * 3600)

        // 1. Test natural finish action sequence
        var sm1 = SessionStateMachine(initialState: .running(
            runID: "run-finish",
            startedAt: Date(),
            runStartedAt: Date(),
            pauseCount: 0,
            isPlaying: true
        ))
        let samples = [
            TrackSample(latitude: -33.0472, longitude: -71.6127, elevation: 10.0, horizontalAccuracy: 5.0, timestamp: Date()),
            TrackSample(latitude: -33.0473, longitude: -71.6128, elevation: 11.0, horizontalAccuracy: 5.0, timestamp: Date().addingTimeInterval(10))
        ]
        let sampleTrack = try TrackSummary.make(fileName: "test.gpx", samples: samples)
        let actionsFinish = sm1.handle(
            event: .audioFinishedNaturally(
                summary: sampleTrack,
                routeTraversal: nil,
                audioIncidents: [],
                locationIncidents: [],
                elapsed: 1800
            ),
            mission: mission,
            precommittedNextWorkoutAt: nextWorkout
        )

        let debriefIndex1 = actionsFinish.firstIndex {
            if case .scheduleDebrief = $0 { return true }
            return false
        }
        let clearIndex1 = actionsFinish.firstIndex {
            if case .clearJournal = $0 { return true }
            return false
        }

        XCTAssertNotNil(debriefIndex1)
        XCTAssertNotNil(clearIndex1)
        XCTAssertTrue(debriefIndex1! < clearIndex1!, "scheduleDebrief must occur before clearJournal on finish")

        // 2. Test user abort action sequence
        var sm2 = SessionStateMachine(initialState: .running(
            runID: "run-abort",
            startedAt: Date(),
            runStartedAt: Date(),
            pauseCount: 0,
            isPlaying: true
        ))
        let actionsAbort = sm2.handle(
            event: .userAborted(
                reason: "Test user abort",
                summary: sampleTrack,
                routeTraversal: nil,
                audioIncidents: [],
                locationIncidents: [],
                elapsed: 300
            ),
            mission: mission,
            precommittedNextWorkoutAt: nextWorkout
        )

        let debriefIndex2 = actionsAbort.firstIndex {
            if case .scheduleDebrief = $0 { return true }
            return false
        }
        let clearIndex2 = actionsAbort.firstIndex {
            if case .clearJournal = $0 { return true }
            return false
        }

        XCTAssertNotNil(debriefIndex2)
        XCTAssertNotNil(clearIndex2)
        XCTAssertTrue(debriefIndex2! < clearIndex2!, "scheduleDebrief must occur before clearJournal on abort")

        // 3. Test crash recovery action sequence
        var sm3 = SessionStateMachine(initialState: .ready)
        let attempt = ActiveRunAttempt(
            schemaVersion: "0.1",
            runID: "recovered-run",
            missionID: mission.missionID,
            bindingID: mission.bindingID,
            audioSHA256: mission.audioSHA256,
            routeWorkoutFingerprint: mission.routeWorkoutFingerprint,
            partialGPXBasename: "recovered.partial.gpx",
            phase: .running,
            startedAt: Date()
        )
        let actionsCrash = sm3.handle(
            event: .processCrashRecovered(attempt: attempt),
            mission: mission,
            precommittedNextWorkoutAt: nextWorkout
        )

        let debriefIndex3 = actionsCrash.firstIndex {
            if case .scheduleDebrief = $0 { return true }
            return false
        }
        let clearIndex3 = actionsCrash.firstIndex {
            if case .clearJournal = $0 { return true }
            return false
        }

        XCTAssertNotNil(debriefIndex3)
        XCTAssertNotNil(clearIndex3)
        XCTAssertTrue(debriefIndex3! < clearIndex3!, "scheduleDebrief must occur before clearJournal on crash recovery")
    }

    @MainActor
    func testQuarantineOrderingReadsBytesWritesStagingVerifiesAndDeletesOriginal() throws {
        let suiteName = "ActiveRunJournalTests.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suiteName)!
        defer { defaults.removePersistentDomain(forName: suiteName) }

        let docDir = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: docDir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: docDir) }

        let journal = ActiveRunJournal(defaults: defaults, documentsDirectory: docDir)
        let corruptedBytes = Data("corrupted active journal content".utf8)
        try corruptedBytes.write(to: journal.journalFileURL)

        XCTAssertTrue(FileManager.default.fileExists(atPath: journal.journalFileURL.path))

        let quarantinedURL = try journal.quarantineCorruptedJournal(reason: "test corruption", rawData: corruptedBytes)

        // 1. Verify published quarantine file exists and contains exact original bytes
        XCTAssertTrue(FileManager.default.fileExists(atPath: quarantinedURL.path))
        let publishedData = try Data(contentsOf: quarantinedURL)
        XCTAssertEqual(publishedData, corruptedBytes)

        // 2. Verify original source journal file was deleted only after quarantine verification
        XCTAssertFalse(FileManager.default.fileExists(atPath: journal.journalFileURL.path))
    }

    @MainActor
    func testQuarantineReadFailureDoesNotWriteEmptyData() throws {
        let suiteName = "ActiveRunJournalTests.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suiteName)!
        defer { defaults.removePersistentDomain(forName: suiteName) }

        let docDir = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: docDir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: docDir) }

        let journal = ActiveRunJournal(defaults: defaults, documentsDirectory: docDir)

        // Create a directory at journalFileURL path so Data(contentsOf:) throws a read error
        try FileManager.default.createDirectory(at: journal.journalFileURL, withIntermediateDirectories: true)

        XCTAssertThrowsError(try journal.quarantineCorruptedJournal(reason: "read error", rawData: nil))

        // Verify no quarantine file containing empty Data was written
        if FileManager.default.fileExists(atPath: journal.quarantineDirectoryURL.path) {
            let files = try FileManager.default.contentsOfDirectory(atPath: journal.quarantineDirectoryURL.path)
            XCTAssertTrue(files.isEmpty, "No empty quarantine files should be written on read failure")
        }
    }

    @MainActor
    func testResetQuarantineValidatesDeletionBeforeClearingLockState() throws {
        let suiteName = "ActiveRunJournalTests.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suiteName)!
        defer { defaults.removePersistentDomain(forName: suiteName) }

        let docDir = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: docDir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: docDir) }

        let journal = ActiveRunJournal(defaults: defaults, documentsDirectory: docDir)
        let corruptedData = Data("corrupted data".utf8)
        try corruptedData.write(to: journal.journalFileURL)

        let model = AppModel(defaults: defaults, documentsDirectory: docDir)
        XCTAssertTrue(model.journalCorrupted)
        XCTAssertNotNil(model.journalErrorBanner)

        model.resetJournalQuarantine()

        XCTAssertFalse(FileManager.default.fileExists(atPath: journal.quarantineDirectoryURL.path))
        XCTAssertFalse(model.journalCorrupted)
        XCTAssertNil(model.journalErrorBanner)
    }

    @MainActor
    func testRelaunchRecoveryBindsPartialGPXByExactBasename() throws {
        let suiteName = "ActiveRunJournalTests.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suiteName)!
        defer { defaults.removePersistentDomain(forName: suiteName) }

        let docDir = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: docDir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: docDir) }

        let initialModel = AppModel(defaults: defaults, documentsDirectory: docDir)
        let mission = try XCTUnwrap(initialModel.mission)

        let partialBasename = "recovered-run-456.partial.gpx"
        let partialURL = docDir.appendingPathComponent(partialBasename)
        let baseDate = Date().addingTimeInterval(-600)
        let samples = [
            TrackSample(latitude: -33.0472, longitude: -71.6127, elevation: 10.0, horizontalAccuracy: 5.0, timestamp: baseDate),
            TrackSample(latitude: -33.0473, longitude: -71.6128, elevation: 11.0, horizontalAccuracy: 5.0, timestamp: baseDate.addingTimeInterval(30))
        ]
        let gpxData = try GPXDocument.data(samples: samples)
        try gpxData.write(to: partialURL)

        let attempt = ActiveRunAttempt(
            schemaVersion: "0.1",
            runID: "recovered-run-456",
            missionID: mission.missionID,
            bindingID: mission.bindingID,
            audioSHA256: mission.audioSHA256,
            routeWorkoutFingerprint: mission.routeWorkoutFingerprint,
            partialGPXBasename: partialBasename,
            condition: "A",
            phase: .running,
            startedAt: baseDate,
            pauseCount: 0,
            audioIncidents: [],
            locationIncidents: []
        )
        let preJournal = ActiveRunJournal(defaults: defaults, documentsDirectory: docDir)
        try preJournal.save(attempt)

        let relaunchModel = AppModel(defaults: defaults, documentsDirectory: docDir)

        XCTAssertEqual(relaunchModel.pendingDebriefs.count, 1)
        let debrief = try XCTUnwrap(relaunchModel.pendingDebriefs.first)
        XCTAssertEqual(debrief.runID, "recovered-run-456")
        XCTAssertNotNil(debrief.track)
        XCTAssertEqual(debrief.track?.fileName, partialBasename)
        XCTAssertEqual(debrief.track?.sampleCount, 2)
    }

    @MainActor
    func testRelaunchRecoveryPathTraversalCheckRejectsInvalidBasename() throws {
        let suiteName = "ActiveRunJournalTests.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suiteName)!
        defer { defaults.removePersistentDomain(forName: suiteName) }

        let docDir = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: docDir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: docDir) }

        let initialModel = AppModel(defaults: defaults, documentsDirectory: docDir)
        let mission = try XCTUnwrap(initialModel.mission)

        let attempt = ActiveRunAttempt(
            schemaVersion: "0.1",
            runID: "traversal-run-789",
            missionID: mission.missionID,
            bindingID: mission.bindingID,
            audioSHA256: mission.audioSHA256,
            routeWorkoutFingerprint: mission.routeWorkoutFingerprint,
            partialGPXBasename: "../../etc/passwd",
            condition: "A",
            phase: .running,
            startedAt: Date().addingTimeInterval(-300),
            pauseCount: 0,
            audioIncidents: [],
            locationIncidents: []
        )
        let preJournal = ActiveRunJournal(defaults: defaults, documentsDirectory: docDir)
        try preJournal.save(attempt)

        let relaunchModel = AppModel(defaults: defaults, documentsDirectory: docDir)

        XCTAssertEqual(relaunchModel.pendingDebriefs.count, 1)
        let debrief = try XCTUnwrap(relaunchModel.pendingDebriefs.first)
        XCTAssertEqual(debrief.runID, "traversal-run-789")
        XCTAssertNil(debrief.track, "Path traversal in partialGPXBasename must be rejected")
    }
}
