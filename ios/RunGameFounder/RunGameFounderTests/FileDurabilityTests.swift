import XCTest
@testable import RunGameFounder

@MainActor
final class FileDurabilityTests: XCTestCase {
    nonisolated(unsafe) private var tempDirectory: URL!

    override func setUpWithError() throws {
        try super.setUpWithError()
        FileDurability.injectedFailure = .none
        tempDirectory = FileManager.default.temporaryDirectory
            .appendingPathComponent("FileDurabilityTests-\(UUID().uuidString)", isDirectory: true)
        try FileManager.default.createDirectory(at: tempDirectory, withIntermediateDirectories: true)
    }

    override func tearDownWithError() throws {
        FileDurability.injectedFailure = .none
        if tempDirectory != nil {
            try? FileManager.default.removeItem(at: tempDirectory)
        }
        try super.tearDownWithError()
    }

    func testAtomicDraftWriteAndBackupExclusion() throws {
        let fileURL = tempDirectory.appendingPathComponent("test-draft.json")
        let draftData = Data("{\"status\": \"draft\"}".utf8)

        try FileDurability.writeAtomicDraft(data: draftData, to: fileURL)

        XCTAssertTrue(FileManager.default.fileExists(atPath: fileURL.path))
        let readData = try Data(contentsOf: fileURL)
        XCTAssertEqual(readData, draftData)
        XCTAssertTrue(FileDurability.isExcludedFromBackup(url: fileURL))
    }

    func testFinalEvidenceWithoutOverwritingProtection() throws {
        let fileURL = tempDirectory.appendingPathComponent("test-final-evidence.json")
        let initialData = Data("{\"status\": \"initial\"}".utf8)
        let replacementData = Data("{\"status\": \"replacement\"}".utf8)

        try FileDurability.writeFinalEvidence(data: initialData, to: fileURL)
        XCTAssertTrue(FileManager.default.fileExists(atPath: fileURL.path))
        XCTAssertTrue(FileDurability.isExcludedFromBackup(url: fileURL))

        XCTAssertThrowsError(
            try FileDurability.writeFinalEvidence(data: replacementData, to: fileURL)
        ) { error in
            let nsError = error as NSError
            XCTAssertEqual(nsError.domain, NSCocoaErrorDomain)
            XCTAssertEqual(nsError.code, NSFileWriteFileExistsError)
        }

        let preservedData = try Data(contentsOf: fileURL)
        XCTAssertEqual(preservedData, initialData)
    }

    func testFinalEvidenceStagingSyncAndAtomicRename() throws {
        let fileURL = tempDirectory.appendingPathComponent("test-staging-final.json")
        let finalData = Data("{\"status\": \"staged_and_synced\"}".utf8)

        try FileDurability.writeFinalEvidence(data: finalData, to: fileURL)
        XCTAssertTrue(FileManager.default.fileExists(atPath: fileURL.path))

        // Check content
        let readData = try Data(contentsOf: fileURL)
        XCTAssertEqual(readData, finalData)
        XCTAssertTrue(FileDurability.isExcludedFromBackup(url: fileURL))

        // Verify temporary staging file (.tmp.<uuid>) is no longer present in directory
        let files = try FileManager.default.contentsOfDirectory(atPath: tempDirectory.path)
        let tmpFiles = files.filter { $0.hasPrefix(".tmp.") }
        XCTAssertTrue(tmpFiles.isEmpty)
    }

    func testSHA256VerificationBeforeApproval() throws {
        let fileURL = tempDirectory.appendingPathComponent("test-track.gpx")
        let trackData = Data("<gpx><trk></trk></gpx>".utf8)
        try FileDurability.writeAtomicDraft(data: trackData, to: fileURL)

        let expectedSHA = BundleIntegrity.sha256(of: trackData)
        XCTAssertTrue(FileDurability.verifySHA256(of: fileURL, expectedSHA: expectedSHA))

        let tamperedData = Data("<gpx><trk>TAMPERED</trk></gpx>".utf8)
        try tamperedData.write(to: fileURL, options: .atomic)
        XCTAssertFalse(FileDurability.verifySHA256(of: fileURL, expectedSHA: expectedSHA))
    }

    @MainActor
    func testCorruptedQueueInAppModelFailsClosed() throws {
        let suiteName = "FileDurabilityTests.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suiteName)!
        defer { defaults.removePersistentDomain(forName: suiteName) }

        let docDir = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: docDir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: docDir) }

        let queueKeyBytes: [UInt8] = [102, 111, 117, 110, 100, 101, 114, 46, 118, 50, 46, 112, 101, 110, 100, 105, 110, 103, 68, 101, 98, 114, 105, 101, 102, 115]
        let debriefKey = String(bytes: queueKeyBytes, encoding: .utf8)!
        defaults.set(Data("corrupted json data".utf8), forKey: debriefKey)

        let model = AppModel(defaults: defaults, documentsDirectory: docDir)

        XCTAssertTrue(model.queueCorrupted)
        XCTAssertTrue(model.evidenceCaptureLocked)

        // Also verify corrupted file on disk sets queueCorrupted
        let docDir2 = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: docDir2, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: docDir2) }

        let fileURL = docDir2.appendingPathComponent("pending_debriefs.json")
        try Data("corrupted json data".utf8).write(to: fileURL)

        let model2 = AppModel(defaults: defaults, documentsDirectory: docDir2)
        XCTAssertTrue(model2.queueCorrupted)
        XCTAssertTrue(model2.evidenceCaptureLocked)
    }

    @MainActor
    func testConcurrentAtomicWrites() async throws {
        let iterations = 20
        let expectation = expectation(description: "Concurrent atomic writes complete")
        expectation.expectedFulfillmentCount = iterations

        let targetDir = tempDirectory!

        DispatchQueue.concurrentPerform(iterations: iterations) { index in
            let fileURL = targetDir.appendingPathComponent("concurrent-\(index).json")
            let data = Data("{\"index\": \(index)}".utf8)
            do {
                try FileDurability.writeAtomicDraft(data: data, to: fileURL)
                let readData = try Data(contentsOf: fileURL)
                XCTAssertEqual(readData, data)
                XCTAssertTrue(FileDurability.isExcludedFromBackup(url: fileURL))
            } catch {
                XCTFail("Concurrent write failed for index \(index): \(error)")
            }
            expectation.fulfill()
        }

        await fulfillment(of: [expectation], timeout: 10.0)

        let files = try FileManager.default.contentsOfDirectory(atPath: targetDir.path)
        let tmpFiles = files.filter { $0.hasPrefix(".tmp.") }
        XCTAssertTrue(tmpFiles.isEmpty, "Leftover staging files found: \(tmpFiles)")
    }

    @MainActor
    func testConcurrentOverwriteProtection() async throws {
        let fileURL = tempDirectory.appendingPathComponent("concurrent-overwrite.json")
        let initialData = Data("{\"status\": \"initial\"}".utf8)
        try FileDurability.writeFinalEvidence(data: initialData, to: fileURL)

        let iterations = 20
        let expectation = expectation(description: "Concurrent overwrite attempts complete")
        expectation.expectedFulfillmentCount = iterations

        DispatchQueue.concurrentPerform(iterations: iterations) { index in
            let replacementData = Data("{\"status\": \"replacement-\(index)\"}".utf8)
            do {
                try FileDurability.writeFinalEvidence(data: replacementData, to: fileURL)
                XCTFail("writeFinalEvidence should have thrown NSFileWriteFileExistsError for index \(index)")
            } catch {
                let nsError = error as NSError
                XCTAssertEqual(nsError.domain, NSCocoaErrorDomain)
                XCTAssertEqual(nsError.code, NSFileWriteFileExistsError)
            }
            expectation.fulfill()
        }

        await fulfillment(of: [expectation], timeout: 10.0)

        let preservedData = try Data(contentsOf: fileURL)
        XCTAssertEqual(preservedData, initialData)

        let files = try FileManager.default.contentsOfDirectory(atPath: tempDirectory.path)
        let tmpFiles = files.filter { $0.hasPrefix(".tmp.") }
        XCTAssertTrue(tmpFiles.isEmpty, "Leftover staging files found: \(tmpFiles)")
    }

    @MainActor
    func test20ConcurrentWritersToUncreatedDestinationURL() async throws {
        let fileURL = tempDirectory.appendingPathComponent("concurrent-uncreated-target.json")
        let iterations = 20
        let expectation = expectation(description: "20 concurrent writers to uncreated destination complete")
        expectation.expectedFulfillmentCount = iterations

        nonisolated(unsafe) var successCount = 0
        nonisolated(unsafe) var fileExistsRejections = 0
        nonisolated(unsafe) var unexpectedErrors: [String] = []
        nonisolated(unsafe) var winningPayload: Data?
        let lock = NSLock()

        DispatchQueue.concurrentPerform(iterations: iterations) { index in
            let payload = Data("{\"writer_index\": \(index)}".utf8)
            do {
                try FileDurability.writeFinalEvidence(data: payload, to: fileURL)
                lock.withLock {
                    successCount += 1
                    winningPayload = payload
                }
            } catch {
                let nsError = error as NSError
                if nsError.domain == NSCocoaErrorDomain && nsError.code == NSFileWriteFileExistsError {
                    lock.withLock {
                        fileExistsRejections += 1
                    }
                } else {
                    lock.withLock {
                        unexpectedErrors.append("Index \(index) failed with unexpected error: \(error)")
                    }
                }
            }
            expectation.fulfill()
        }

        await fulfillment(of: [expectation], timeout: 10.0)

        XCTAssertEqual(unexpectedErrors, [], "No unexpected errors should occur")
        XCTAssertEqual(successCount, 1, "Exactly 1 writer should succeed")
        XCTAssertEqual(fileExistsRejections, 19, "Exactly 19 writers should receive file-exists rejection")

        XCTAssertTrue(FileManager.default.fileExists(atPath: fileURL.path), "Destination file must exist")
        let readData = try Data(contentsOf: fileURL)
        XCTAssertEqual(readData, winningPayload, "Destination file content must match winning payload")
        XCTAssertTrue(FileDurability.isExcludedFromBackup(url: fileURL), "Destination file must be excluded from backup")

        let files = try FileManager.default.contentsOfDirectory(atPath: tempDirectory.path)
        let tmpFiles = files.filter { $0.hasPrefix(".tmp.") }
        XCTAssertTrue(tmpFiles.isEmpty, "Zero temporary staging files should remain, found: \(tmpFiles)")
    }

    func testOverwriteFailureCleansStagingAndPreservesOriginal() throws {
        let fileURL = tempDirectory.appendingPathComponent("overwrite-failure.json")
        let initialData = Data("{\"status\": \"original\"}".utf8)
        try FileDurability.writeAtomicDraft(data: initialData, to: fileURL)

        let overwriteData = Data("{\"status\": \"blocked\"}".utf8)

        XCTAssertThrowsError(
            try FileDurability.writeAtomicStaging(data: overwriteData, to: fileURL, overwrite: false)
        ) { error in
            let nsError = error as NSError
            XCTAssertEqual(nsError.domain, NSCocoaErrorDomain)
            XCTAssertEqual(nsError.code, NSFileWriteFileExistsError)
        }

        let currentData = try Data(contentsOf: fileURL)
        XCTAssertEqual(currentData, initialData)

        let files = try FileManager.default.contentsOfDirectory(atPath: tempDirectory.path)
        let tmpFiles = files.filter { $0.hasPrefix(".tmp.") }
        XCTAssertTrue(tmpFiles.isEmpty, "Staging file was not cleaned up after overwrite failure")
    }

    func testFilesystemFailureInjectionCleanUp() throws {
        let fileURL = tempDirectory.appendingPathComponent("failure-injection.json")
        let testData = Data("{\"status\": \"failure_test\"}".utf8)

        // 1. Fail staging write
        FileDurability.injectedFailure = .failStagingWrite
        XCTAssertThrowsError(try FileDurability.writeAtomicDraft(data: testData, to: fileURL))
        var files = try FileManager.default.contentsOfDirectory(atPath: tempDirectory.path)
        XCTAssertTrue(files.filter { $0.hasPrefix(".tmp.") }.isEmpty, "Staging file must be cleaned up on staging write failure")
        XCTAssertFalse(FileManager.default.fileExists(atPath: fileURL.path))

        // 2. Fail staging sync
        FileDurability.injectedFailure = .failStagingSync
        XCTAssertThrowsError(try FileDurability.writeAtomicDraft(data: testData, to: fileURL))
        files = try FileManager.default.contentsOfDirectory(atPath: tempDirectory.path)
        XCTAssertTrue(files.filter { $0.hasPrefix(".tmp.") }.isEmpty, "Staging file must be cleaned up on staging sync failure")
        XCTAssertFalse(FileManager.default.fileExists(atPath: fileURL.path))

        // 3. Fail fallback fsync
        FileDurability.injectedFailure = .failFallbackFsync
        XCTAssertThrowsError(try FileDurability.writeAtomicDraft(data: testData, to: fileURL))
        files = try FileManager.default.contentsOfDirectory(atPath: tempDirectory.path)
        XCTAssertTrue(files.filter { $0.hasPrefix(".tmp.") }.isEmpty, "Staging file must be cleaned up on fallback fsync failure")
        XCTAssertFalse(FileManager.default.fileExists(atPath: fileURL.path))

        // 4. Fail backup exclusion
        FileDurability.injectedFailure = .failBackupExclusion
        XCTAssertThrowsError(try FileDurability.writeAtomicDraft(data: testData, to: fileURL))
        files = try FileManager.default.contentsOfDirectory(atPath: tempDirectory.path)
        XCTAssertTrue(files.filter { $0.hasPrefix(".tmp.") }.isEmpty, "Staging file must be cleaned up on backup exclusion failure")
        XCTAssertFalse(FileManager.default.fileExists(atPath: fileURL.path))

        // 5. Fail publication
        FileDurability.injectedFailure = .failPublication
        XCTAssertThrowsError(try FileDurability.writeAtomicDraft(data: testData, to: fileURL))
        files = try FileManager.default.contentsOfDirectory(atPath: tempDirectory.path)
        XCTAssertTrue(files.filter { $0.hasPrefix(".tmp.") }.isEmpty, "Staging file must be cleaned up on publication failure")
        XCTAssertFalse(FileManager.default.fileExists(atPath: fileURL.path))

        // 6. Fail parent open
        FileDurability.injectedFailure = .failParentOpen
        XCTAssertThrowsError(try FileDurability.writeAtomicDraft(data: testData, to: fileURL))
        files = try FileManager.default.contentsOfDirectory(atPath: tempDirectory.path)
        XCTAssertTrue(files.filter { $0.hasPrefix(".tmp.") }.isEmpty, "Staging file must be cleaned up on parent open failure")

        // 7. Fail parent sync
        FileDurability.injectedFailure = .failParentSync
        XCTAssertThrowsError(try FileDurability.writeAtomicDraft(data: testData, to: fileURL))
        FileDurability.injectedFailure = .none
    }

    @MainActor
    func testDebriefQueueTransitionsPublishOnlyAfterDurableWrite() throws {
        let suiteName = "FileDurabilityTests.DebriefQueue.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suiteName)!
        defer { defaults.removePersistentDomain(forName: suiteName) }
        let model = AppModel(defaults: defaults, documentsDirectory: tempDirectory)
        let context = makeCompletedContext(runID: "durable-debrief")

        FileDurability.injectedFailure = .failPublication
        XCTAssertThrowsError(try model.scheduleDebrief(for: context))
        XCTAssertTrue(model.pendingDebriefs.isEmpty)
        XCTAssertTrue(model.queuePersistenceFailed)
        XCTAssertTrue(model.evidenceCaptureLocked)

        FileDurability.injectedFailure = .none
        try model.scheduleDebrief(for: context)
        let durableBeforeCompletion = try Data(contentsOf: model.pendingDebriefsFileURL)
        XCTAssertEqual(model.pendingDebriefs.map(\.runID), [context.runID])

        FileDurability.injectedFailure = .failPublication
        XCTAssertThrowsError(try model.completeDebrief(runID: context.runID))
        XCTAssertEqual(model.pendingDebriefs.map(\.runID), [context.runID])
        XCTAssertEqual(try Data(contentsOf: model.pendingDebriefsFileURL), durableBeforeCompletion)
        XCTAssertTrue(model.queuePersistenceFailed)
        XCTAssertTrue(model.evidenceCaptureLocked)

        FileDurability.injectedFailure = .none
        let restored = AppModel(defaults: defaults, documentsDirectory: tempDirectory)
        XCTAssertEqual(restored.pendingDebriefs.map(\.runID), [context.runID])
        try restored.completeDebrief(runID: context.runID)
        XCTAssertTrue(restored.pendingDebriefs.isEmpty)
        XCTAssertFalse(restored.queuePersistenceFailed)
    }

    @MainActor
    func testRecallQueueTransitionsPublishOnlyAfterDurableWrite() throws {
        let suiteName = "FileDurabilityTests.RecallQueue.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suiteName)!
        defer { defaults.removePersistentDomain(forName: suiteName) }
        let model = AppModel(defaults: defaults, documentsDirectory: tempDirectory)
        let context = makeCompletedContext(runID: "durable-recall")

        FileDurability.injectedFailure = .failPublication
        XCTAssertThrowsError(try model.scheduleRecall(for: context))
        XCTAssertTrue(model.pendingRecalls.isEmpty)
        XCTAssertTrue(model.queuePersistenceFailed)
        XCTAssertTrue(model.evidenceCaptureLocked)

        FileDurability.injectedFailure = .none
        try model.scheduleRecall(for: context)
        let durableBeforeCompletion = try Data(contentsOf: model.pendingRecallsFileURL)
        XCTAssertEqual(model.pendingRecalls.map(\.runID), [context.runID])

        FileDurability.injectedFailure = .failPublication
        XCTAssertThrowsError(try model.completeRecall(runID: context.runID))
        XCTAssertEqual(model.pendingRecalls.map(\.runID), [context.runID])
        XCTAssertEqual(try Data(contentsOf: model.pendingRecallsFileURL), durableBeforeCompletion)
        XCTAssertTrue(model.queuePersistenceFailed)
        XCTAssertTrue(model.evidenceCaptureLocked)

        FileDurability.injectedFailure = .none
        let restored = AppModel(defaults: defaults, documentsDirectory: tempDirectory)
        XCTAssertEqual(restored.pendingRecalls.map(\.runID), [context.runID])
        try restored.completeRecall(runID: context.runID)
        XCTAssertTrue(restored.pendingRecalls.isEmpty)
        XCTAssertFalse(restored.queuePersistenceFailed)
    }

    @MainActor
    func testCorruptedQueueCanBeQuarantinedAndResetWithoutDiscardingBytes() throws {
        let suiteName = "FileDurabilityTests.QueueRecovery.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suiteName)!
        defer { defaults.removePersistentDomain(forName: suiteName) }
        let corruptedData = Data("not valid queue json".utf8)
        let queueURL = tempDirectory.appendingPathComponent("pending_debriefs.json")
        try corruptedData.write(to: queueURL)

        let model = AppModel(defaults: defaults, documentsDirectory: tempDirectory)
        XCTAssertTrue(model.queueCorrupted)
        XCTAssertTrue(model.evidenceCaptureLocked)

        model.resetQueueQuarantine()

        XCTAssertFalse(model.queueCorrupted)
        XCTAssertFalse(model.queuePersistenceFailed)
        XCTAssertTrue(model.pendingDebriefs.isEmpty)
        XCTAssertTrue(model.pendingRecalls.isEmpty)
        XCTAssertEqual(model.queueQuarantineURLs.count, 1)
        XCTAssertEqual(try Data(contentsOf: try XCTUnwrap(model.queueQuarantineURLs.first)), corruptedData)

        let restored = AppModel(defaults: defaults, documentsDirectory: tempDirectory)
        XCTAssertFalse(restored.queueCorrupted)
        XCTAssertTrue(restored.pendingDebriefs.isEmpty)
        XCTAssertEqual(restored.queueQuarantineURLs.count, 1)
    }

    @MainActor
    func testInterruptedQueueTransactionRemainsFailClosedAcrossRelaunch() throws {
        let suiteName = "FileDurabilityTests.InterruptedQueue.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suiteName)!
        defer { defaults.removePersistentDomain(forName: suiteName) }
        let markerURL = tempDirectory.appendingPathComponent("pending_queue_transaction.json")
        let interruptedMarker = Data("interrupted transaction marker".utf8)
        try interruptedMarker.write(to: markerURL)

        let restored = AppModel(defaults: defaults, documentsDirectory: tempDirectory)

        XCTAssertTrue(restored.queuePersistenceFailed)
        XCTAssertTrue(restored.evidenceCaptureLocked)
        XCTAssertTrue(restored.pendingDebriefs.isEmpty)
        XCTAssertTrue(restored.pendingRecalls.isEmpty)
        XCTAssertTrue(restored.queueErrorBanner?.contains("interrupted queue transaction") == true)

        restored.resetQueueQuarantine()
        XCTAssertFalse(restored.queueCorrupted)
        XCTAssertFalse(restored.queuePersistenceFailed)
        XCTAssertFalse(FileManager.default.fileExists(atPath: markerURL.path))
        XCTAssertTrue(restored.queueQuarantineURLs.contains { url in
            (try? Data(contentsOf: url)) == interruptedMarker
        })
    }

    private func makeCompletedContext(runID: String) -> RunSessionContext {
        let endedAt = Date()
        return RunSessionContext(
            participantID: "participant_founder_durability",
            runID: runID,
            missionID: "m01",
            bindingID: "binding-durability",
            audioSHA256: String(repeating: "a", count: 64),
            routeWorkoutFingerprint: String(repeating: "b", count: 64),
            condition: "A",
            startedAt: endedAt.addingTimeInterval(-1800),
            endedAt: endedAt,
            precommittedNextWorkoutAt: endedAt.addingTimeInterval(86400),
            completed: true,
            aborted: false,
            abortReason: "",
            audioElapsedSeconds: 1800,
            pauseCount: 0,
            track: nil,
            routeTraversalEvidence: nil,
            audioIncidents: [],
            locationIncidents: []
        )
    }
}
